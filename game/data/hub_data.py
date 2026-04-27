from dataclasses import dataclass, field
from core.constants import SkillType


@dataclass
class HubBuilding:
    id: str
    name: str
    description: str
    skill: SkillType                    # skill it automates
    skill_level_req: int                # must reach this level to build
    build_cost: dict[str, int]          # {item_id: quantity}
    upgrade_levels: int = 3             # how many times it can be upgraded
    idle_xp_per_tick: int = 5           # XP granted per idle tick at base level
    idle_resource_per_tick: int = 1     # resources gathered per idle tick
    unlock_message: str = ""


HUB_BUILDINGS: dict[str, HubBuilding] = {
    "mine_shaft": HubBuilding(
        id="mine_shaft",
        name="Mine Shaft",
        description="Automated mine that extracts ore while you dungeon.",
        skill=SkillType.MINING,
        skill_level_req=50,
        build_cost={"iron": 50, "coal": 30},
        idle_xp_per_tick=8,
        idle_resource_per_tick=1,
        unlock_message="The mine shaft hums with activity.",
    ),
    "lumber_mill": HubBuilding(
        id="lumber_mill",
        name="Lumber Mill",
        description="Chops logs automatically once built.",
        skill=SkillType.WOODCUTTING,
        skill_level_req=50,
        build_cost={"oak": 60, "willow": 20},
        idle_xp_per_tick=7,
        idle_resource_per_tick=1,
        unlock_message="The mill blades spin steadily.",
    ),
    "fishing_dock": HubBuilding(
        id="fishing_dock",
        name="Fishing Dock",
        description="Sends out fishing boats that return with catches.",
        skill=SkillType.FISHING,
        skill_level_req=50,
        build_cost={"oak": 40, "iron": 20},
        idle_xp_per_tick=6,
        idle_resource_per_tick=1,
        unlock_message="Boats set sail on the horizon.",
    ),
    "greenhouse": HubBuilding(
        id="greenhouse",
        name="Greenhouse",
        description="Grows herbs and crops without tending.",
        skill=SkillType.FARMING,
        skill_level_req=50,
        build_cost={"oak": 30, "iron": 10},
        idle_xp_per_tick=5,
        idle_resource_per_tick=1,
        unlock_message="The greenhouse blooms with life.",
    ),
    "forge": HubBuilding(
        id="forge",
        name="Forge",
        description="Smelts and smiths items while idle.",
        skill=SkillType.SMITHING,
        skill_level_req=50,
        build_cost={"iron": 60, "coal": 40},
        idle_xp_per_tick=10,
        idle_resource_per_tick=1,
        unlock_message="The forge burns day and night.",
    ),
    "kitchen": HubBuilding(
        id="kitchen",
        name="Kitchen",
        description="Cooks food automatically from stored ingredients.",
        skill=SkillType.COOKING,
        skill_level_req=50,
        build_cost={"oak": 20, "iron": 10},
        idle_xp_per_tick=6,
        idle_resource_per_tick=1,
        unlock_message="The smell of cooking fills the hub.",
    ),
    "herb_lab": HubBuilding(
        id="herb_lab",
        name="Herb Laboratory",
        description="Brews potions from stored herbs automatically.",
        skill=SkillType.HERBLORE,
        skill_level_req=50,
        build_cost={"guam_herb": 30, "oak": 10},
        idle_xp_per_tick=7,
        idle_resource_per_tick=1,
        unlock_message="Bubbling flasks line the shelves.",
    ),
    "rune_altar": HubBuilding(
        id="rune_altar",
        name="Rune Altar",
        description="Crafts runes from stored essence automatically.",
        skill=SkillType.RUNECRAFT,
        skill_level_req=50,
        build_cost={"enchanted_ore": 10, "mithril": 20},
        idle_xp_per_tick=8,
        idle_resource_per_tick=1,
        unlock_message="The altar pulses with arcane energy.",
    ),
}

# Hub upgrade tiers — each tier multiplies idle output
HUB_UPGRADE_MULTIPLIERS: list[float] = [1.0, 1.5, 2.0, 3.0]  # index = upgrade level

# Hub phases (from GDD)
HUB_PHASES: dict[str, dict] = {
    "early": {
        "name": "Camp",
        "description": "A basic camp with essential structures.",
        "combat_level_req": 1,
        "buildings_req": 0,
    },
    "mid": {
        "name": "Outpost",
        "description": "A proper outpost with workshops.",
        "combat_level_req": 30,
        "buildings_req": 2,
    },
    "late": {
        "name": "Settlement",
        "description": "A growing settlement with specialists.",
        "combat_level_req": 60,
        "buildings_req": 5,
    },
    "endgame": {
        "name": "Village",
        "description": "A thriving village with full automation.",
        "combat_level_req": 80,
        "buildings_req": 8,
    },
}
