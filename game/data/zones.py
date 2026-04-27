"""
Zone definitions — each zone has unlock conditions, a tier, a skill challenge,
and references to its monsters and boss.

Unlock rules (from GDD):
  1. Boss of the previous zone must have been defeated.
  2. Player must meet the minimum combat level.
  Both conditions are required simultaneously.
"""
from dataclasses import dataclass, field
from core.constants import SkillType, MaterialTier


@dataclass
class ZoneUnlock:
    previous_boss_id: str | None   # None = starting zone, no boss required
    min_combat_level: int
    description: str = ""


@dataclass
class ZoneCurrency:
    id: str
    name: str
    symbol: str


@dataclass
class Zone:
    id: str
    name: str
    description: str
    tier: MaterialTier
    unlock: ZoneUnlock
    skill_challenge: SkillType        # skill tested in mandatory skill room
    currency: ZoneCurrency
    monster_ids: list[str]            # normal monsters (from data/monsters.py)
    elite_ids: list[str]
    rare_ids: list[str]
    boss_id: str
    recommended_combat_level: int
    ambient_loot_table: list[str]     # item_ids that can appear in loot/event rooms
    zone_color: str = "#888888"       # UI hint


ZONE_CURRENCIES = {
    "forest_token":  ZoneCurrency("forest_token",  "Forest Token",  "🍃"),
    "dungeon_shard": ZoneCurrency("dungeon_shard", "Dungeon Shard", "💎"),
    "swamp_muck":    ZoneCurrency("swamp_muck",    "Swamp Muck",    "🌿"),
    "desert_coin":   ZoneCurrency("desert_coin",   "Desert Coin",   "🌙"),
    "mountain_ore":  ZoneCurrency("mountain_ore",  "Mountain Ore",  "⛏"),
    "void_essence":  ZoneCurrency("void_essence",  "Void Essence",  "🔮"),
    "raid_emblem":   ZoneCurrency("raid_emblem",   "Raid Emblem",   "⚔"),
}

