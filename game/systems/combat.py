import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List


class CombatState(Enum):
    PLAYER_TURN = auto()
    VICTORY     = auto()
    DEFEAT      = auto()
    FLED        = auto()


class Action(Enum):
    ATTACK  = auto()
    DEFEND  = auto()
    FLEE    = auto()
    ITEM    = auto()
    ABILITY = auto()


@dataclass
class TurnResult:
    logs:          List[str]    = field(default_factory=list)
    player_damage: int          = 0
    enemy_damage:  int          = 0
    state:         CombatState  = CombatState.PLAYER_TURN
    shake_player:  bool         = False
    shake_enemy:   bool         = False


class CombatSystem:
    def __init__(self, player, enemy):
        self.player = player
        self.enemy  = enemy
        self.state  = CombatState.PLAYER_TURN
        self.turn   = 0

    # ------------------------------------------------------------------

    def execute(self, action: Action, ability: str = None) -> TurnResult:
        result = TurnResult()
        self.turn += 1

        if action == Action.ATTACK:
            self._player_strikes(result)
            if result.state is CombatState.PLAYER_TURN:
                self._enemy_turn(result)

        elif action == Action.DEFEND:
            self.player.start_defend()
            result.logs.append("You brace for impact!")
            cs = getattr(self.player, 'combat_skills', None)
            if cs:
                for name in cs.grant_action_xp('defend'):
                    result.logs.append(f"[LEVEL UP] {name} skill!")
            self._enemy_turn(result)
            self.player.end_turn()

        elif action == Action.FLEE:
            if self._attempt_flee():
                result.logs.append("You escaped from battle!")
                result.state = CombatState.FLED
                self.state   = CombatState.FLED
                return result
            result.logs.append("No escape! The enemy blocks your path.")
            self._enemy_turn(result)

        elif action == Action.ITEM:
            self._enemy_turn(result)

        elif action == Action.ABILITY and ability:
            self._player_ability(result, ability)

        if result.state is CombatState.PLAYER_TURN and not self.player.alive:
            result.logs.append(f"You have been defeated by {self.enemy.name}...")
            result.state = CombatState.DEFEAT
            self.state   = CombatState.DEFEAT

        cs = getattr(self.player, 'combat_skills', None)
        if cs:
            cs.tick_all_cooldowns()

        return result

    # ------------------------------------------------------------------

    def _player_strikes(self, result: TurnResult):
        raw = self.player.roll_damage()
        dmg = self.enemy.receive_hit(raw)
        result.enemy_damage = dmg
        result.shake_enemy  = True
        result.logs.append(f"You hit {self.enemy.name} for {dmg} damage!")

        cs = getattr(self.player, 'combat_skills', None)
        if cs:
            for name in cs.grant_action_xp('attack'):
                result.logs.append(f"[LEVEL UP] {name} skill!")

        if not self.enemy.alive:
            result.logs.append(f"{self.enemy.name} has been defeated!")
            result.state = CombatState.VICTORY
            self.state   = CombatState.VICTORY

    def _enemy_turn(self, result: TurnResult):
        choice = self._ai_choose()
        if choice == "attack":
            raw = self.enemy.roll_damage()
            dmg = self.player.receive_hit(raw)
            result.player_damage = dmg
            result.shake_player  = True
            result.logs.append(
                f"{self.enemy.name} strikes you for {dmg} damage!"
            )
            cs = getattr(self.player, 'combat_skills', None)
            if cs:
                for name in cs.grant_action_xp('take_damage'):
                    result.logs.append(f"[LEVEL UP] {name} skill!")
        else:
            self.enemy.start_defend()
            result.logs.append(f"{self.enemy.name} takes a defensive stance!")

    def _player_ability(self, result: TurnResult, action: str):
        cs = getattr(self.player, 'combat_skills', None)
        if not cs:
            return
        cs.use_ability(action)

        if action == "heavy_strike":
            raw = int(self.player.roll_damage() * 1.5)
            dmg = self.enemy.receive_hit(raw)
            result.enemy_damage = dmg
            result.shake_enemy  = True
            result.logs.append(f"Heavy Strike! {dmg} damage!")
            self._ability_xp_and_victory(result, cs, action)
            if result.state is CombatState.PLAYER_TURN:
                self._enemy_turn(result)

        elif action == "flurry":
            total = 0
            for _ in range(2):
                raw = int(self.player.roll_damage() * 0.75)
                total += self.enemy.receive_hit(raw)
            result.enemy_damage = total
            result.shake_enemy  = True
            result.logs.append(f"Flurry! Two hits for {total} total damage!")
            self._ability_xp_and_victory(result, cs, action)
            if result.state is CombatState.PLAYER_TURN:
                self._enemy_turn(result)

        elif action == "cleave":
            raw = int(self.player.roll_damage() * 1.2)
            dmg = self.enemy.receive_hit(raw)
            result.enemy_damage = dmg
            result.shake_enemy  = True
            result.logs.append(f"Cleave! {dmg} damage!")
            self._ability_xp_and_victory(result, cs, action)
            if result.state is CombatState.PLAYER_TURN:
                self._enemy_turn(result)

        elif action == "power_strike":
            raw = int(self.player.roll_damage() * 1.3)
            saved = self.enemy._def
            self.enemy._def = int(saved * 0.6)
            dmg = self.enemy.receive_hit(raw)
            self.enemy._def = saved
            result.enemy_damage = dmg
            result.shake_enemy  = True
            result.logs.append(f"Power Strike! {dmg} damage (40% DEF ignored)!")
            self._ability_xp_and_victory(result, cs, action)
            if result.state is CombatState.PLAYER_TURN:
                self._enemy_turn(result)

        elif action == "berserk":
            result.logs.append(f"Berserk! +50% ATK for 3 turns!")
            for name in cs.grant_action_xp(action):
                result.logs.append(f"[LEVEL UP] {name} skill!")
            self._enemy_turn(result)

        elif action == "iron_skin":
            result.logs.append("Iron Skin! Next hit reduced by 60%!")
            for name in cs.grant_action_xp(action):
                result.logs.append(f"[LEVEL UP] {name} skill!")
            self._enemy_turn(result)

        elif action == "retaliate":
            self.player.start_defend()
            result.logs.append("Retaliate! Defending with counter ready...")
            for name in cs.grant_action_xp(action):
                result.logs.append(f"[LEVEL UP] {name} skill!")
            self._enemy_turn(result)
            if result.player_damage > 0 and result.state is CombatState.PLAYER_TURN:
                raw = self.player.roll_damage() // 2
                dmg = self.enemy.receive_hit(raw)
                if dmg > 0:
                    result.enemy_damage += dmg
                    result.shake_enemy   = True
                    result.logs.append(f"Counter-attack! {dmg} damage!")
                if not self.enemy.alive:
                    result.logs.append(f"{self.enemy.name} has been defeated!")
                    result.state = CombatState.VICTORY
                    self.state   = CombatState.VICTORY
            self.player.end_turn()

    def _ability_xp_and_victory(self, result, cs, action):
        for name in cs.grant_action_xp(action):
            result.logs.append(f"[LEVEL UP] {name} skill!")
        if not self.enemy.alive:
            result.logs.append(f"{self.enemy.name} has been defeated!")
            result.state = CombatState.VICTORY
            self.state   = CombatState.VICTORY

    def _ai_choose(self) -> str:
        hp_ratio = self.enemy.hp_ratio
        defend_bias = 0.10 if hp_ratio > 0.5 else 0.25
        if self.enemy.name == "Dark Lord":
            defend_bias += 0.10
        return "defend" if random.random() < defend_bias else "attack"

    def _attempt_flee(self) -> bool:
        speed_edge = self.player.speed - self.enemy.speed
        chance = 0.45 + speed_edge * 0.03
        return random.random() < max(0.15, min(0.80, chance))
