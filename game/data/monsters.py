from dataclasses import dataclass, field
from core.constants import CombatStyle, WeaknessType


@dataclass
class Drop:
    item_id: str
    chance: float       # 0.0–1.0
    quantity_min: int = 1
    quantity_max: int = 1


@dataclass
class MonsterWeakness:
    style: CombatStyle
    weakness: WeaknessType


@dataclass
class MonsterDefinition:
    id: str
    name: str
    zone: str
    level: int
    hp: int
    attack: int
    defense: int
    combat_style: CombatStyle
    xp_reward: int
    weaknesses: list[MonsterWeakness] = field(default_factory=list)
    drops: list[Drop] = field(default_factory=list)
    is_boss: bool = False
    is_elite: bool = False
    is_rare: bool = False
    lore: str = ""


@dataclass
class BossPhaseData:
    phase: int             # 1, 2, 3
    hp_threshold: float    # fraction (e.g. 0.6 means phase triggers at 60% HP)
    new_attacks: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class BossDefinition(MonsterDefinition):
    phases: list[BossPhaseData] = field(default_factory=list)
    immune_to: list[CombatStyle] = field(default_factory=list)


# ─── Zone 1: Forest / Early ──────────────────────────────────────────────────

MONSTERS: dict[str, MonsterDefinition] = {

    "goblin": MonsterDefinition(
        id="goblin", name="Goblin", zone="forest", level=2,
        hp=30, attack=4, defense=2, combat_style=CombatStyle.MELEE,
        xp_reward=15,
        weaknesses=[
            MonsterWeakness(CombatStyle.RANGE, WeaknessType.WEAK),
            MonsterWeakness(CombatStyle.MELEE, WeaknessType.NEUTRAL),
            MonsterWeakness(CombatStyle.MAGIC, WeaknessType.RESISTANT),
        ],
        drops=[
            Drop("bronze_sword", 0.05), Drop("basic_potion", 0.2),
            Drop("cooked_trout", 0.4),
        ],
        lore="Cunning but cowardly. Vulnerable to arrows.",
    ),

    "stone_goblin": MonsterDefinition(
        id="stone_goblin", name="Stone Goblin", zone="forest", level=5,
        hp=50, attack=6, defense=8, combat_style=CombatStyle.MELEE,
        xp_reward=30,
        weaknesses=[
            MonsterWeakness(CombatStyle.MAGIC, WeaknessType.WEAK),
            MonsterWeakness(CombatStyle.RANGE, WeaknessType.NEUTRAL),
            MonsterWeakness(CombatStyle.MELEE, WeaknessType.RESISTANT),
        ],
        drops=[
            Drop("iron_sword", 0.03), Drop("basic_potion", 0.3),
        ],
        lore="Encrusted in stone. Magic cuts right through.",
    ),

    "forest_boar": MonsterDefinition(
        id="forest_boar", name="Forest Boar", zone="forest", level=4,
        hp=60, attack=8, defense=4, combat_style=CombatStyle.MELEE,
        xp_reward=25,
        weaknesses=[
            MonsterWeakness(CombatStyle.MELEE, WeaknessType.NEUTRAL),
            MonsterWeakness(CombatStyle.RANGE, WeaknessType.NEUTRAL),
            MonsterWeakness(CombatStyle.MAGIC, WeaknessType.NEUTRAL),
        ],
        drops=[Drop("cooked_trout", 0.6)],
        lore="A large boar with no particular weakness.",
    ),

    "skeleton_archer": MonsterDefinition(
        id="skeleton_archer", name="Skeleton Archer", zone="dungeon_1", level=8,
        hp=45, attack=10, defense=3, combat_style=CombatStyle.RANGE,
        xp_reward=40,
        weaknesses=[
            MonsterWeakness(CombatStyle.MELEE, WeaknessType.WEAK),
            MonsterWeakness(CombatStyle.RANGE, WeaknessType.NEUTRAL),
            MonsterWeakness(CombatStyle.MAGIC, WeaknessType.NEUTRAL),
        ],
        drops=[
            Drop("wood_bow", 0.04), Drop("anti_venom", 0.15),
        ],
        lore="Undead ranger — close the gap and destroy it.",
    ),

    "dark_mage": MonsterDefinition(
        id="dark_mage", name="Dark Mage", zone="dungeon_1", level=10,
        hp=40, attack=12, defense=2, combat_style=CombatStyle.MAGIC,
        xp_reward=50,
        weaknesses=[
            MonsterWeakness(CombatStyle.RANGE, WeaknessType.WEAK),
            MonsterWeakness(CombatStyle.MELEE, WeaknessType.NEUTRAL),
            MonsterWeakness(CombatStyle.MAGIC, WeaknessType.RESISTANT),
        ],
        drops=[
            Drop("basic_staff", 0.05), Drop("basic_potion", 0.25),
        ],
        lore="A sorcerer corrupted by dark power. Pierce with arrows.",
    ),

    # Elite variants
    "elite_goblin": MonsterDefinition(
        id="elite_goblin", name="Elite Goblin Warchief", zone="forest", level=8,
        hp=90, attack=12, defense=6, combat_style=CombatStyle.MELEE,
        xp_reward=80, is_elite=True,
        weaknesses=[
            MonsterWeakness(CombatStyle.RANGE, WeaknessType.WEAK),
            MonsterWeakness(CombatStyle.MELEE, WeaknessType.NEUTRAL),
            MonsterWeakness(CombatStyle.MAGIC, WeaknessType.RESISTANT),
        ],
        drops=[
            Drop("iron_sword", 0.15), Drop("strength_potion", 0.25),
        ],
    ),

    # Rare variant
    "rare_spider": MonsterDefinition(
        id="rare_spider", name="Venom Tarantula (Rare)", zone="forest", level=12,
        hp=70, attack=15, defense=5, combat_style=CombatStyle.MELEE,
        xp_reward=120, is_rare=True,
        weaknesses=[
            MonsterWeakness(CombatStyle.MAGIC, WeaknessType.WEAK),
            MonsterWeakness(CombatStyle.RANGE, WeaknessType.NEUTRAL),
            MonsterWeakness(CombatStyle.MELEE, WeaknessType.NEUTRAL),
        ],
        drops=[
            Drop("anti_venom", 0.5), Drop("mithril_sword", 0.02),
        ],
        lore="Massive venomous spider. Rare encounter.",
    ),
}