ZONES: dict[str, Zone] = {

    "forest": Zone(
        id="forest",
        name="Goblin Forest",
        description="Dense woodland teeming with goblins and wildlife. The starting zone.",
        tier=MaterialTier.BRONZE,
        unlock=ZoneUnlock(previous_boss_id=None, min_combat_level=1,
                          description="Starting zone — always unlocked."),
        skill_challenge=SkillType.WOODCUTTING,
        currency=ZONE_CURRENCIES["forest_token"],
        monster_ids=["goblin", "stone_goblin", "forest_boar"],
        elite_ids=["elite_goblin"],
        rare_ids=["rare_spider"],
        boss_id="goblin_king",
        recommended_combat_level=10,
        ambient_loot_table=["basic_potion", "cooked_trout", "bronze_sword",
                             "bronze_body", "anti_venom"],
        zone_color="#4a7c3f",
    ),

    "dungeon_1": Zone(
        id="dungeon_1",
        name="The Buried Vault",
        description="Ancient underground ruins. Skeletons and dark mages guard forgotten treasure.",
        tier=MaterialTier.IRON,
        unlock=ZoneUnlock(previous_boss_id="goblin_king", min_combat_level=15,
                          description="Defeat Goblin King Gruk and reach Combat Level 15."),
        skill_challenge=SkillType.MINING,
        currency=ZONE_CURRENCIES["dungeon_shard"],
        monster_ids=["skeleton_archer", "dark_mage"],
        elite_ids=[],
        rare_ids=[],
        boss_id="goblin_king",   # placeholder — would be a dungeon boss in full game
        recommended_combat_level=20,
        ambient_loot_table=["iron_sword", "basic_potion", "strength_potion",
                             "iron_body", "wood_bow"],
        zone_color="#5a4a3a",
    ),

    "swamp": Zone(
        id="swamp",
        name="Venomous Swamp",
        description="A toxic marshland. Poison is everywhere — bring anti-venoms.",
        tier=MaterialTier.STEEL,
        unlock=ZoneUnlock(previous_boss_id="goblin_king", min_combat_level=25,
                          description="Defeat Goblin King Gruk and reach Combat Level 25."),
        skill_challenge=SkillType.HERBLORE,
        currency=ZONE_CURRENCIES["swamp_muck"],
        monster_ids=["goblin", "forest_boar"],   # reuse; full roster TBD
        elite_ids=["elite_goblin"],
        rare_ids=["rare_spider"],
        boss_id="goblin_king",
        recommended_combat_level=30,
        ambient_loot_table=["steel_sword", "anti_venom", "super_potion",
                             "steel_body", "maple_bow"],
        zone_color="#3a5a3a",
    ),

    "desert": Zone(
        id="desert",
        name="Scorched Desert",
        description="A brutal wasteland. Heat and sand golems challenge every step.",
        tier=MaterialTier.MITHRIL,
        unlock=ZoneUnlock(previous_boss_id="goblin_king", min_combat_level=35,
                          description="Defeat the Swamp Boss and reach Combat Level 35."),
        skill_challenge=SkillType.FISHING,
        currency=ZONE_CURRENCIES["desert_coin"],
        monster_ids=["stone_goblin", "dark_mage"],
        elite_ids=["elite_goblin"],
        rare_ids=[],
        boss_id="goblin_king",
        recommended_combat_level=45,
        ambient_loot_table=["mithril_sword", "defense_potion", "super_potion",
                             "mithril_body", "mithril_staff"],
        zone_color="#c8a050",
    ),

    "mountain": Zone(
        id="mountain",
        name="Iron Peak",
        description="Treacherous mountain passes guarded by elite warriors and stone beasts.",
        tier=MaterialTier.ADAMANTITE,
        unlock=ZoneUnlock(previous_boss_id="goblin_king", min_combat_level=50,
                          description="Defeat the Desert Boss and reach Combat Level 50."),
        skill_challenge=SkillType.SMITHING,
        currency=ZONE_CURRENCIES["mountain_ore"],
        monster_ids=["skeleton_archer", "stone_goblin"],
        elite_ids=["elite_goblin"],
        rare_ids=["rare_spider"],
        boss_id="goblin_king",
        recommended_combat_level=60,
        ambient_loot_table=["adamantite_sword", "overload", "super_potion",
                             "adamantite_body", "maple_bow"],
        zone_color="#6a7a8a",
    ),

    "void": Zone(
        id="void",
        name="The Void Rift",
        description="A tear in reality. Rune-tier gear is the minimum to survive.",
        tier=MaterialTier.RUNE,
        unlock=ZoneUnlock(previous_boss_id="goblin_king", min_combat_level=60,
                          description="Defeat the Mountain Boss and reach Combat Level 60."),
        skill_challenge=SkillType.RUNECRAFT,
        currency=ZONE_CURRENCIES["void_essence"],
        monster_ids=["dark_mage", "skeleton_archer"],
        elite_ids=["elite_goblin"],
        rare_ids=["rare_spider"],
        boss_id="goblin_king",
        recommended_combat_level=70,
        ambient_loot_table=["rune_sword", "overload", "rune_body",
                             "rune_staff", "magic_bow"],
        zone_color="#4a3a6a",
    ),

    "raid": Zone(
        id="raid",
        name="Eternal Raid",
        description="The ultimate challenge. Face Grondar, Sylvara, and Zythera.",
        tier=MaterialTier.RAID,
        unlock=ZoneUnlock(previous_boss_id="goblin_king", min_combat_level=85,
                          description="Defeat the Void Boss and reach Combat Level 85."),
        skill_challenge=SkillType.RUNECRAFT,
        currency=ZONE_CURRENCIES["raid_emblem"],
        monster_ids=["dark_mage", "skeleton_archer"],
        elite_ids=["elite_goblin"],
        rare_ids=["rare_spider"],
        boss_id="grondar",
        recommended_combat_level=90,
        ambient_loot_table=["rune_body", "rune_staff", "magic_bow", "overload"],
        zone_color="#8a1a1a",
    ),
}

# Ordered zone progression
ZONE_ORDER: list[str] = [
    "forest", "dungeon_1", "swamp", "desert", "mountain", "void", "raid"
]


def get_next_zone(current_zone_id: str) -> str | None:
    try:
        idx = ZONE_ORDER.index(current_zone_id)
        return ZONE_ORDER[idx + 1] if idx + 1 < len(ZONE_ORDER) else None
    except ValueError:
        return None


def get_zone(zone_id: str) -> Zone | None:
    return ZONES.get(zone_id)
