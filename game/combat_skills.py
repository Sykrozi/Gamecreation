from dataclasses import dataclass, field

_XP_TABLE = [
    0, 0, 50, 120, 220, 350, 520, 740, 1020, 1370, 1800,
    2320, 2940, 3670, 4520, 5500, 6620, 7890, 9310, 10890, 12640,
]
MAX_SKILL_LEVEL = 99


def _xp_for_level(lvl: int) -> int:
    if lvl <= 1:
        return 0
    if lvl < len(_XP_TABLE):
        return _XP_TABLE[lvl]
    return int(12640 * (1.12 ** (lvl - 20)))


# Public XP utilities used by gathering_skills
XP_TABLE = [_xp_for_level(i) for i in range(100)]

def level_for_xp(xp: int) -> int:
    """Return the level that corresponds to total accumulated XP."""
    level = 1
    for lv in range(2, MAX_SKILL_LEVEL + 1):
        if xp >= _xp_for_level(lv):
            level = lv
        else:
            break
    return level

def xp_to_next_level(xp: int) -> int:
    """Return XP still needed to reach the next level."""
    lvl = level_for_xp(xp)
    if lvl >= MAX_SKILL_LEVEL:
        return 0
    return _xp_for_level(lvl + 1) - xp


@dataclass
class Ability:
    name: str
    description: str
    cooldown_max: int
    action: str


@dataclass
class CombatSkill:
    name: str
    xp: int = 0
    level: int = 1

    def add_xp(self, amount: int) -> bool:
        self.xp += amount
        leveled = False
        while self.level < MAX_SKILL_LEVEL:
            if self.xp >= _xp_for_level(self.level + 1):
                self.level += 1
                leveled = True
            else:
                break
        return leveled

    def xp_to_next(self) -> int:
        if self.level >= MAX_SKILL_LEVEL:
            return 0
        return max(0, _xp_for_level(self.level + 1) - self.xp)

    def xp_progress(self) -> float:
        if self.level >= MAX_SKILL_LEVEL:
            return 1.0
        cur = _xp_for_level(self.level)
        nxt = _xp_for_level(self.level + 1)
        span = nxt - cur
        return max(0.0, min(1.0, (self.xp - cur) / span)) if span else 0.0


_ATTACK_ABILITIES: list[tuple[int, Ability]] = [
    (5,  Ability("Heavy Strike", "150% damage",              3, "heavy_strike")),
    (15, Ability("Flurry",       "Two hits at 75% each",     4, "flurry")),
    (30, Ability("Cleave",       "120% damage",              5, "cleave")),
]

_DEFENSE_ABILITIES: list[tuple[int, Ability]] = [
    (5,  Ability("Iron Skin",    "Next hit reduced by 60%",  4, "iron_skin")),
    (15, Ability("Retaliate",    "Defend + counter-attack",  5, "retaliate")),
]

_STRENGTH_ABILITIES: list[tuple[int, Ability]] = [
    (5,  Ability("Power Strike", "130% dmg, ignore 40% DEF", 3, "power_strike")),
    (15, Ability("Berserk",      "+50% ATK for 3 turns",     6, "berserk")),
]

_ALL_DEFS = _ATTACK_ABILITIES + _DEFENSE_ABILITIES + _STRENGTH_ABILITIES


class PlayerCombatSkills:
    def __init__(self):
        self.attack   = CombatSkill("Attack")
        self.defense  = CombatSkill("Defense")
        self.strength = CombatSkill("Strength")
        self._cooldowns: dict[str, int] = {}
        self._berserk_turns: int = 0
        self._iron_skin_active: bool = False

    # ── XP ───────────────────────────────────────────────────────────────────

    def grant_action_xp(self, action: str = "attack") -> list[str]:
        table: dict[str, dict[str, int]] = {
            "attack":       {"attack": 8,  "strength": 3},
            "take_damage":  {"defense": 6},
            "defend":       {"defense": 10},
            "heavy_strike": {"attack": 12, "strength": 2},
            "flurry":       {"attack": 14},
            "cleave":       {"attack": 10, "strength": 4},
            "power_strike": {"strength": 12, "attack": 3},
            "berserk":      {"strength": 8},
            "iron_skin":    {"defense": 12},
            "retaliate":    {"defense": 10, "attack": 4},
        }
        leveled: list[str] = []
        for skill_name, amount in table.get(action, {"attack": 8}).items():
            skill: CombatSkill | None = getattr(self, skill_name, None)
            if skill and skill.add_xp(amount):
                leveled.append(skill.name)
        return leveled

    # ── Cooldowns ────────────────────────────────────────────────────────────

    def tick_all_cooldowns(self):
        for k in list(self._cooldowns):
            if self._cooldowns[k] > 0:
                self._cooldowns[k] -= 1
        if self._berserk_turns > 0:
            self._berserk_turns -= 1

    def ability_ready(self, action: str) -> bool:
        return self._cooldowns.get(action, 0) == 0

    def use_ability(self, action: str):
        ab = next((a for _, a in _ALL_DEFS if a.action == action), None)
        if ab:
            self._cooldowns[action] = ab.cooldown_max
        if action == "berserk":
            self._berserk_turns = 3
        if action == "iron_skin":
            self._iron_skin_active = True

    def get_cooldown(self, action: str) -> int:
        return self._cooldowns.get(action, 0)

    def consume_iron_skin(self):
        self._iron_skin_active = False

    # ── Unlocked abilities ───────────────────────────────────────────────────

    def unlocked_abilities(self) -> list[Ability]:
        result: list[Ability] = []
        for req, ab in _ATTACK_ABILITIES:
            if self.attack.level >= req:
                result.append(ab)
        for req, ab in _DEFENSE_ABILITIES:
            if self.defense.level >= req:
                result.append(ab)
        for req, ab in _STRENGTH_ABILITIES:
            if self.strength.level >= req:
                result.append(ab)
        return result

    def skill_ability_defs(self):
        return [
            (self.attack,   "Attack",   _ATTACK_ABILITIES),
            (self.defense,  "Defense",  _DEFENSE_ABILITIES),
            (self.strength, "Strength", _STRENGTH_ABILITIES),
        ]

    # ── Stat bonuses ─────────────────────────────────────────────────────────

    @property
    def attack_bonus(self) -> int:
        return (self.attack.level - 1) // 3

    @property
    def defense_bonus(self) -> int:
        return (self.defense.level - 1) // 4

    @property
    def max_hp_bonus(self) -> int:
        return (self.strength.level - 1) * 3

    @property
    def berserk_active(self) -> bool:
        return self._berserk_turns > 0

    @property
    def iron_skin_active(self) -> bool:
        return self._iron_skin_active

    @property
    def berserk_turns_left(self) -> int:
        return self._berserk_turns
