import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.constants import SkillType, XP_TABLE, MAX_LEVEL
from entities.skill import Skill, SkillSet


def test_skill_starts_at_level_1():
    skill = Skill(skill_type=SkillType.ATTACK)
    assert skill.level == 1
    assert skill.xp == 0


def test_add_xp_increases_level():
    skill = Skill(skill_type=SkillType.ATTACK)
    # Get enough XP to reach level 2
    xp_needed = XP_TABLE.get(2, 83)
    leveled = skill.add_xp(xp_needed)
    assert skill.level >= 2
    assert 2 in leveled


def test_level_cap_at_99():
    skill = Skill(skill_type=SkillType.ATTACK)
    skill.add_xp(999_999_999)
    assert skill.level == MAX_LEVEL


def test_xp_to_next_level():
    skill = Skill(skill_type=SkillType.ATTACK)
    xp_needed = skill.xp_to_next_level()
    assert xp_needed > 0
    skill.add_xp(xp_needed)
    assert skill.level == 2


def test_skill_set_all_skills_initialized():
    ss = SkillSet()
    for st in SkillType:
        assert ss.get(st) is not None
        assert ss.level(st) == 1


def test_combat_level_increases_with_skills():
    ss = SkillSet()
    base_cb = ss.combat_level
    ss.add_xp(SkillType.ATTACK, 1_000_000)
    ss.add_xp(SkillType.STRENGTH, 1_000_000)
    assert ss.combat_level > base_cb


def test_combat_level_formula_bounded():
    ss = SkillSet()
    ss.add_xp(SkillType.ATTACK, 999_999_999)
    ss.add_xp(SkillType.DEFENSE, 999_999_999)
    ss.add_xp(SkillType.STRENGTH, 999_999_999)
    ss.add_xp(SkillType.RESISTANCE, 999_999_999)
    ss.add_xp(SkillType.RANGE, 999_999_999)
    ss.add_xp(SkillType.MAGIC, 999_999_999)
    assert 1 <= ss.combat_level <= 200  # reasonable cap


def test_multi_levelup_in_one_add():
    skill = Skill(skill_type=SkillType.ATTACK)
    # Jump many levels at once
    leveled = skill.add_xp(50_000)
    assert len(leveled) > 1
    assert skill.level > 2
