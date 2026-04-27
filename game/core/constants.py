from enum import Enum, auto


class CombatStyle(Enum):
    MELEE = "melee"
    RANGE = "range"
    MAGIC = "magic"


class WeaknessType(Enum):
    WEAK = "weak"        # +50% damage received
    NEUTRAL = "neutral"  # normal damage
    RESISTANT = "resistant"  # -50% damage received
    IMMUNE = "immune"    # 0 damage (bosses only)


class BossPhase(Enum):
    PHASE_1 = 1  # 100–60% HP
    PHASE_2 = 2  # 60–30% HP
    PHASE_3 = 3  # 30–0% HP (ENRAGE)


class CombatAction(Enum):
    # Base actions (all builds)
    ATTACK = "attack"
    DEFEND = "defend"
    USE_ITEM = "use_item"
    FLEE = "flee"
    # Melee
    SPECIAL_STRIKE = "special_strike"
    TAUNT = "taunt"
    AREA_ATTACK = "area_attack"
    # Range
    CHARGED_SHOT = "charged_shot"
    RETREAT = "retreat"
    MULTI_SHOT = "multi_shot"
    # Magic
    SPELL = "spell"
    MAGIC_SHIELD = "magic_shield"
    DEBUFF = "debuff"


class StatusEffect(Enum):
    POISON = "poison"
    SLOW = "slow"
    STUN = "stun"
    BURNING = "burning"
    DEFENDING = "defending"
    RAGE = "rage"
    MAGIC_SHIELD = "magic_shield"
    CHARGED = "charged"  # range charge-up state


class SkillType(Enum):
    # Combat
    ATTACK = "attack"
    DEFENSE = "defense"
    STRENGTH = "strength"
    RESISTANCE = "resistance"
    RANGE = "range"
    MAGIC = "magic"
    # Gathering
    MINING = "mining"
    WOODCUTTING = "woodcutting"
    FISHING = "fishing"
    FARMING = "farming"
    # Production
    SMITHING = "smithing"
    COOKING = "cooking"
    HERBLORE = "herblore"
    RUNECRAFT = "runecraft"


class MaterialTier(Enum):
    BRONZE = "bronze"
    IRON = "iron"
    STEEL = "steel"
    MITHRIL = "mithril"
    ADAMANTITE = "adamantite"
    RUNE = "rune"
    LEGENDARY = "legendary"
    RAID = "raid"


TIER_LEVEL_REQUIREMENTS = {
    MaterialTier.BRONZE: 1,
    MaterialTier.IRON: 15,
    MaterialTier.STEEL: 25,
    MaterialTier.MITHRIL: 35,
    MaterialTier.ADAMANTITE: 50,
    MaterialTier.RUNE: 55,
    MaterialTier.LEGENDARY: 80,
    MaterialTier.RAID: 90,
}

# XP required per level (RuneScape-style curve)
XP_TABLE: dict[int, int] = {}
_xp = 0
for _lvl in range(1, 100):
    _xp += int(_lvl + 300 * (2 ** (_lvl / 7.0)))
    XP_TABLE[_lvl + 1] = _xp // 4

MAX_LEVEL = 99
SKILL_CAP = 99

WEAKNESS_MULTIPLIERS = {
    WeaknessType.WEAK: 1.5,
    WeaknessType.NEUTRAL: 1.0,
    WeaknessType.RESISTANT: 0.5,
    WeaknessType.IMMUNE: 0.0,
}

DEATH_DURABILITY_PENALTY = 0.15  # 15% extra durability loss on death
FLEE_BASE_CHANCE = 0.4           # 40% base flee chance
DEFEND_DAMAGE_REDUCTION = 0.5   # 50% damage reduction when defending
SPECIAL_STRIKE_COOLDOWN = 3      # turns
POISON_DAMAGE_PER_TURN = 0.05   # 5% of max HP
SLOW_SPEED_REDUCTION = 0.5      # 50% action speed reduction
