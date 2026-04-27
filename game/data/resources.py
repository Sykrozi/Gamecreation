from dataclasses import dataclass, field
from core.constants import SkillType, MaterialTier


@dataclass
class Resource:
    id: str
    name: str
    skill: SkillType
    level_req: int
    xp_reward: int
    tier: MaterialTier
    respawn_ticks: int = 3      # ticks until node refills
    quantity_min: int = 1
    quantity_max: int = 1
    zone: str = "any"


@dataclass
class OreNode(Resource):
    ore_hardness: int = 1       # affects sweet-spot timing window


@dataclass
class TreeNode(Resource):
    tree_hp: int = 3            # chops before tree falls


@dataclass
class FishSpot(Resource):
    bait_required: bool = False
    storm_only: bool = False    # unlocked at high Fishing level


@dataclass
class FarmingPatch(Resource):
    grow_ticks: int = 5         # ticks from plant to harvest
    seed_id: str = ""           # seed item needed to plant


# ─── Mining ──────────────────────────────────────────────────────────────────

ORES: dict[str, OreNode] = {
    "copper": OreNode(
        id="copper", name="Copper Rock", skill=SkillType.MINING,
        level_req=1, xp_reward=17, tier=MaterialTier.BRONZE,
        respawn_ticks=2, ore_hardness=1,
    ),
    "tin": OreNode(
        id="tin", name="Tin Rock", skill=SkillType.MINING,
        level_req=1, xp_reward=17, tier=MaterialTier.BRONZE,
        respawn_ticks=2, ore_hardness=1,
    ),
    "iron": OreNode(
        id="iron", name="Iron Rock", skill=SkillType.MINING,
        level_req=15, xp_reward=35, tier=MaterialTier.IRON,
        respawn_ticks=3, ore_hardness=2,
    ),
    "coal": OreNode(
        id="coal", name="Coal Rock", skill=SkillType.MINING,
        level_req=20, xp_reward=50, tier=MaterialTier.IRON,
        respawn_ticks=4, ore_hardness=2,
    ),
    "mithril": OreNode(
        id="mithril", name="Mithril Rock", skill=SkillType.MINING,
        level_req=35, xp_reward=80, tier=MaterialTier.MITHRIL,
        respawn_ticks=5, ore_hardness=3,
    ),
    "adamantite": OreNode(
        id="adamantite", name="Adamantite Rock", skill=SkillType.MINING,
        level_req=50, xp_reward=120, tier=MaterialTier.ADAMANTITE,
        respawn_ticks=6, ore_hardness=4,
    ),
    "runite": OreNode(
        id="runite", name="Runite Rock", skill=SkillType.MINING,
        level_req=55, xp_reward=175, tier=MaterialTier.RUNE,
        respawn_ticks=8, ore_hardness=5,
    ),
    "enchanted_ore": OreNode(
        id="enchanted_ore", name="Enchanted Ore", skill=SkillType.MINING,
        level_req=60, xp_reward=250, tier=MaterialTier.RUNE,
        respawn_ticks=10, ore_hardness=5,
    ),
    "legendary_ore": OreNode(
        id="legendary_ore", name="Legendary Ore", skill=SkillType.MINING,
        level_req=90, xp_reward=500, tier=MaterialTier.LEGENDARY,
        respawn_ticks=15, ore_hardness=6,
    ),
}

# ─── Woodcutting ─────────────────────────────────────────────────────────────

TREES: dict[str, TreeNode] = {
    "pine": TreeNode(
        id="pine", name="Pine Tree", skill=SkillType.WOODCUTTING,
        level_req=1, xp_reward=25, tier=MaterialTier.BRONZE,
        respawn_ticks=3, tree_hp=2,
    ),
    "oak": TreeNode(
        id="oak", name="Oak Tree", skill=SkillType.WOODCUTTING,
        level_req=1, xp_reward=37, tier=MaterialTier.BRONZE,
        respawn_ticks=3, tree_hp=3,
    ),
    "willow": TreeNode(
        id="willow", name="Willow Tree", skill=SkillType.WOODCUTTING,
        level_req=20, xp_reward=67, tier=MaterialTier.IRON,
        respawn_ticks=4, tree_hp=3,
    ),
    "maple": TreeNode(
        id="maple", name="Maple Tree", skill=SkillType.WOODCUTTING,
        level_req=30, xp_reward=100, tier=MaterialTier.STEEL,
        respawn_ticks=5, tree_hp=4,
    ),
    "yew": TreeNode(
        id="yew", name="Yew Tree", skill=SkillType.WOODCUTTING,
        level_req=60, xp_reward=175, tier=MaterialTier.ADAMANTITE,
        respawn_ticks=6, tree_hp=5,
    ),
    "magic_tree": TreeNode(
        id="magic_tree", name="Magic Tree", skill=SkillType.WOODCUTTING,
        level_req=60, xp_reward=250, tier=MaterialTier.RUNE,
        respawn_ticks=8, tree_hp=6,
    ),
    "enchanted_wood": TreeNode(
        id="enchanted_wood", name="Enchanted Tree", skill=SkillType.WOODCUTTING,
        level_req=70, xp_reward=350, tier=MaterialTier.RUNE,
        respawn_ticks=10, tree_hp=6,
    ),
    "legendary_tree": TreeNode(
        id="legendary_tree", name="Legendary Tree", skill=SkillType.WOODCUTTING,
        level_req=90, xp_reward=600, tier=MaterialTier.LEGENDARY,
        respawn_ticks=15, tree_hp=8,
    ),
}

