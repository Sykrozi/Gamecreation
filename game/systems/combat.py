"""
Turn-based combat system.

Flow per turn:
  1. Check for stun (skip turn if stunned)
  2. Tick status effects (poison damage, duration countdown)
  3. Player chooses action
  4. Resolve player action
  5. Monster acts (if alive)
  6. Check win/loss
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from core.constants import (
    CombatAction, CombatStyle, StatusEffect,
    FLEE_BASE_CHANCE, SPECIAL_STRIKE_COOLDOWN,
    WEAKNESS_MULTIPLIERS, WeaknessType,
)
from core.events import (
    bus, GameEvent,
    EVT_COMBAT_START, EVT_COMBAT_END, EVT_TURN_START, EVT_TURN_END,
    EVT_ACTION_TAKEN, EVT_DAMAGE_DEALT, EVT_ENTITY_DIED, EVT_STATUS_APPLIED,
    EVT_STATUS_EXPIRED, EVT_BOSS_PHASE_CHANGE, EVT_PLAYER_FLED, EVT_ITEM_USED,
)
from entities.player import Player
from entities.monster import MonsterInstance, BossInstance
from data.items import Consumable

if TYPE_CHECKING:
    from data.monsters import MonsterDefinition


class CombatResult(Enum):
    ONGOING = auto()
    PLAYER_WIN = auto()
    PLAYER_FLED = auto()
    PLAYER_DEAD = auto()


@dataclass
class TurnLog:
    turn: int
    actor: str
    action: str
    damage: int = 0
    heal: int = 0
    effects_applied: list[str] = field(default_factory=list)
    effects_expired: list[str] = field(default_factory=list)
    narrative: str = ""


@dataclass
class ActionResult:
    success: bool
    damage: int = 0
    heal: int = 0
    narrative: str = ""
    status_applied: list[StatusEffect] = field(default_factory=list)
    cooldown_set: int = 0


class CombatEngine:
    def __init__(self, player: Player, enemy: MonsterInstance):
        self.player = player
        self.enemy = enemy
        self.turn = 0
        self.result = CombatResult.ONGOING
        self.log: list[TurnLog] = []
        self._special_cooldown = 0
        self._charged_shot_ready = False
        self._player_retreating = False

    # ─── Public entry ───────────────────────────────────────────────────────

    def start(self) -> None:
        bus.emit(GameEvent(EVT_COMBAT_START, {
            "player": self.player.name,
            "enemy": self.enemy.name,
        }))

    def player_action(self, action: CombatAction, item_id: str | None = None) -> TurnLog:
        """Process a full turn: player acts, then enemy acts."""
        if self.result != CombatResult.ONGOING:
            raise RuntimeError("Combat is not ongoing.")

        self.turn += 1
        self.player.turn_count += 1
        log = TurnLog(turn=self.turn, actor=self.player.name, action=action.value)

        bus.emit(GameEvent(EVT_TURN_START, {"turn": self.turn}))

        # Tick cooldowns
        if self._special_cooldown > 0:
            self._special_cooldown -= 1

        # Stun check — player loses turn
        if self.player.effects.is_stunned():
            log.narrative = "You are stunned and cannot act!"
            log.effects_expired = [e.value for e in self.player.effects.tick_all()]
            self._enemy_turn(log)
            self._check_end()
            return log

        # Clear temporary stance from last turn
        if not self.player.effects.is_defending():
            self.player.effects.remove(StatusEffect.DEFENDING)
        self._player_retreating = False

        # Resolve player action
        result = self._resolve_player_action(action, item_id)
        log.damage = result.damage
        log.heal = result.heal
        log.narrative = result.narrative
        log.effects_applied = [e.value for e in result.status_applied]
        log.action = action.value

        # Poison tick on player
        poison_dmg = self.player.effects.get_poison_damage(self.player.max_hp)
        if poison_dmg:
            self.player._hp = max(0, self.player.hp - poison_dmg)
            log.narrative += f" | Poison deals {poison_dmg} damage to you."

        # Expire player effects
        expired = self.player.effects.tick_all()
        log.effects_expired = [e.value for e in expired]

        # Charge special bar on attack
        if action in (CombatAction.ATTACK, CombatAction.CHARGED_SHOT,
                      CombatAction.SPELL, CombatAction.AREA_ATTACK):
            self.player.charge_special(10)

        # Event: action taken
        bus.emit(GameEvent(EVT_ACTION_TAKEN, {
            "actor": self.player.name,
            "action": action.value,
            "damage": result.damage,
        }))

        if self.result == CombatResult.PLAYER_FLED:
            return log

        # Enemy turn (only if alive and player didn't flee)
        if self.enemy.is_alive:
            self._enemy_turn(log)

        # Poison tick on enemy
        enemy_poison = self.enemy.effects.get_poison_damage(self.enemy.max_hp)
        if enemy_poison:
            self.enemy.hp = max(0, self.enemy.hp - enemy_poison)
            log.narrative += f" | Poison deals {enemy_poison} to {self.enemy.name}."

        self.enemy.effects.tick_all()

        self._check_end()
        bus.emit(GameEvent(EVT_TURN_END, {"turn": self.turn, "result": self.result.name}))
        return log

    # ─── Player action resolvers ────────────────────────────────────────────

    def _resolve_player_action(self, action: CombatAction, item_id: str | None) -> ActionResult:
        style = self.player.active_style
        dispatch = {
            CombatAction.ATTACK: self._action_attack,
            CombatAction.DEFEND: self._action_defend,
            CombatAction.USE_ITEM: lambda: self._action_use_item(item_id),
            CombatAction.FLEE: self._action_flee,
            CombatAction.SPECIAL_STRIKE: self._action_special_strike,
            CombatAction.TAUNT: self._action_taunt,
            CombatAction.AREA_ATTACK: self._action_area_attack,
            CombatAction.CHARGED_SHOT: self._action_charged_shot,
            CombatAction.RETREAT: self._action_retreat,
            CombatAction.MULTI_SHOT: self._action_multi_shot,
            CombatAction.SPELL: self._action_spell,
            CombatAction.MAGIC_SHIELD: self._action_magic_shield,
            CombatAction.DEBUFF: self._action_debuff,
        }
        handler = dispatch.get(action)
        if not handler:
            return ActionResult(success=False, narrative="Unknown action.")
        return handler()

    def _base_damage(self) -> int:
        style = self.player.active_style
        power = self.player.active_power
        weapon = self.player.equipment.weapon
        dmg_min = weapon.damage_min if weapon else 1
        dmg_max = weapon.damage_max if weapon else max(2, power // 5)
        base = random.randint(dmg_min, dmg_max)
        # Scale with skill level
        scale = 1.0 + (power / 200)
        return int(base * scale)

    def _action_attack(self) -> ActionResult:
        dmg_raw = self._base_damage()
        dmg_dealt = self.enemy.take_damage(dmg_raw, self.player.active_style)
        weakness = self.enemy.get_weakness(self.player.active_style)
        suffix = ""
        if weakness == WeaknessType.WEAK:
            suffix = " [WEAK — bonus damage!]"
        elif weakness == WeaknessType.RESISTANT:
            suffix = " [Resistant — reduced damage]"
        elif weakness == WeaknessType.IMMUNE:
            suffix = " [IMMUNE — no damage!]"
        bus.emit(GameEvent(EVT_DAMAGE_DEALT, {
            "source": self.player.name, "target": self.enemy.name,
            "damage": dmg_dealt, "style": self.player.active_style.value,
        }))
        return ActionResult(
            success=True, damage=dmg_dealt,
            narrative=f"You attack {self.enemy.name} for {dmg_dealt} damage.{suffix}",
        )

    def _action_defend(self) -> ActionResult:
        self.player.effects.apply(StatusEffect.DEFENDING, duration=1)
        return ActionResult(
            success=True,
            narrative="You brace yourself, reducing incoming damage by 50%.",
        )

    def _action_use_item(self, item_id: str | None) -> ActionResult:
        if not item_id:
            return ActionResult(success=False, narrative="No item selected.")
        result = self.player.use_consumable(item_id)
        if not result["success"]:
            return ActionResult(success=False, narrative=result.get("error", "Item failed."))
        parts = []
        if "healed" in result:
            parts.append(f"You restore {result['healed']} HP.")
        if "cured" in result:
            parts.append(f"You cured {result['cured']}!")
        if "buff" in result:
            parts.append(f"You feel the effects of {result['buff']}!")
        bus.emit(GameEvent(EVT_ITEM_USED, {"item": item_id, "result": result}))
        return ActionResult(
            success=True, heal=result.get("healed", 0),
            narrative=" ".join(parts) or "Item used.",
        )

    def _action_flee(self) -> ActionResult:
        level_diff = self.player.skills.combat_level - self.enemy.definition.level
        chance = min(0.85, FLEE_BASE_CHANCE + level_diff * 0.02)
        if random.random() < chance:
            self.result = CombatResult.PLAYER_FLED
            bus.emit(GameEvent(EVT_PLAYER_FLED, {"player": self.player.name}))
            return ActionResult(success=True, narrative="You successfully fled!")
        dmg_raw = self.enemy.calculate_attack_damage()
        dmg = self.player.take_damage(dmg_raw)
        return ActionResult(
            success=False, damage=dmg,
            narrative=f"Flee failed! {self.enemy.name} hits you for {dmg} as you try to escape.",
        )

    def _action_special_strike(self) -> ActionResult:
        if self.player.active_style != CombatStyle.MELEE:
            return ActionResult(success=False, narrative="Special Strike is a Melee action.")
        if self._special_cooldown > 0:
            return ActionResult(
                success=False,
                narrative=f"Special Strike on cooldown ({self._special_cooldown} turns left).",
            )
        if not self.player.consume_special(self.player.equipment.weapon.special_cost
                                           if self.player.equipment.weapon else 100):
            return ActionResult(success=False, narrative="Not enough special bar.")
        dmg_raw = int(self._base_damage() * 1.75)
        dmg_dealt = self.enemy.take_damage(dmg_raw, CombatStyle.MELEE)
        self._special_cooldown = SPECIAL_STRIKE_COOLDOWN
        # Knockback chance (Strength-gated)
        str_lvl = self.player.skills.level
        from core.constants import SkillType
        stun_chance = min(0.4, self.player.skills.level(SkillType.STRENGTH) / 100)
        stun_msg = ""
        if random.random() < stun_chance:
            self.enemy.effects.apply(StatusEffect.STUN, duration=1)
            stun_msg = " Enemy is stunned!"
        return ActionResult(
            success=True, damage=dmg_dealt,
            status_applied=[StatusEffect.STUN] if stun_msg else [],
            narrative=f"Special Strike hits {self.enemy.name} for {dmg_dealt}!{stun_msg}",
        )

    def _action_taunt(self) -> ActionResult:
        """Melee — forces enemy to attack harder but also reduces its accuracy (no dodge)."""
        if self.player.active_style != CombatStyle.MELEE:
            return ActionResult(success=False, narrative="Taunt is a Melee action.")
        self.player.effects.apply(StatusEffect.RAGE, duration=3, magnitude=0.2)
        return ActionResult(
            success=True,
            status_applied=[StatusEffect.RAGE],
            narrative="You taunt the enemy! Your rage builds (+20% damage for 3 turns).",
        )

    def _action_area_attack(self) -> ActionResult:
        """Melee/Magic AoE — single target for now; designed for multi-enemy extension."""
        if self.player.active_style not in (CombatStyle.MELEE, CombatStyle.MAGIC):
            return ActionResult(success=False, narrative="Area Attack not available for Range.")
        dmg_raw = int(self._base_damage() * 0.8)  # slightly weaker per target
        dmg_dealt = self.enemy.take_damage(dmg_raw, self.player.active_style)
        return ActionResult(
            success=True, damage=dmg_dealt,
            narrative=f"Area attack sweeps {self.enemy.name} for {dmg_dealt}!",
        )

    def _action_charged_shot(self) -> ActionResult:
        if self.player.active_style != CombatStyle.RANGE:
            return ActionResult(success=False, narrative="Charged Shot is a Range action.")
        if not self._charged_shot_ready:
            self._charged_shot_ready = True
            self.player.effects.apply(StatusEffect.CHARGED, duration=1)
            return ActionResult(
                success=True,
                narrative="You draw back your bowstring... (Charged Shot next turn deals 2× damage).",
            )
        self._charged_shot_ready = False
        self.player.effects.remove(StatusEffect.CHARGED)
        dmg_raw = int(self._base_damage() * 2.0)
        dmg_dealt = self.enemy.take_damage(dmg_raw, CombatStyle.RANGE)
        return ActionResult(
            success=True, damage=dmg_dealt,
            narrative=f"Charged Shot fires! {self.enemy.name} takes {dmg_dealt} damage!",
        )

    def _action_retreat(self) -> ActionResult:
        if self.player.active_style != CombatStyle.RANGE:
            return ActionResult(success=False, narrative="Retreat is a Range action.")
        self._player_retreating = True
        self.player.effects.apply(StatusEffect.DEFENDING, duration=1, magnitude=0.3)
        return ActionResult(
            success=True, status_applied=[StatusEffect.DEFENDING],
            narrative="You retreat and take a defensive stance (+30% defense this turn).",
        )

    def _action_multi_shot(self) -> ActionResult:
        if self.player.active_style != CombatStyle.RANGE:
            return ActionResult(success=False, narrative="Multi-shot is a Range action.")
        shots = 3
        total_dmg = 0
        for _ in range(shots):
            dmg_raw = int(self._base_damage() * 0.6)
            total_dmg += self.enemy.take_damage(dmg_raw, CombatStyle.RANGE)
        return ActionResult(
            success=True, damage=total_dmg,
            narrative=f"Multi-shot fires {shots} arrows for {total_dmg} total damage!",
        )

    def _action_spell(self) -> ActionResult:
        if self.player.active_style != CombatStyle.MAGIC:
            return ActionResult(success=False, narrative="Spell is a Magic action.")
        dmg_raw = self._base_damage()
        # Magic ignores physical defense (passes pure magic bonus through)
        weakness = self.enemy.get_weakness(CombatStyle.MAGIC)
        if weakness == WeaknessType.IMMUNE:
            return ActionResult(
                success=True, damage=0,
                narrative=f"{self.enemy.name} is immune to magic! No damage.",
            )
        multiplier = WEAKNESS_MULTIPLIERS[weakness]
        dmg_dealt = max(0, int(dmg_raw * multiplier))
        self.enemy.hp = max(0, self.enemy.hp - dmg_dealt)
        return ActionResult(
            success=True, damage=dmg_dealt,
            narrative=f"Elemental spell hits {self.enemy.name} for {dmg_dealt}!",
        )

    def _action_magic_shield(self) -> ActionResult:
        if self.player.active_style != CombatStyle.MAGIC:
            return ActionResult(success=False, narrative="Magic Shield is a Magic action.")
        self.player.effects.apply(StatusEffect.MAGIC_SHIELD, duration=2, magnitude=0.35)
        return ActionResult(
            success=True, status_applied=[StatusEffect.MAGIC_SHIELD],
            narrative="Magic Shield activated! Absorbs 35% damage for 2 turns.",
        )

    def _action_debuff(self) -> ActionResult:
        if self.player.active_style != CombatStyle.MAGIC:
            return ActionResult(success=False, narrative="Debuff is a Magic action.")
        magic_lvl = self.player.skills.level
        from core.constants import SkillType
        mag_lvl = self.player.skills.level(SkillType.MAGIC)
        roll = random.random()
        chosen: StatusEffect | None = None
        if roll < 0.33:
            chosen = StatusEffect.SLOW
            self.enemy.effects.apply(StatusEffect.SLOW, duration=3)
        elif roll < 0.66:
            chosen = StatusEffect.POISON
            self.enemy.effects.apply(StatusEffect.POISON, duration=5,
                                     magnitude=max(0.5, mag_lvl / 99))
        else:
            chosen = StatusEffect.STUN
            duration = 1 if mag_lvl < 50 else 2
            self.enemy.effects.apply(StatusEffect.STUN, duration=duration)
        bus.emit(GameEvent(EVT_STATUS_APPLIED, {
            "target": self.enemy.name, "effect": chosen.value,
        }))
        return ActionResult(
            success=True, status_applied=[chosen],
            narrative=f"Debuff applied: {chosen.value} on {self.enemy.name}!",
        )

    # ─── Enemy turn ─────────────────────────────────────────────────────────

    def _enemy_turn(self, log: TurnLog) -> None:
        if self.enemy.effects.is_stunned():
            log.narrative += f" | {self.enemy.name} is stunned and cannot act."
            return

        if isinstance(self.enemy, BossInstance):
            self._boss_act(log)
        else:
            self._standard_enemy_act(log)

    def _standard_enemy_act(self, log: TurnLog) -> None:
        dmg_raw = self.enemy.calculate_attack_damage()
        dmg = self.player.take_damage(dmg_raw)
        log.narrative += f" | {self.enemy.name} attacks you for {dmg}."

    def _boss_act(self, log: TurnLog) -> None:
        boss = self.enemy
        assert isinstance(boss, BossInstance)

        # Phase transition check
        phase_data = boss.check_phase_transition()
        if phase_data:
            bus.emit(GameEvent(EVT_BOSS_PHASE_CHANGE, {
                "boss": boss.name,
                "phase": phase_data.phase,
                "description": phase_data.description,
            }))
            log.narrative += f" | ⚠ {boss.name} enters Phase {phase_data.phase}: {phase_data.description}!"

        attacks = boss.get_available_attacks()
        chosen = random.choice(attacks) if attacks else "melee_strike"
        self._resolve_boss_attack(boss, chosen, log)

    def _resolve_boss_attack(self, boss: BossInstance, attack: str, log: TurnLog) -> None:
        phase_mult = {1: 1.0, 2: 1.25, 3: 1.6}.get(boss.current_phase, 1.0)

        if attack in ("melee_strike", "stomp", "shadow_strike", "arcane_bolt"):
            dmg_raw = int(boss.calculate_attack_damage() * phase_mult)
            dmg = self.player.take_damage(dmg_raw)
            log.narrative += f" | {boss.name} uses {attack} for {dmg}."

        elif attack in ("power_strike", "dual_strike", "seismic_slam"):
            dmg_raw = int(boss.calculate_attack_damage() * phase_mult * 1.5)
            dmg = self.player.take_damage(dmg_raw)
            log.narrative += f" | {boss.name} uses {attack} for {dmg}!"

        elif attack == "battle_cry":
            log.narrative += f" | {boss.name} roars — next attack will be devastating!"

        elif attack == "berserk_strike":
            dmg_raw = int(boss.calculate_attack_damage() * phase_mult * 2.0)
            dmg = self.player.take_damage(dmg_raw)
            log.narrative += f" | BERSERK STRIKE! {boss.name} deals {dmg}!"

        elif attack == "venom_barrage":
            dmg_raw = int(boss.calculate_attack_damage() * phase_mult * 0.6)
            dmg = self.player.take_damage(dmg_raw)
            self.player.effects.apply(StatusEffect.POISON, duration=4)
            log.narrative += f" | Venom Barrage! {dmg} damage + Poisoned!"

        elif attack == "mana_drain":
            self.player.special_bar = max(0, self.player.special_bar - 30)
            log.narrative += f" | Mana Drain! Special bar reduced by 30."

        elif attack in ("apocalyptic_fury", "starfall", "shadow_apocalypse"):
            dmg_raw = int(boss.calculate_attack_damage() * phase_mult * 2.5)
            dmg = self.player.take_damage(dmg_raw)
            log.narrative += f" | ☠ {attack.upper()}! {boss.name} deals {dmg} — DEVASTATING!"

        elif attack == "death_mark":
            self.player.effects.apply(StatusEffect.SLOW, duration=3)
            log.narrative += f" | Death Mark applied! You are slowed for 3 turns."

        elif attack == "summon_goblins":
            log.narrative += " | Goblin minions are summoned! (Future: multi-enemy support)"

        else:
            dmg_raw = int(boss.calculate_attack_damage() * phase_mult)
            dmg = self.player.take_damage(dmg_raw)
            log.narrative += f" | {boss.name} uses {attack} for {dmg}."

    # ─── Win/loss check ─────────────────────────────────────────────────────

    def _check_end(self) -> None:
        if self.result in (CombatResult.PLAYER_FLED,):
            return
        if not self.enemy.is_alive:
            self.result = CombatResult.PLAYER_WIN
            bus.emit(GameEvent(EVT_ENTITY_DIED, {
                "entity": self.enemy.name,
                "xp_reward": self.enemy.xp_reward,
            }))
        elif not self.player.is_alive:
            self.result = CombatResult.PLAYER_DEAD
            bus.emit(GameEvent(EVT_ENTITY_DIED, {"entity": self.player.name}))

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def get_valid_actions(self) -> list[CombatAction]:
        style = self.player.active_style
        base = [CombatAction.ATTACK, CombatAction.DEFEND,
                CombatAction.USE_ITEM, CombatAction.FLEE]
        if style == CombatStyle.MELEE:
            extras = [CombatAction.SPECIAL_STRIKE, CombatAction.TAUNT, CombatAction.AREA_ATTACK]
        elif style == CombatStyle.RANGE:
            extras = [CombatAction.CHARGED_SHOT, CombatAction.RETREAT, CombatAction.MULTI_SHOT]
        else:
            extras = [CombatAction.SPELL, CombatAction.MAGIC_SHIELD, CombatAction.DEBUFF]
        return base + extras

    def enemy_weakness_info(self) -> dict[str, str]:
        return {
            style.value: self.enemy.get_weakness(style).value
            for style in CombatStyle
        }

    def summary(self) -> str:
        return (
            f"Turn {self.turn} | "
            f"Player: {self.player.hp}/{self.player.max_hp} HP | "
            f"Enemy: {self.enemy.hp}/{self.enemy.max_hp} HP | "
            f"Result: {self.result.name}"
        )
