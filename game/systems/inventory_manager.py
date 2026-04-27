"""
Inventory manager — equip/unequip, item comparison, and display helpers.

Wraps a Player's Inventory + Equipment objects and enforces:
  - Level requirements on equip (attack/range/magic/defense skill-gated)
  - Slot management (unequip returns item to inventory)
  - Stat delta comparison (candidate vs. currently equipped)
  - Sorting and filtering shortcuts
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.constants import CombatStyle, SkillType
from data.items import Item, Weapon, Armor, Consumable, WEAPONS, ARMORS, CONSUMABLES

if TYPE_CHECKING:
    from entities.player import Player


# ─── Per-style skill gate ─────────────────────────────────────────────────────

_WEAPON_SKILL: dict[CombatStyle, SkillType] = {
    CombatStyle.MELEE: SkillType.ATTACK,
    CombatStyle.RANGE: SkillType.RANGE,
    CombatStyle.MAGIC: SkillType.MAGIC,
}


# ─── Stat snapshot ────────────────────────────────────────────────────────────

@dataclass
class StatSnapshot:
    attack_bonus: int = 0
    defense_bonus: int = 0
    strength_bonus: int = 0
    range_bonus: int = 0
    magic_bonus: int = 0

    def delta(self, other: "StatSnapshot") -> "StatSnapshot":
        """Returns (self - other) — positive means self is better."""
        return StatSnapshot(
            attack_bonus   = self.attack_bonus   - other.attack_bonus,
            defense_bonus  = self.defense_bonus  - other.defense_bonus,
            strength_bonus = self.strength_bonus - other.strength_bonus,
            range_bonus    = self.range_bonus    - other.range_bonus,
            magic_bonus    = self.magic_bonus    - other.magic_bonus,
        )

    def to_dict(self) -> dict:
        return {
            "attack":   self.attack_bonus,
            "defense":  self.defense_bonus,
            "strength": self.strength_bonus,
            "range":    self.range_bonus,
            "magic":    self.magic_bonus,
        }


def _item_stats(item: Item | None) -> StatSnapshot:
    if item is None:
        return StatSnapshot()
    s = item.stats
    return StatSnapshot(
        attack_bonus   = s.attack_bonus,
        defense_bonus  = s.defense_bonus,
        strength_bonus = s.strength_bonus,
        range_bonus    = s.range_bonus,
        magic_bonus    = s.magic_bonus,
    )


# ─── Manager ─────────────────────────────────────────────────────────────────

class InventoryManager:
    """
    Coordinates inventory and equipment for a single player.

    All mutating methods return a result dict with at minimum:
      {"success": bool, "reason": str}
    plus operation-specific keys.
    """

    def __init__(self, player: "Player") -> None:
        self._player = player

    # ─── Read helpers ─────────────────────────────────────────────────────

    @property
    def inventory(self):
        return self._player.inventory

    @property
    def equipment(self):
        return self._player.equipment

    def slots_used(self) -> int:
        return len(self.inventory.items)

    def slots_free(self) -> int:
        return self.inventory.max_slots - self.slots_used()

    def equipped_summary(self) -> dict:
        eq = self.equipment
        return {
            "weapon": eq.weapon.name if eq.weapon else None,
            "head":   eq.head.name   if eq.head   else None,
            "body":   eq.body.name   if eq.body   else None,
            "legs":   eq.legs.name   if eq.legs   else None,
            "hands":  eq.hands.name  if eq.hands  else None,
            "feet":   eq.feet.name   if eq.feet   else None,
            "shield": eq.shield.name if eq.shield else None,
        }

    def inventory_summary(self) -> list[dict]:
        return [
            {
                "item_id":  item.id,
                "name":     item.name,
                "type":     type(item).__name__,
                "quantity": item.quantity,
                "level_req": item.level_req,
                "tier":     item.tier.value,
            }
            for item in self.inventory.items
        ]

    def full_view(self) -> dict:
        return {
            "equipped":      self.equipped_summary(),
            "inventory":     self.inventory_summary(),
            "slots_used":    self.slots_used(),
            "slots_free":    self.slots_free(),
            "zone_currency": self.inventory.zone_currency,
            "gold":          self.inventory.gold,
        }

    # ─── Item info ────────────────────────────────────────────────────────

    def item_info(self, item_id: str) -> dict:
        """Returns full stats for any item (in inventory or item database)."""
        item = self._find_in_inventory(item_id)
        if item is None:
            item = (WEAPONS.get(item_id) or ARMORS.get(item_id)
                    or CONSUMABLES.get(item_id))
        if item is None:
            return {"error": f"Unknown item '{item_id}'."}

        info: dict = {
            "item_id":   item.id,
            "name":      item.name,
            "type":      type(item).__name__,
            "tier":      item.tier.value,
            "level_req": item.level_req,
            "stats":     _item_stats(item).to_dict(),
        }
        if isinstance(item, Weapon):
            info["combat_style"]  = item.combat_style.value
            info["damage_min"]    = item.damage_min
            info["damage_max"]    = item.damage_max
            info["special_cost"]  = item.special_cost
        if isinstance(item, Armor):
            info["slot"] = item.slot
        if isinstance(item, Consumable):
            info["heal_amount"]       = item.heal_amount
            info["effect"]            = item.effect
            info["effect_duration"]   = item.effect_duration
            info["effect_magnitude"]  = item.effect_magnitude
            info["doses"]             = item.doses
        return info

    # ─── Equip ────────────────────────────────────────────────────────────

    def equip(self, item_id: str) -> dict:
        """
        Move an item from inventory to the appropriate equipment slot.
        Returns the previously equipped item (if any) to the inventory.
        """
        item = self._find_in_inventory(item_id)
        if item is None:
            return {"success": False, "reason": f"'{item_id}' not in inventory."}

        # Level requirement check
        ok, reason = self._check_level_req(item)
        if not ok:
            return {"success": False, "reason": reason}

        if isinstance(item, Weapon):
            return self._equip_weapon(item)
        if isinstance(item, Armor):
            return self._equip_armor(item)
        return {"success": False, "reason": "Only weapons and armour can be equipped."}

    def unequip(self, slot: str) -> dict:
        """
        Remove the item in `slot` and return it to the inventory.
        `slot` must be one of: weapon, head, body, legs, hands, feet, shield
        """
        valid_slots = ("weapon", "head", "body", "legs", "hands", "feet", "shield")
        if slot not in valid_slots:
            return {"success": False, "reason": f"Invalid slot '{slot}'."}

        current = getattr(self.equipment, slot, None)
        if current is None:
            return {"success": False, "reason": f"Nothing equipped in '{slot}'."}

        if not self.inventory.add(current):
            return {"success": False, "reason": "Inventory full — make room first."}

        setattr(self.equipment, slot, None)
        # Recompute player max HP since equipment changed
        self._player._max_hp = self._player._calc_max_hp()
        return {"success": True, "unequipped": current.name, "slot": slot}

    # ─── Comparison ───────────────────────────────────────────────────────

    def compare(self, item_id: str) -> dict:
        """
        Compare an item in the inventory against what is currently equipped in
        its slot. Returns stat deltas (positive = candidate is better).
        """
        item = self._find_in_inventory(item_id)
        if item is None:
            return {"error": f"'{item_id}' not in inventory."}

        if isinstance(item, Weapon):
            current = self.equipment.weapon
        elif isinstance(item, Armor):
            slot = item.slot
            current = getattr(self.equipment, slot, None)
        else:
            return {"error": "Consumables cannot be compared for equip stats."}

        candidate_stats = _item_stats(item)
        current_stats   = _item_stats(current)
        delta           = candidate_stats.delta(current_stats)

        return {
            "item_id":    item_id,
            "name":       item.name,
            "candidate":  candidate_stats.to_dict(),
            "equipped":   current_stats.to_dict(),
            "delta":      delta.to_dict(),
            "is_upgrade": any(v > 0 for v in delta.to_dict().values()),
            "level_req":  item.level_req,
        }

    # ─── Consumable use ───────────────────────────────────────────────────

    def use_item(self, item_id: str) -> dict:
        result = self._player.use_consumable(item_id)
        if not result["success"]:
            return {"success": False, "reason": result.get("error", "Failed.")}
        return result

    # ─── Drop ─────────────────────────────────────────────────────────────

    def drop(self, item_id: str) -> dict:
        """Remove one unit of item_id from inventory permanently."""
        if self.inventory.remove(item_id):
            return {"success": True, "dropped": item_id}
        return {"success": False, "reason": f"'{item_id}' not in inventory."}

    # ─── Sorting / filtering ──────────────────────────────────────────────

    def sort(self, by: str = "type") -> None:
        """
        Sort inventory in-place.
        `by`: "type" | "tier" | "level" | "name"
        """
        key_funcs = {
            "type":  lambda i: (type(i).__name__, i.level_req),
            "tier":  lambda i: (i.tier.value, i.level_req),
            "level": lambda i: i.level_req,
            "name":  lambda i: i.name.lower(),
        }
        key = key_funcs.get(by, key_funcs["type"])
        self.inventory.items.sort(key=key)

    def filter_by_type(self, item_type: str) -> list[dict]:
        """
        Filter inventory items.
        `item_type`: "weapon" | "armor" | "consumable"
        """
        type_map = {
            "weapon":    Weapon,
            "armor":     Armor,
            "consumable": Consumable,
        }
        cls = type_map.get(item_type.lower())
        if cls is None:
            return []
        return [
            {"item_id": i.id, "name": i.name, "level_req": i.level_req}
            for i in self.inventory.items
            if isinstance(i, cls)
        ]

    # ─── Internal ─────────────────────────────────────────────────────────

    def _find_in_inventory(self, item_id: str) -> Item | None:
        return next((i for i in self.inventory.items if i.id == item_id), None)

    def _check_level_req(self, item: Item) -> tuple[bool, str]:
        p = self._player
        req = item.level_req
        if req <= 1:
            return True, ""

        if isinstance(item, Weapon):
            skill = _WEAPON_SKILL.get(item.combat_style, SkillType.ATTACK)
            have = p.skills.level(skill)
            if have < req:
                return False, (
                    f"Need {skill.value.capitalize()} level {req} "
                    f"(you have {have})."
                )
        elif isinstance(item, Armor):
            have = p.skills.level(SkillType.DEFENSE)
            if have < req:
                return False, (
                    f"Need Defense level {req} (you have {have})."
                )
        return True, ""

    def _equip_weapon(self, item: Weapon) -> dict:
        from copy import deepcopy
        old = self.equipment.weapon
        # Return old weapon to inventory
        if old is not None and not self.inventory.add(old):
            return {"success": False, "reason": "Inventory full — unequip failed."}
        self.inventory.remove(item.id)
        self.equipment.weapon = item
        self._player._max_hp = self._player._calc_max_hp()
        return {
            "success":    True,
            "equipped":   item.name,
            "slot":       "weapon",
            "unequipped": old.name if old else None,
        }

    def _equip_armor(self, item: Armor) -> dict:
        slot = item.slot
        if not hasattr(self.equipment, slot):
            return {"success": False, "reason": f"Unknown armour slot '{slot}'."}
        old = getattr(self.equipment, slot)
        if old is not None and not self.inventory.add(old):
            return {"success": False, "reason": "Inventory full — unequip failed."}
        self.inventory.remove(item.id)
        setattr(self.equipment, slot, item)
        self._player._max_hp = self._player._calc_max_hp()
        return {
            "success":    True,
            "equipped":   item.name,
            "slot":       slot,
            "unequipped": old.name if old else None,
        }