# ─── Fishing ─────────────────────────────────────────────────────────────────

FISH_SPOTS: dict[str, FishSpot] = {
    "sardine": FishSpot(
        id="sardine", name="Sardine", skill=SkillType.FISHING,
        level_req=1, xp_reward=20, tier=MaterialTier.BRONZE,
        respawn_ticks=2,
    ),
    "trout": FishSpot(
        id="trout", name="Trout", skill=SkillType.FISHING,
        level_req=1, xp_reward=50, tier=MaterialTier.BRONZE,
        respawn_ticks=3,
    ),
    "salmon": FishSpot(
        id="salmon", name="Salmon", skill=SkillType.FISHING,
        level_req=20, xp_reward=70, tier=MaterialTier.IRON,
        respawn_ticks=3,
    ),
    "tuna": FishSpot(
        id="tuna", name="Tuna", skill=SkillType.FISHING,
        level_req=20, xp_reward=80, tier=MaterialTier.IRON,
        respawn_ticks=4, bait_required=True,
    ),
    "swordfish": FishSpot(
        id="swordfish", name="Swordfish", skill=SkillType.FISHING,
        level_req=50, xp_reward=100, tier=MaterialTier.STEEL,
        respawn_ticks=5, bait_required=True,
    ),
    "squid": FishSpot(
        id="squid", name="Squid", skill=SkillType.FISHING,
        level_req=50, xp_reward=115, tier=MaterialTier.STEEL,
        respawn_ticks=5,
    ),
    "abyssal_fish": FishSpot(
        id="abyssal_fish", name="Abyssal Fish", skill=SkillType.FISHING,
        level_req=70, xp_reward=200, tier=MaterialTier.RUNE,
        respawn_ticks=8, bait_required=True,
    ),
    "legendary_fish": FishSpot(
        id="legendary_fish", name="Legendary Fish", skill=SkillType.FISHING,
        level_req=80, xp_reward=400, tier=MaterialTier.LEGENDARY,
        respawn_ticks=12, storm_only=True,
    ),
}

# ─── Farming ─────────────────────────────────────────────────────────────────

FARMING_PATCHES: dict[str, FarmingPatch] = {
    "guam_herb": FarmingPatch(
        id="guam_herb", name="Guam Herb", skill=SkillType.FARMING,
        level_req=1, xp_reward=11, tier=MaterialTier.BRONZE,
        grow_ticks=4, seed_id="guam_seed",
    ),
    "marrentill": FarmingPatch(
        id="marrentill", name="Marrentill Herb", skill=SkillType.FARMING,
        level_req=5, xp_reward=14, tier=MaterialTier.BRONZE,
        grow_ticks=5, seed_id="marrentill_seed",
    ),
    "tarromin": FarmingPatch(
        id="tarromin", name="Tarromin Herb", skill=SkillType.FARMING,
        level_req=15, xp_reward=18, tier=MaterialTier.IRON,
        grow_ticks=5, seed_id="tarromin_seed",
    ),
    "irit": FarmingPatch(
        id="irit", name="Irit Herb", skill=SkillType.FARMING,
        level_req=25, xp_reward=24, tier=MaterialTier.STEEL,
        grow_ticks=6, seed_id="irit_seed",
    ),
    "kwuarm": FarmingPatch(
        id="kwuarm", name="Kwuarm Herb", skill=SkillType.FARMING,
        level_req=40, xp_reward=31, tier=MaterialTier.MITHRIL,
        grow_ticks=7, seed_id="kwuarm_seed",
    ),
    "torstol": FarmingPatch(
        id="torstol", name="Torstol Herb", skill=SkillType.FARMING,
        level_req=60, xp_reward=68, tier=MaterialTier.RUNE,
        grow_ticks=10, seed_id="torstol_seed",
    ),
    "legendary_plant": FarmingPatch(
        id="legendary_plant", name="Legendary Plant", skill=SkillType.FARMING,
        level_req=70, xp_reward=200, tier=MaterialTier.LEGENDARY,
        grow_ticks=20, seed_id="legendary_seed",
    ),
}

# ─── Lookup helpers ────────────────────────────────────────────────────────────

ALL_RESOURCES: dict[str, Resource] = {
    **ORES, **TREES, **FISH_SPOTS, **FARMING_PATCHES,
}


def get_resources_for_skill(skill: SkillType) -> list[Resource]:
    return [r for r in ALL_RESOURCES.values() if r.skill == skill]


def get_available_resources(skill: SkillType, level: int) -> list[Resource]:
    return [r for r in get_resources_for_skill(skill) if r.level_req <= level]
