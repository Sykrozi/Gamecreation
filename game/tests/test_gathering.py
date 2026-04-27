import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.constants import SkillType
from entities.player import Player
from entities.skill import SkillSet
from entities.inventory import Inventory
from data.items import WEAPONS
from data.resources import ORES, TREES, FISH_SPOTS, FARMING_PATCHES, get_available_resources
from systems.gathering import (
    GatheringEngine, GatherResult,
    gather_mining, gather_woodcutting, gather_fishing, gather_farming,
    smith_item, cook_item, brew_potion, craft_rune,
)


def make_engine(mining_level=1, woodcutting_level=1, fishing_level=1,
                farming_level=1) -> GatheringEngine:
    skills = SkillSet()
    if mining_level > 1:
        skills.add_xp(SkillType.MINING, 999_999_999)
        skills.skills[SkillType.MINING].level = mining_level
    if woodcutting_level > 1:
        skills.add_xp(SkillType.WOODCUTTING, 999_999_999)
        skills.skills[SkillType.WOODCUTTING].level = woodcutting_level
    if fishing_level > 1:
        skills.add_xp(SkillType.FISHING, 999_999_999)
        skills.skills[SkillType.FISHING].level = fishing_level
    if farming_level > 1:
        skills.add_xp(SkillType.FARMING, 999_999_999)
        skills.skills[SkillType.FARMING].level = farming_level
    inventory = Inventory()
    return GatheringEngine(skills, inventory)


# ─── Resource data ────────────────────────────────────────────────────────────

def test_all_ores_defined():
    assert "copper" in ORES
    assert "runite" in ORES
    assert "legendary_ore" in ORES


def test_all_trees_defined():
    assert "oak" in TREES
    assert "magic_tree" in TREES


def test_get_available_resources_filters_by_level():
    available = get_available_resources(SkillType.MINING, 1)
    ids = [r.id for r in available]
    assert "copper" in ids
    assert "runite" not in ids   # requires level 55


def test_get_available_resources_at_high_level():
    available = get_available_resources(SkillType.MINING, 90)
    ids = [r.id for r in available]
    assert "legendary_ore" in ids


# ─── Mining interactions ──────────────────────────────────────────────────────

def test_mining_perfect_hit():
    node = ORES["copper"]
    qty, quality = gather_mining(node, skill_level=1, precision=0.5)
    assert qty >= 1
    assert quality == 1.0


def test_mining_miss():
    node = ORES["copper"]
    qty, quality = gather_mining(node, skill_level=1, precision=0.0)
    assert qty == 0


def test_mining_overcharge_at_level_30():
    node = ORES["iron"]
    qty_base, _ = gather_mining(node, skill_level=1, precision=0.5)
    qty_oc, _ = gather_mining(node, skill_level=30, precision=0.5)
    assert qty_oc >= qty_base


def test_mining_harder_ore_smaller_window():
    soft = ORES["copper"]
    hard = ORES["runite"]
    from systems.gathering import _sweet_spot_check
    # Hard ore sweet spot is narrower — a near-centre hit that works on copper
    # may not work on runite
    soft_qty, _ = gather_mining(soft, skill_level=1, precision=0.62)
    hard_qty, _ = gather_mining(hard, skill_level=1, precision=0.62)
    # Runite should be harder or equal — not easier
    assert soft_qty >= hard_qty


def test_gather_mining_engine():
    engine = make_engine(mining_level=1)
    outcome = engine.mine("copper", precision=0.5)
    assert outcome.result in (GatherResult.SUCCESS, GatherResult.PARTIAL)
    assert outcome.quantity >= 1
    assert outcome.xp_gained > 0


def test_gather_mining_level_check():
    engine = make_engine(mining_level=1)
    outcome = engine.mine("runite", precision=0.5)   # requires level 55
    assert outcome.result == GatherResult.FAIL
    assert "Need Mining" in outcome.narrative


# ─── Woodcutting interactions ─────────────────────────────────────────────────

def test_woodcutting_precise_hit():
    node = TREES["oak"]
    qty, quality = gather_woodcutting(node, skill_level=10, precision=0.9)
    assert qty >= 1
    assert quality == 1.0


def test_woodcutting_miss():
    node = TREES["oak"]
    qty, quality = gather_woodcutting(node, skill_level=1, precision=0.0)
    assert qty == 0


def test_woodcutting_tree_fells_after_hp():
    engine = make_engine(woodcutting_level=10)
    node = TREES["oak"]   # tree_hp = 3
    outcomes = []
    for _ in range(node.tree_hp + 1):
        outcomes.append(engine.chop("oak", precision=0.9))
    fell_msgs = [o for o in outcomes if "fell" in o.narrative]
    assert len(fell_msgs) >= 1


