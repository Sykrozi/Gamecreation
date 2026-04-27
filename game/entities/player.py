from dataclasses import dataclass, field
from core.constants import (
    SkillType, CombatStyle, StatusEffect,
    DEATH_DURABILITY_PENALTY,
)
from core.events import bus, GameEvent, EVT_PLAYER_DIED
from entities.skill import SkillSet
from entities.inventory import Inventory, Equipment
from entities.status_effects import StatusEffectManager
from data.items import Consumable


@dataclass
class Player:
    name: str
    skills: SkillSet = field(default_factory=SkillSet)
    equipment: Equipment = field(default_factory=Equipment)
    inventory: Inventory = field(default_factory=Inventory)
    effects: StatusEffectManager = field(default_factory=StatusEffectManager)

    _hp: int = field(init=False)
    _max_hp: int = field(init=False)
    active_style: CombatStyle = CombatStyle.MELEE
    special_bar: int = 0       # 0–100
    special_bar_max: int = 100
    turn_count: int = 0

    def __post_init__(self):
        self._max_hp = self._calc_max_hp()
        self._hp = self._max_hp

    # ─── HP ────────────────────────────────────────────────────────────────

    def _calc_max_hp(self) -> int:
        res_lvl = self.skills.level(SkillType.RESISTANCE)
        base = 100 + (res_lvl - 1) * (350 / 98)
        bonus = self.equipment.total_attack_bonus // 10
        return int(base) + bonus

    @property
    def hp(self) -> int:
        return self._hp

    @property
    def max_hp(self) -> int:
        return self._max_hp

    @property
    def hp_fraction(self) -> float:
        return self._hp / self._max_hp

    def heal(self, amount: int) -> int:
        healed = min(amount, self._max_hp - self._hp)
        self._hp += healed
        return healed

    def take_damage(self, raw_damage: int) -> int:
        reduction = self.effects.damage_reduction()
        defense = self.equipment.total_defense_bonus
        def_reduction = min(defense / (defense + 100), 0.6)
        total_reduction = min(reduction + def_reduction, 0.85)
        damage = max(1, int(raw_damage * (1 - total_reduction)))
        self._hp = max(0, self._hp - damage)
        return damage

    @property
    def is_alive(self) -> bool:
        return self._hp > 0

    def die(self, run_inventory: list = None) -> None:
        bus.emit(GameEvent(EVT_PLAYER_DIED, {"player": self.name}))
        # Lose run drops
        self.inventory.clear_run_drops()
        # Extra durability penalty
        for piece in self.equipment.equipped_pieces():
            penalty = int(piece.max_durability * DEATH_DURABILITY_PENALTY)
            piece.durability = max(0, piece.durability - penalty)
        # Return to hub with full HP
        self._max_hp = self._calc_max_hp()
        self._hp = self._max_hp

    # ─── Combat stats ──────────────────────────────────────────────────────

    @property
    def attack_power(self) -> int:
        base = self.skills.level(SkillType.ATTACK)
        bonus = self.equipment.total_attack_bonus
        str_bonus = int(self.skills.level(SkillType.STRENGTH) * 0.5)
        rage_bonus = 0
        if self.effects.has(StatusEffect.RAGE):
            rage_bonus = int(base * 0.3)
        return base + bonus + str_bonus + rage_bonus

    @property
    def range_power(self) -> int:
        base = self.skills.level(SkillType.RANGE)
        return base + self.equipment.total_range_bonus

    @property
    def magic_power(self) -> int:
        base = self.skills.level(SkillType.MAGIC)
        return base + self.equipment.total_magic_bonus

    @property
    def active_power(self) -> int:
        if self.active_style == CombatStyle.MELEE:
            return self.attack_power
        if self.active_style == CombatStyle.RANGE:
            return self.range_power
        return self.magic_power

    # ─── Special bar ───────────────────────────────────────────────────────

    def charge_special(self, amount: int = 10) -> None:
        self.special_bar = min(self.special_bar_max, self.special_bar + amount)

    def consume_special(self, cost: int = 100) -> bool:
        if self.special_bar >= cost:
            self.special_bar -= cost
            return True
        return False

    # ─── Consumables ───────────────────────────────────────────────────────

    def use_consumable(self, item_id: str) -> dict:
        result: dict = {"success": False}
        item = next(
            (i for i in self.inventory.get_consumables() if i.id == item_id),
            None
        )
        if not item:
            result["error"] = "Item not found"
            return result

        if item.heal_amount:
            healed = self.heal(item.heal_amount)
            result["healed"] = healed

        if item.effect == "anti-venom":
            self.effects.remove(StatusEffect.POISON)
            result["cured"] = "poison"

        elif item.effect in ("strength", "defense", "overload"):
            if item.effect == "strength":
                self.effects.apply(StatusEffect.RAGE, item.effect_duration,
                                   item.effect_magnitude)
            elif item.effect == "overload":
                self.effects.apply(StatusEffect.RAGE, item.effect_duration,
                                   item.effect_magnitude)
            result["buff"] = item.effect

        if item.doses > 1:
            item.doses -= 1
        else:
            self.inventory.remove(item_id)

        result["success"] = True
        return result

    # ─── Regen (out of combat) ─────────────────────────────────────────────

    def regen_tick(self) -> None:
        res_lvl = self.skills.level(SkillType.RESISTANCE)
        regen = max(1, res_lvl // 10)
        self.heal(regen)

    # ─── Misc ──────────────────────────────────────────────────────────────

    def refresh_for_run(self) -> None:
        self._max_hp = self._calc_max_hp()
        self._hp = self._max_hp
        self.special_bar = 0
        self.turn_count = 0

    def __repr__(self) -> str:
        return (
            f"Player({self.name!r}, "
            f"HP={self._hp}/{self._max_hp}, "
            f"CB={self.skills.combat_level}, "
            f"style={self.active_style.value})"
        )
