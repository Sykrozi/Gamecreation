"""
Skill challenge system — mandatory dungeon skill rooms.

Each zone has one skill room. The player inputs a precision float (0.0–1.0)
representing their mini-game performance; the challenge resolves pass/fail
using the same maths as the gathering engine.

Difficulty scales inversely with skill level:
  - Higher skill → wider sweet spot / lower threshold → easier to pass
  - Exceptional quality (≥ 0.85) awards a bonus raw resource drop

Failing a skill room does NOT advance the room — the player must retry
(precision input) or die trying. Each attempt still grants consolation XP.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from core.constants import SkillType, MaterialTier
from core.events import bus, GameEvent

EVT_SKILL_CHALLENGE_PASS = "skill_challenge_pass"
EVT_SKILL_CHALLENGE_FAIL = "skill_challenge_fail"


@dataclass
class ChallengeResult:
    passed: bool
    quality: float          # 0.0–1.0 — scales XP gained
    xp_gained: int
    skill: SkillType
    narrative: str
    bonus_items: list[str] = field(default_factory=list)  # item IDs on exceptional perf


# Base XP awarded for clearing a skill room challenge (× quality multiplier)
CHALLENGE_XP: dict[SkillType, int] = {
    SkillType.MINING:      250,
    SkillType.WOODCUTTING: 200,
    SkillType.FISHING:     175,
    SkillType.FARMING:     150,
    SkillType.SMITHING:    275,
    SkillType.COOKING:     175,
    SkillType.HERBLORE:    225,
    SkillType.RUNECRAFT:   300,
}

# Raw resource IDs awarded on exceptional (quality ≥ 0.85) performance
CHALLENGE_BONUS_ITEMS: dict[SkillType, list[str]] = {
    SkillType.MINING:      ["iron", "coal"],
    SkillType.WOODCUTTING: ["oak"],
    SkillType.FISHING:     ["cooked_trout"],
    SkillType.FARMING:     ["guam_herb"],
    SkillType.SMITHING:    ["iron_sword"],
    SkillType.COOKING:     ["cooked_trout"],
    SkillType.HERBLORE:    ["basic_potion"],
    SkillType.RUNECRAFT:   ["basic_potion"],
}

_PASS_NARRATIVES = {
    "exceptional": "Exceptional {skill}! You clear the challenge and earn bonus resources.",
    "solid":       "Solid {skill} — the challenge is cleared.",
    "scrape":      "You barely scrape through the {skill} challenge.",
}
_FAIL_NARRATIVE = "The {skill} challenge blocks your way. Try again."


class SkillChallenge:
    """
    Resolves a dungeon skill-room challenge.

    Usage:
        result = SkillChallenge().attempt(SkillType.MINING, skill_level=30, precision=0.55)
        if result.passed:
            player.skills.add_xp(result.skill, result.xp_gained)
            room.advance()
    """

    def attempt(self, skill: SkillType, skill_level: int, precision: float) -> ChallengeResult:
        passed, quality = self._resolve(skill, skill_level, precision)

        base_xp = CHALLENGE_XP.get(skill, 175)
        xp = int(base_xp * (0.4 + quality * 0.6))   # floor at 40 % for a fail

        if not passed:
            bus.emit(GameEvent(EVT_SKILL_CHALLENGE_FAIL, {
                "skill": skill.value, "precision": precision,
            }))
            narrative = _FAIL_NARRATIVE.format(skill=skill.value.capitalize())
            return ChallengeResult(
                passed=False, quality=quality,
                xp_gained=max(10, xp // 3),   # consolation XP
                skill=skill, narrative=narrative,
            )

        bonus: list[str] = []
        if quality >= 0.85:
            candidates = CHALLENGE_BONUS_ITEMS.get(skill, [])
            bonus = candidates[:1]             # one bonus item max
            tier_label = "exceptional"
        elif quality >= 0.55:
            tier_label = "solid"
        else:
            tier_label = "scrape"

        narrative = _PASS_NARRATIVES[tier_label].format(skill=skill.value.capitalize())
        bus.emit(GameEvent(EVT_SKILL_CHALLENGE_PASS, {
            "skill": skill.value, "quality": quality, "bonus": bonus,
        }))
        return ChallengeResult(
            passed=True, quality=quality, xp_gained=xp,
            skill=skill, narrative=narrative, bonus_items=bonus,
        )

    # ─── Per-skill resolution ─────────────────────────────────────────────

    def _resolve(self, skill: SkillType, level: int, precision: float) -> tuple[bool, float]:
        """Returns (passed, quality) by delegating to the gathering engine maths."""
        from systems.gathering import (
            gather_mining, gather_woodcutting, gather_fishing, gather_farming,
            smith_item, cook_item, brew_potion, craft_rune,
        )
        from data.resources import OreNode, TreeNode, FishSpot, FarmingPatch

        if skill == SkillType.MINING:
            node = OreNode(id="_ch", name="Challenge Rock", skill=skill,
                           level_req=1, xp_reward=0, tier=MaterialTier.IRON,
                           ore_hardness=2)
            qty, quality = gather_mining(node, level, precision)
            return qty > 0, quality

        if skill == SkillType.WOODCUTTING:
            node = TreeNode(id="_ch", name="Challenge Tree", skill=skill,
                            level_req=1, xp_reward=0, tier=MaterialTier.IRON,
                            tree_hp=1)
            qty, quality = gather_woodcutting(node, level, precision)
            return qty > 0, quality

        if skill == SkillType.FISHING:
            node = FishSpot(id="_ch", name="Challenge Spot", skill=skill,
                            level_req=1, xp_reward=0, tier=MaterialTier.IRON,
                            bait_required=False)
            qty, quality = gather_fishing(node, level, precision)
            return qty > 0, quality

        if skill == SkillType.FARMING:
            node = FarmingPatch(id="_ch", name="Challenge Herb", skill=skill,
                                level_req=1, xp_reward=0, tier=MaterialTier.IRON)
            qty, quality = gather_farming(node, level, precision)
            return qty > 0, quality

        if skill == SkillType.SMITHING:
            # Higher-level smithers get a hotter, more forgiving forge
            heat = min(0.9, 0.5 + level * 0.004)
            success, quality = smith_item(level, precision, heat)
            return success, quality

        if skill == SkillType.COOKING:
            success, quality = cook_item(level, precision)
            return success, quality

        if skill == SkillType.HERBLORE:
            seq = ["guam_herb", "eye_of_newt"]
            success, quality = brew_potion(level, seq, seq, precision)
            return success, quality

        if skill == SkillType.RUNECRAFT:
            # Three symbols; derive slightly varied precisions from the single input
            symbols = [
                min(1.0, precision * 1.05),
                precision,
                min(1.0, precision * 0.95),
            ]
            success, _ = craft_rune(level, symbols)
            quality = precision if success else 0.0
            return success, quality

        # Fallback: simple threshold that eases with level
        threshold = max(0.25, 0.70 - level * 0.003)
        passed = precision >= threshold
        return passed, precision if passed else 0.0
