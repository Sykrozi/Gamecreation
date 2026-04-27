"""
Gathering skill engine.

Each skill has a distinct interaction pattern (from GDD):
  Mining    — Rhythmic tap: hit the sweet spot for bonus yield
  Woodcut   — Precision tap: fragile zones that appear/disappear
  Fishing   — Quick-time: balance tension in a capture window
  Farming   — Precision tap: plant/harvest at the right moment
  Smithing  — Rhythmic tap: hammer at the right moment + heat management
  Cooking   — Quick-time: remove from heat at the perfect point
  Herblore  — Mixed: ingredient sequence + dose adjustment
  Runecraft — Precision tap: trace rune symbols accurately

The engine models each interaction as a mini-game result (0.0–1.0 quality)
that scales XP and yield. In a real mobile client the UI drives the timing;
here we accept a float `precision` parameter so tests can drive it directly.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto

from core.constants import SkillType
from core.events import bus, GameEvent, EVT_LEVEL_UP
from data.resources import (
    Resource, OreNode, TreeNode, FishSpot, FarmingPatch,
    get_available_resources,
)


class GatherResult(Enum):
    SUCCESS = auto()
    PARTIAL = auto()      # got something but below sweet spot
    FAIL = auto()         # missed, no yield
    DEPLETED = auto()     # node empty, needs respawn


@dataclass
class GatherOutcome:
    result: GatherResult
    resource_id: str
    quantity: int
    xp_gained: int
    levels_gained: list[int] = field(default_factory=list)
    narrative: str = ""
    quality: float = 1.0   # 0.0–1.0, affects Cooking/Smithing output


# ─── Interaction helpers ──────────────────────────────────────────────────────

def _sweet_spot_check(precision: float, window: float) -> bool:
    """True if `precision` lands within the sweet-spot `window` centred at 0.5."""
    centre = 0.5
    return abs(precision - centre) <= window / 2


def _precision_check(precision: float, threshold: float) -> bool:
    """True if precision meets or exceeds threshold."""
    return precision >= threshold


# ─── Skill-specific gather functions ─────────────────────────────────────────

def gather_mining(node: OreNode, skill_level: int, precision: float) -> tuple[int, float]:
    """
    Rhythmic tap — sweet-spot window shrinks with harder ore.
    Returns (quantity, quality).
    """
    window = max(0.1, 0.5 - (node.ore_hardness - 1) * 0.08)
    if _sweet_spot_check(precision, window):
        # Perfect hit: overcharge bonus at level 30+
        bonus = 1 if skill_level >= 30 else 0
        return 1 + bonus, 1.0
    elif precision > 0.2:
        return 1, 0.7
    return 0, 0.0


def gather_woodcutting(node: TreeNode, skill_level: int, precision: float) -> tuple[int, float]:
    """
    Precision tap — hit the fragile zone.
    Returns (logs, quality). Multiple chops may be needed to fell the tree.
    """
    threshold = max(0.3, 0.7 - skill_level * 0.003)
    if _precision_check(precision, threshold):
        bonus = 1 if skill_level >= 30 else 0   # combo cut
        return 1 + bonus, 1.0
    return 0, 0.0


def gather_fishing(node: FishSpot, skill_level: int, precision: float) -> tuple[int, float]:
    """
    Quick-time — land precision inside the capture window.
    Returns (fish, quality).
    """
    window = min(0.6, 0.2 + skill_level * 0.004)
    if _sweet_spot_check(precision, window):
        return 1, 1.0
    elif precision > 0.3:
        return 1, 0.5
    return 0, 0.0


def gather_farming(patch: FarmingPatch, skill_level: int, precision: float) -> tuple[int, float]:
    """
    Precision tap — harvest at the right moment.
    Early = half yield, perfect = full, late = spoiled.
    Returns (herbs, quality).
    """
    if 0.4 <= precision <= 0.7:
        return random.randint(patch.quantity_min, patch.quantity_max + 1), 1.0
    elif precision < 0.4:
        return 1, 0.5      # early harvest
    else:
        return 0, 0.0      # over-ripe, spoiled


# ─── Production interaction functions ────────────────────────────────────────

def smith_item(skill_level: int, precision: float, heat: float) -> tuple[bool, float]:
    """
    Rhythmic tap + heat management.
    heat: 0.0 (cold) to 1.0 (perfect temperature)
    Returns (success, quality).
    """
    window = max(0.1, 0.4 - (100 - skill_level) * 0.003)
    timing_ok = _sweet_spot_check(precision, window)
    heat_ok = 0.5 <= heat <= 0.9
    if timing_ok and heat_ok:
        quality = 0.7 + heat * 0.3
        return True, min(1.0, quality)
    elif timing_ok or heat_ok:
        return True, 0.5
    return False, 0.0


def cook_item(skill_level: int, precision: float) -> tuple[bool, float]:
    """
    Quick-time — remove from heat at ideal point.
    Returns (success, quality). Burnt food = quality 0.
    """
    # Ideal window grows with cooking level
    ideal_min = max(0.1, 0.5 - skill_level * 0.003)
    ideal_max = min(0.9, 0.7 + skill_level * 0.002)
    if ideal_min <= precision <= ideal_max:
        quality = 0.6 + (precision - ideal_min) / (ideal_max - ideal_min) * 0.4
        return True, quality
    elif precision > ideal_max:
        return False, 0.0   # burnt
    return True, 0.3        # undercooked


def brew_potion(skill_level: int, ingredient_sequence: list[str],
                expected_sequence: list[str], dose_precision: float) -> tuple[bool, float]:
    """
    Mixed interaction — ingredient order + dose adjustment.
    Returns (success, quality).
    """
    if ingredient_sequence != expected_sequence:
        return False, 0.0
    window = min(0.5, 0.1 + skill_level * 0.004)
    quality = 1.0 if _sweet_spot_check(dose_precision, window) else 0.6
    return True, quality


def craft_rune(skill_level: int, symbol_precisions: list[float]) -> tuple[bool, int]:
    """
    Precision tap — trace each rune symbol accurately.
    Returns (success, rune_count).
    """
    threshold = max(0.4, 0.8 - skill_level * 0.004)
    hits = sum(1 for p in symbol_precisions if p >= threshold)
    total = len(symbol_precisions)
    if hits == total:
        # Bonus runes at high level
        bonus = skill_level // 25
        return True, 1 + bonus
    elif hits >= total // 2:
        return True, 1
    return False, 0


# ─── GatheringEngine: main interface ─────────────────────────────────────────

class GatheringEngine:
    """
    Drives a single gathering action for a player.
    The `precision` argument represents the outcome of the mobile mini-game
    (0.0 = worst, 1.0 = perfect). The UI layer supplies this value.
    """

    def __init__(self, skill_set, inventory):
        self._skills = skill_set
        self._inventory = inventory
        self._node_hp: dict[str, int] = {}   # remaining chops/ticks on active nodes

    # ─── Public actions ────────────────────────────────────────────────────

    def mine(self, ore_id: str, precision: float) -> GatherOutcome:
        from data.resources import ORES
        node = ORES.get(ore_id)
        if not node:
            return GatherOutcome(GatherResult.FAIL, ore_id, 0, 0,
                                  narrative=f"Unknown ore: {ore_id}")
        level = self._skills.level(SkillType.MINING)
        if level < node.level_req:
            return GatherOutcome(GatherResult.FAIL, ore_id, 0, 0,
                                  narrative=f"Need Mining {node.level_req}.")
        qty, quality = gather_mining(node, level, precision)
        return self._finalise(SkillType.MINING, node, qty, quality,
                               f"You mine {qty}x {node.name}." if qty else "You miss the sweet spot.")

    def chop(self, tree_id: str, precision: float) -> GatherOutcome:
        from data.resources import TREES
        node = TREES.get(tree_id)
        if not node:
            return GatherOutcome(GatherResult.FAIL, tree_id, 0, 0,
                                  narrative=f"Unknown tree: {tree_id}")
        level = self._skills.level(SkillType.WOODCUTTING)
        if level < node.level_req:
            return GatherOutcome(GatherResult.FAIL, tree_id, 0, 0,
                                  narrative=f"Need Woodcutting {node.level_req}.")

        # Track chops remaining
        if tree_id not in self._node_hp:
            self._node_hp[tree_id] = node.tree_hp

        qty, quality = gather_woodcutting(node, level, precision)
        if qty:
            self._node_hp[tree_id] -= 1

        if self._node_hp.get(tree_id, 1) <= 0:
            self._node_hp.pop(tree_id, None)
            narr = f"You fell the {node.name} and get {qty}x logs!"
        elif qty:
            narr = f"You chop {qty}x {node.name} logs."
        else:
            narr = "You miss the fragile zone."

        return self._finalise(SkillType.WOODCUTTING, node, qty, quality, narr)

    def fish(self, spot_id: str, precision: float, has_bait: bool = False) -> GatherOutcome:
        from data.resources import FISH_SPOTS
        node = FISH_SPOTS.get(spot_id)
        if not node:
            return GatherOutcome(GatherResult.FAIL, spot_id, 0, 0,
                                  narrative=f"Unknown fish spot: {spot_id}")
        level = self._skills.level(SkillType.FISHING)
        if level < node.level_req:
            return GatherOutcome(GatherResult.FAIL, spot_id, 0, 0,
                                  narrative=f"Need Fishing {node.level_req}.")
        if node.bait_required and not has_bait:
            return GatherOutcome(GatherResult.FAIL, spot_id, 0, 0,
                                  narrative=f"{node.name} requires bait.")
        qty, quality = gather_fishing(node, level, precision)
        narr = (f"You catch {qty}x {node.name}!" if qty
                else "The fish escapes — missed the capture window.")
        return self._finalise(SkillType.FISHING, node, qty, quality, narr)

    def harvest(self, patch_id: str, precision: float) -> GatherOutcome:
        from data.resources import FARMING_PATCHES
        node = FARMING_PATCHES.get(patch_id)
        if not node:
            return GatherOutcome(GatherResult.FAIL, patch_id, 0, 0,
                                  narrative=f"Unknown patch: {patch_id}")
        level = self._skills.level(SkillType.FARMING)
        if level < node.level_req:
            return GatherOutcome(GatherResult.FAIL, patch_id, 0, 0,
                                  narrative=f"Need Farming {node.level_req}.")
        qty, quality = gather_farming(node, level, precision)
        if qty:
            narr = f"You harvest {qty}x {node.name}."
        elif quality == 0.0 and precision >= 0.7:
            narr = f"The {node.name} is over-ripe — wasted."
        else:
            narr = f"Early harvest — {node.name} yields less."
        return self._finalise(SkillType.FARMING, node, qty, quality, narr)

    # ─── Internal ──────────────────────────────────────────────────────────

    def _finalise(self, skill: SkillType, node: Resource,
                   qty: int, quality: float, narr: str) -> GatherOutcome:
        if qty <= 0:
            return GatherOutcome(GatherResult.FAIL, node.id, 0, 0,
                                  narrative=narr, quality=quality)
        xp = int(node.xp_reward * quality * qty)
        levels = self._skills.add_xp(skill, xp)
        result = GatherResult.SUCCESS if quality >= 0.9 else GatherResult.PARTIAL
        return GatherOutcome(
            result=result,
            resource_id=node.id,
            quantity=qty,
            xp_gained=xp,
            levels_gained=levels,
            narrative=narr,
            quality=quality,
        )

    # ─── Idle gathering (hub automation) ───────────────────────────────────

    def idle_tick(self, skill: SkillType, resource_id: str,
                   xp_per_tick: int, qty_per_tick: int) -> GatherOutcome:
        """Called by the hub every game tick for automated gathering."""
        levels = self._skills.add_xp(skill, xp_per_tick)
        return GatherOutcome(
            result=GatherResult.SUCCESS,
            resource_id=resource_id,
            quantity=qty_per_tick,
            xp_gained=xp_per_tick,
            levels_gained=levels,
            narrative=f"[Idle] {skill.value}: +{qty_per_tick}x {resource_id}, +{xp_per_tick} XP.",
        )
