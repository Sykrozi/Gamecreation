import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from systems.character_creation import (
    CharacterCreator, TEMPLATES, validate_name, CharacterTemplate,
)
from core.constants import CombatStyle, SkillType


# ─── validate_name ────────────────────────────────────────────────────────────

def test_name_too_short():
    ok, reason = validate_name("Ab")
    assert ok is False
    assert "3" in reason


def test_name_too_long():
    ok, reason = validate_name("A" * 21)
    assert ok is False
    assert "20" in reason


def test_name_starts_with_digit_invalid():
    ok, reason = validate_name("1Hero")
    assert ok is False


def test_name_with_trailing_space_stripped_valid():
    # strip() is applied before validation, so trailing space doesn't invalidate
    ok, _ = validate_name("Hero ")
    assert ok is True


def test_name_reserved_word():
    ok, reason = validate_name("admin")
    assert ok is False
    assert "reserved" in reason.lower()


def test_name_valid_simple():
    ok, _ = validate_name("HeroName")
    assert ok is True


def test_name_valid_with_space():
    ok, _ = validate_name("Dark Knight")
    assert ok is True


def test_name_valid_with_hyphen():
    ok, _ = validate_name("Blade-Master")
    assert ok is True


def test_name_valid_min_length():
    ok, _ = validate_name("Axe")
    assert ok is True


def test_name_valid_max_length():
    ok, _ = validate_name("A" * 19 + "z")  # 20 chars, starts/ends alpha
    assert ok is True


# ─── TEMPLATES coverage ──────────────────────────────────────────────────────

def test_all_four_templates_exist():
    assert set(TEMPLATES.keys()) == {"warrior", "ranger", "mage", "ironman"}


def test_warrior_template_style():
    assert TEMPLATES["warrior"].starting_style == CombatStyle.MELEE


def test_ranger_template_style():
    assert TEMPLATES["ranger"].starting_style == CombatStyle.RANGE


def test_mage_template_style():
    assert TEMPLATES["mage"].starting_style == CombatStyle.MAGIC


def test_ironman_flag():
    assert TEMPLATES["ironman"].is_ironman is True


def test_non_ironman_flag():
    for tid in ("warrior", "ranger", "mage"):
        assert TEMPLATES[tid].is_ironman is False


def test_warrior_has_consumables():
    assert len(TEMPLATES["warrior"].starting_consumables) > 0


def test_templates_have_descriptions():
    for t in TEMPLATES.values():
        assert len(t.description) > 10


# ─── list_templates ───────────────────────────────────────────────────────────

def test_list_templates_returns_four():
    templates = CharacterCreator.list_templates()
    assert len(templates) == 4


def test_list_templates_returns_template_objects():
    templates = CharacterCreator.list_templates()
    assert all(isinstance(t, CharacterTemplate) for t in templates)


# ─── CharacterCreator.create — happy paths ───────────────────────────────────

def test_create_warrior():
    p = CharacterCreator.create("TestWarrior", "warrior")
    assert p.name == "TestWarrior"
    assert p.active_style == CombatStyle.MELEE
    assert p.equipment.weapon is not None
    assert p.equipment.weapon.id == "iron_sword"


def test_create_warrior_has_body_armor():
    p = CharacterCreator.create("Tanks", "warrior")
    assert p.equipment.body is not None
    assert p.equipment.body.id == "bronze_body"


def test_create_ranger():
    p = CharacterCreator.create("Swift", "ranger")
    assert p.active_style == CombatStyle.RANGE
    assert p.equipment.weapon.id == "wood_bow"


def test_create_mage():
    p = CharacterCreator.create("Arcane", "mage")
    assert p.active_style == CombatStyle.MAGIC
    assert p.equipment.weapon.id == "basic_staff"


def test_create_ironman():
    p = CharacterCreator.create("Ironone", "ironman")
    assert p.equipment.weapon.id == "bronze_sword"
    assert p.is_ironman is True


def test_create_warrior_consumables_in_inventory():
    p = CharacterCreator.create("Hero", "warrior")
    ids = [i.id for i in p.inventory.items]
    assert "basic_potion" in ids
    assert "cooked_trout" in ids


def test_create_warrior_xp_bonuses_applied():
    p = CharacterCreator.create("Fighter", "warrior")
    assert p.skills.level(SkillType.ATTACK) > 1
    assert p.skills.level(SkillType.STRENGTH) > 1


def test_create_ranger_xp_bonus_applied():
    p = CharacterCreator.create("Archer", "ranger")
    assert p.skills.level(SkillType.RANGE) > 1


def test_create_mage_xp_bonus_applied():
    p = CharacterCreator.create("Wizard", "mage")
    assert p.skills.level(SkillType.MAGIC) > 1


def test_create_ironman_no_xp_bonuses():
    p = CharacterCreator.create("Ironone", "ironman")
    # ironman template has no XP bonuses
    assert p.skills.level(SkillType.ATTACK) == 1


def test_create_sets_hp():
    p = CharacterCreator.create("Healer", "warrior")
    assert p.hp > 0
    assert p.max_hp > 0
    assert p.hp == p.max_hp


def test_create_strips_name_whitespace():
    p = CharacterCreator.create("  Trimmed  ", "warrior")
    assert p.name == "Trimmed"


# ─── CharacterCreator.create — error cases ───────────────────────────────────

def test_create_invalid_name_raises():
    with pytest.raises(ValueError, match="3"):
        CharacterCreator.create("Ab", "warrior")


def test_create_unknown_template_raises():
    with pytest.raises(ValueError, match="Unknown template"):
        CharacterCreator.create("Validname", "unknown_template")


def test_create_reserved_name_raises():
    with pytest.raises(ValueError, match="reserved"):
        CharacterCreator.create("admin", "warrior")