# ─── Bosses ───────────────────────────────────────────────────────────────────

BOSSES: dict[str, BossDefinition] = {

    "goblin_king": BossDefinition(
        id="goblin_king", name="Goblin King Gruk", zone="forest", level=15,
        hp=300, attack=18, defense=10, combat_style=CombatStyle.MELEE,
        xp_reward=500, is_boss=True,
        weaknesses=[
            MonsterWeakness(CombatStyle.RANGE, WeaknessType.WEAK),
            MonsterWeakness(CombatStyle.MAGIC, WeaknessType.NEUTRAL),
            MonsterWeakness(CombatStyle.MELEE, WeaknessType.RESISTANT),
        ],
        drops=[
            Drop("iron_sword", 0.3), Drop("strength_potion", 0.5),
            Drop("bronze_body", 0.4),
        ],
        lore="King of the forest goblins. Unlock next zone by defeating him.",
        phases=[
            BossPhaseData(
                phase=1, hp_threshold=1.0,
                description="Normal attacks, taunts player",
                new_attacks=["melee_strike", "taunt"],
            ),
            BossPhaseData(
                phase=2, hp_threshold=0.6,
                description="Summons goblin minions, power strike",
                new_attacks=["summon_goblins", "power_strike"],
            ),
            BossPhaseData(
                phase=3, hp_threshold=0.3,
                description="ENRAGE — berserk mode, devastating strike",
                new_attacks=["berserk_strike", "battle_cry"],
            ),
        ],
    ),

    "grondar": BossDefinition(
        id="grondar", name="Grondar the Unyielding", zone="raid", level=85,
        hp=5000, attack=80, defense=60, combat_style=CombatStyle.MELEE,
        xp_reward=10000, is_boss=True,
        weaknesses=[
            MonsterWeakness(CombatStyle.MAGIC, WeaknessType.WEAK),
            MonsterWeakness(CombatStyle.RANGE, WeaknessType.NEUTRAL),
            MonsterWeakness(CombatStyle.MELEE, WeaknessType.RESISTANT),
        ],
        immune_to=[],
        drops=[
            Drop("rune_body", 0.4), Drop("overload", 0.6),
        ],
        lore="Ancient colossus guarding the vault of eternity.",
        phases=[
            BossPhaseData(
                phase=1, hp_threshold=1.0,
                description="Stomp attacks and ground shatter",
                new_attacks=["stomp", "ground_shatter"],
            ),
            BossPhaseData(
                phase=2, hp_threshold=0.6,
                description="Awakens second pair of arms, dual strike",
                new_attacks=["dual_strike", "seismic_slam"],
            ),
            BossPhaseData(
                phase=3, hp_threshold=0.3,
                description="ENRAGE — Apocalyptic Fury, unavoidable AoE",
                new_attacks=["apocalyptic_fury", "colossus_roar"],
            ),
        ],
    ),

    "sylvara": BossDefinition(
        id="sylvara", name="Sylvara the Forsaken", zone="raid", level=87,
        hp=4500, attack=90, defense=45, combat_style=CombatStyle.MAGIC,
        xp_reward=10000, is_boss=True,
        weaknesses=[
            MonsterWeakness(CombatStyle.RANGE, WeaknessType.WEAK),
            MonsterWeakness(CombatStyle.MELEE, WeaknessType.NEUTRAL),
            MonsterWeakness(CombatStyle.MAGIC, WeaknessType.IMMUNE),
        ],
        immune_to=[CombatStyle.MAGIC],
        drops=[
            Drop("rune_staff", 0.3), Drop("overload", 0.6),
        ],
        lore="A corrupted archmage. Magic cannot harm her.",
        phases=[
            BossPhaseData(
                phase=1, hp_threshold=1.0,
                description="Arcane bolts, mana drain",
                new_attacks=["arcane_bolt", "mana_drain"],
            ),
            BossPhaseData(
                phase=2, hp_threshold=0.6,
                description="Summons arcane shields, void rift",
                new_attacks=["arcane_shield", "void_rift"],
            ),
            BossPhaseData(
                phase=3, hp_threshold=0.3,
                description="ENRAGE — Starfall, infinite mana",
                new_attacks=["starfall", "arcane_overload"],
            ),
        ],
    ),

    "zythera": BossDefinition(
        id="zythera", name="Zythera the Unseen", zone="raid", level=90,
        hp=6000, attack=100, defense=50, combat_style=CombatStyle.RANGE,
        xp_reward=15000, is_boss=True,
        weaknesses=[
            MonsterWeakness(CombatStyle.MELEE, WeaknessType.WEAK),
            MonsterWeakness(CombatStyle.MAGIC, WeaknessType.NEUTRAL),
            MonsterWeakness(CombatStyle.RANGE, WeaknessType.RESISTANT),
        ],
        drops=[
            Drop("magic_bow", 0.3), Drop("overload", 0.7),
        ],
        lore="Ghost assassin, master of shadows.",
        phases=[
            BossPhaseData(
                phase=1, hp_threshold=1.0,
                description="Shadow strikes, vanish",
                new_attacks=["shadow_strike", "vanish"],
            ),
            BossPhaseData(
                phase=2, hp_threshold=0.6,
                description="Clone illusions, venom barrage",
                new_attacks=["clone_illusion", "venom_barrage"],
            ),
            BossPhaseData(
                phase=3, hp_threshold=0.3,
                description="ENRAGE — Death Mark, instant-kill threshold",
                new_attacks=["death_mark", "shadow_apocalypse"],
            ),
        ],
    ),
}


def get_monsters_by_zone(zone: str) -> list[MonsterDefinition]:
    return [m for m in MONSTERS.values() if m.zone == zone]


def get_boss_for_zone(zone: str) -> BossDefinition | None:
    return next((b for b in BOSSES.values() if b.zone == zone), None)