def test_woodcutting_combo_cut_at_30():
    node = TREES["maple"]
    qty_base, _ = gather_woodcutting(node, skill_level=1, precision=0.95)
    qty_combo, _ = gather_woodcutting(node, skill_level=30, precision=0.95)
    assert qty_combo >= qty_base


# ─── Fishing interactions ─────────────────────────────────────────────────────

def test_fishing_success():
    node = FISH_SPOTS["trout"]
    qty, quality = gather_fishing(node, skill_level=10, precision=0.5)
    assert qty >= 1


def test_fishing_miss():
    node = FISH_SPOTS["trout"]
    qty, quality = gather_fishing(node, skill_level=1, precision=0.0)
    assert qty == 0


def test_fishing_bait_required():
    engine = make_engine(fishing_level=25)
    outcome = engine.fish("tuna", precision=0.5, has_bait=False)
    assert outcome.result == GatherResult.FAIL
    assert "bait" in outcome.narrative


def test_fishing_bait_provided():
    engine = make_engine(fishing_level=25)
    outcome = engine.fish("tuna", precision=0.5, has_bait=True)
    assert outcome.result in (GatherResult.SUCCESS, GatherResult.PARTIAL,
                               GatherResult.FAIL)   # fail is OK if precision misses window


def test_fishing_window_grows_with_level():
    node = FISH_SPOTS["sardine"]
    # At high level the window is wider so a moderate precision should succeed
    qty_low, _ = gather_fishing(node, skill_level=1, precision=0.35)
    qty_high, _ = gather_fishing(node, skill_level=80, precision=0.35)
    assert qty_high >= qty_low


# ─── Farming interactions ─────────────────────────────────────────────────────

def test_farming_perfect_harvest():
    node = FARMING_PATCHES["guam_herb"]
    qty, quality = gather_farming(node, skill_level=5, precision=0.55)
    assert qty >= 1
    assert quality == 1.0


def test_farming_early_harvest():
    node = FARMING_PATCHES["guam_herb"]
    qty, quality = gather_farming(node, skill_level=5, precision=0.1)
    assert qty == 1
    assert quality == 0.5


def test_farming_late_harvest_spoiled():
    node = FARMING_PATCHES["guam_herb"]
    qty, quality = gather_farming(node, skill_level=5, precision=0.99)
    assert qty == 0


def test_gather_farming_engine():
    engine = make_engine(farming_level=1)
    outcome = engine.harvest("guam_herb", precision=0.5)
    assert outcome.result in (GatherResult.SUCCESS, GatherResult.PARTIAL,
                               GatherResult.FAIL)


# ─── Production interactions ──────────────────────────────────────────────────

def test_smithing_perfect_conditions():
    success, quality = smith_item(skill_level=50, precision=0.5, heat=0.7)
    assert success is True
    assert quality > 0.7


def test_smithing_cold_metal_fail():
    success, quality = smith_item(skill_level=50, precision=0.5, heat=0.1)
    # cold metal: either fails or low quality
    assert not success or quality <= 0.5


def test_cooking_perfect_timing():
    success, quality = cook_item(skill_level=40, precision=0.6)
    assert success is True
    assert quality > 0.6


def test_cooking_burnt():
    success, quality = cook_item(skill_level=1, precision=0.99)
    assert success is False
    assert quality == 0.0


def test_potion_correct_sequence():
    success, quality = brew_potion(
        skill_level=20,
        ingredient_sequence=["guam_herb", "eye_of_newt"],
        expected_sequence=["guam_herb", "eye_of_newt"],
        dose_precision=0.5,
    )
    assert success is True


def test_potion_wrong_sequence():
    success, quality = brew_potion(
        skill_level=20,
        ingredient_sequence=["eye_of_newt", "guam_herb"],
        expected_sequence=["guam_herb", "eye_of_newt"],
        dose_precision=0.5,
    )
    assert success is False


def test_runecraft_all_symbols_hit():
    success, count = craft_rune(skill_level=10, symbol_precisions=[0.9, 0.85, 0.9])
    assert success is True
    assert count >= 1


def test_runecraft_too_many_misses():
    success, count = craft_rune(skill_level=10, symbol_precisions=[0.1, 0.1, 0.1])
    assert success is False
    assert count == 0


# ─── Idle tick ────────────────────────────────────────────────────────────────

def test_idle_tick_grants_xp():
    engine = make_engine()
    before = engine._skills.level(SkillType.MINING)
    outcome = engine.idle_tick(SkillType.MINING, "copper", xp_per_tick=1000, qty_per_tick=1)
    assert outcome.xp_gained == 1000
    assert outcome.quantity == 1
    assert outcome.result == GatherResult.SUCCESS
