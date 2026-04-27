import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.constants import SkillType
from systems.skill_challenge import SkillChallenge, ChallengeResult, CHALLENGE_XP


# ─── ChallengeResult structure ────────────────────────────────────────────────

def test_challenge_result_has_expected_fields():
    result = ChallengeResult(
        passed=True, quality=1.0, xp_gained=200,
        skill=SkillType.MINING, narrative="OK",
    )
    assert result.passed is True
    assert result.quality == 1.0
    assert result.bonus_items == []


# ─── Pass / fail by precision ─────────────────────────────────────────────────

def test_mining_passes_near_centre():
    # Sweet spot centred at 0.5; precision=0.5 should always pass
    result = SkillChallenge().attempt(SkillType.MINING, skill_level=1, precision=0.5)
    assert result.passed is True


def test_mining_fails_at_zero():
    result = SkillChallenge().attempt(SkillType.MINING, skill_level=1, precision=0.0)
    assert result.passed is False


def test_woodcutting_passes_high_precision():
    result = SkillChallenge().attempt(SkillType.WOODCUTTING, skill_level=10, precision=0.9)
    assert result.passed is True


def test_woodcutting_fails_low_precision():
    result = SkillChallenge().attempt(SkillType.WOODCUTTING, skill_level=1, precision=0.0)
    assert result.passed is False


def test_fishing_passes_mid_precision():
    result = SkillChallenge().attempt(SkillType.FISHING, skill_level=10, precision=0.5)
    assert result.passed is True


def test_farming_passes_mid_range():
    result = SkillChallenge().attempt(SkillType.FARMING, skill_level=5, precision=0.55)
    assert result.passed is True


def test_farming_fails_late_harvest():
    result = SkillChallenge().attempt(SkillType.FARMING, skill_level=5, precision=0.99)
    assert result.passed is False


def test_smithing_passes_good_conditions():
    result = SkillChallenge().attempt(SkillType.SMITHING, skill_level=50, precision=0.5)
    assert result.passed is True


def test_cooking_passes_within_window():
    result = SkillChallenge().attempt(SkillType.COOKING, skill_level=40, precision=0.6)
    assert result.passed is True


def test_herblore_passes_correct_sequence():
    result = SkillChallenge().attempt(SkillType.HERBLORE, skill_level=20, precision=0.5)
    assert result.passed is True


def test_runecraft_passes_good_precision():
    result = SkillChallenge().attempt(SkillType.RUNECRAFT, skill_level=10, precision=0.9)
    assert result.passed is True


def test_runecraft_fails_poor_precision():
    result = SkillChallenge().attempt(SkillType.RUNECRAFT, skill_level=1, precision=0.1)
    assert result.passed is False


# ─── XP scaling ───────────────────────────────────────────────────────────────

def test_pass_gives_more_xp_than_fail():
    ch = SkillChallenge()
    fail_result = ch.attempt(SkillType.MINING, skill_level=1, precision=0.0)
    pass_result = ch.attempt(SkillType.MINING, skill_level=1, precision=0.5)
    assert pass_result.xp_gained > fail_result.xp_gained


def test_fail_still_gives_consolation_xp():
    result = SkillChallenge().attempt(SkillType.MINING, skill_level=1, precision=0.0)
    assert result.xp_gained >= 10


def test_pass_xp_within_base_range():
    base = CHALLENGE_XP[SkillType.MINING]
    result = SkillChallenge().attempt(SkillType.MINING, skill_level=50, precision=0.5)
    assert result.xp_gained <= base + 1   # quality ≤ 1.0 so xp ≤ base


# ─── Bonus items ──────────────────────────────────────────────────────────────

def test_exceptional_quality_gives_bonus_items():
    # precision=0.5 on mining gives quality=1.0 which is > 0.85
    result = SkillChallenge().attempt(SkillType.MINING, skill_level=50, precision=0.5)
    assert result.quality == 1.0
    assert len(result.bonus_items) >= 1


def test_poor_quality_no_bonus_items():
    # precision=0.21 gives qty>0 but quality=0.7 on mining (below 0.85)
    result = SkillChallenge().attempt(SkillType.MINING, skill_level=1, precision=0.21)
    # quality=0.7 < 0.85 → no bonus
    assert result.bonus_items == []


# ─── Narrative ────────────────────────────────────────────────────────────────

def test_pass_narrative_contains_skill_name():
    result = SkillChallenge().attempt(SkillType.WOODCUTTING, skill_level=10, precision=0.9)
    assert "woodcutting" in result.narrative.lower() or "Woodcutting" in result.narrative


def test_fail_narrative_mentions_challenge():
    result = SkillChallenge().attempt(SkillType.MINING, skill_level=1, precision=0.0)
    assert "challenge" in result.narrative.lower() or "Mining" in result.narrative


# ─── Skill attribute ─────────────────────────────────────────────────────────

def test_result_skill_matches_input():
    for skill in (SkillType.MINING, SkillType.FISHING, SkillType.RUNECRAFT):
        result = SkillChallenge().attempt(skill, skill_level=10, precision=0.5)
        assert result.skill == skill


# ─── High level eases challenge ───────────────────────────────────────────────

def test_high_woodcutting_level_easier_threshold():
    # At level 99 the threshold is ~0.3 - 0.003*99 ≈ lower than level 1
    low_result  = SkillChallenge().attempt(SkillType.WOODCUTTING, skill_level=1,  precision=0.35)
    high_result = SkillChallenge().attempt(SkillType.WOODCUTTING, skill_level=99, precision=0.35)
    # High level should pass at least as often
    assert not (low_result.passed and not high_result.passed)
