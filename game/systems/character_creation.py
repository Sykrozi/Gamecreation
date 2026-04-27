"""
Character creation — templates, name validation, and player factory.

Four templates match the GDD's play styles:
  warrior  — melee tank; iron sword, bronze body, attack/strength head-start
  ranger   — skirmisher; wood bow, cooked food, range head-start
  mage     — spell caster; basic staff, potions, magic head-start
  ironman  — self-sufficient challenge mode; bronze gear, no XP bonuses,
              ironman flag disables merchant purchases

Templates give starting gear (placed directly in inventory for the player
to equip themselves) plus a small XP head-start in the relevant combat skill.
"""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field

from core.constants import CombatStyle, SkillType


# ─── Template definition ──────────────────────────────────────────────────────

@dataclass
class CharacterTemplate:
    id: str
    name: str
    description: str
    starting_style: CombatStyle
    starting_weapon_id: str
    starting_armor_id: str | None              # body-slot armour or None
    starting_consumables: list[tuple[str, int]]  # [(item_id, qty)]
    skill_xp_bonuses: dict[SkillType, int] = field(default_factory=dict)
    is_ironman: bool = False


TEMPLATES: dict[str, CharacterTemplate] = {
    "warrior": CharacterTemplate(
        id="warrior",
        name="Warrior",
        description=(
            "A frontline brawler. Starts with an iron sword and bronze armour. "
            "High melee damage potential from the first dungeon."
        ),
        starting_style=CombatStyle.MELEE,
        starting_weapon_id="iron_sword",
        starting_armor_id="bronze_body",
        starting_consumables=[("basic_potion", 3), ("cooked_trout", 2)],
        skill_xp_bonuses={
            SkillType.ATTACK:   300,
            SkillType.STRENGTH: 200,
        },
    ),
    "ranger": CharacterTemplate(
        id="ranger",
        name="Ranger",
        description=(
            "A swift skirmisher who fights at range. Excels at exploiting "
            "enemy weaknesses before they close the distance."
        ),
        starting_style=CombatStyle.RANGE,
        starting_weapon_id="wood_bow",
        starting_armor_id=None,
        starting_consumables=[("basic_potion", 2), ("cooked_trout", 4)],
        skill_xp_bonuses={
            SkillType.RANGE: 400,
        },
    ),
    "mage": CharacterTemplate(
        id="mage",
        name="Mage",
        description=(
            "A fragile but potent arcane caster. Magic ignores physical defence "
            "and can exploit many monster weaknesses."
        ),
        starting_style=CombatStyle.MAGIC,
        starting_weapon_id="basic_staff",
        starting_armor_id=None,
        starting_consumables=[("basic_potion", 4)],
        skill_xp_bonuses={
            SkillType.MAGIC: 400,
        },
    ),
    "ironman": CharacterTemplate(
        id="ironman",
        name="Ironman",
        description=(
            "Self-sufficient challenge mode. No merchant purchases allowed. "
            "Every item must be earned. Starts with nothing but a bronze sword."
        ),
        starting_style=CombatStyle.MELEE,
        starting_weapon_id="bronze_sword",
        starting_armor_id=None,
        starting_consumables=[("basic_potion", 1)],
        skill_xp_bonuses={},
        is_ironman=True,
    ),
}


# ─── Name validation ──────────────────────────────────────────────────────────

_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9 _\-]{1,18}[A-Za-z0-9]$")
_RESERVED = {"admin", "system", "null", "none", "test", "player"}

def validate_name(name: str) -> tuple[bool, str]:
    """
    Returns (valid, reason_if_invalid).
    Rules:
      - 3–20 characters
      - Must start and end with alphanumeric
      - Allowed interior: letters, digits, space, underscore, hyphen
      - Not a reserved word
    """
    stripped = name.strip()
    if len(stripped) < 3:
        return False, "Name must be at least 3 characters."
    if len(stripped) > 20:
        return False, "Name must be 20 characters or fewer."
    if not _NAME_PATTERN.match(stripped):
        return False, ("Name must start and end with a letter or digit; "
                       "interior may use letters, digits, spaces, _ or -.")
    if stripped.lower() in _RESERVED:
        return False, f"'{stripped}' is a reserved name."
    return True, ""


# ─── Factory ─────────────────────────────────────────────────────────────────

class CharacterCreator:
    """
    Validates input and assembles a fully-initialised Player from a template.

    The returned player has:
      - active_style set to the template's combat style
      - Starting weapon equipped
      - Starting armour equipped (if the template includes one)
      - Consumables added to inventory
      - Skill XP bonuses applied
      - is_ironman flag on the player (if applicable)
    """

    @staticmethod
    def list_templates() -> list[CharacterTemplate]:
        return list(TEMPLATES.values())

    @staticmethod
    def create(name: str, template_id: str) -> "Player":  # type: ignore[return]
        from entities.player import Player
        from data.items import WEAPONS, ARMORS, CONSUMABLES

        # --- Validate ---
        ok, reason = validate_name(name)
        if not ok:
            raise ValueError(reason)
        template = TEMPLATES.get(template_id)
        if template is None:
            raise ValueError(f"Unknown template '{template_id}'. "
                             f"Choose from: {', '.join(TEMPLATES)}")

        # --- Build player ---
        player = Player(name=name.strip())
        player.active_style = template.starting_style

        # Equip weapon
        weapon = deepcopy(WEAPONS.get(template.starting_weapon_id))
        if weapon:
            player.equipment.weapon = weapon

        # Equip armour
        if template.starting_armor_id:
            armour = deepcopy(ARMORS.get(template.starting_armor_id))
            if armour:
                slot = armour.slot
                if hasattr(player.equipment, slot):
                    setattr(player.equipment, slot, armour)

        # Add consumables to inventory
        for item_id, qty in template.starting_consumables:
            consumable = deepcopy(CONSUMABLES.get(item_id))
            if consumable:
                consumable.quantity = qty
                if consumable.stackable:
                    consumable.doses = qty
                player.inventory.add(consumable)

        # Apply XP bonuses
        for skill, xp in template.skill_xp_bonuses.items():
            player.skills.add_xp(skill, xp)

        # Recompute HP after equipment is set
        player._max_hp = player._calc_max_hp()
        player._hp = player._max_hp

        # Store ironman flag
        player.is_ironman = template.is_ironman

        return player
