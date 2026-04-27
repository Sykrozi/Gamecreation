"""
Merchant system — in-dungeon shop that appears in EVENT rooms.

The merchant sells zone-appropriate consumables and occasionally gear.
Prices are denominated in zone_currency (the zone-specific token).
A secondary gold price applies to gear items.

Stock is generated once per merchant encounter and is limited.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from core.events import bus, GameEvent

EVT_MERCHANT_PURCHASE = "merchant_purchase"


@dataclass
class MerchantItem:
    item_id: str
    display_name: str
    price_currency: int     # zone currency cost
    price_gold: int = 0     # gold cost (0 = no gold requirement)
    stock: int = 1          # units available

    def is_affordable(self, zone_currency: int, gold: int) -> bool:
        return zone_currency >= self.price_currency and gold >= self.price_gold


# ─── Shop templates per zone ──────────────────────────────────────────────────

_ZONE_STOCK: dict[str, list[tuple[str, int, int, int]]] = {
    # (item_id, currency_price, gold_price, max_stock)
    "forest": [
        ("basic_potion",    10, 0, 3),
        ("anti_venom",      8,  0, 2),
        ("cooked_trout",    5,  0, 4),
        ("bronze_sword",    30, 0, 1),
        ("bronze_body",     40, 0, 1),
    ],
    "dungeon_1": [
        ("basic_potion",    12, 0, 3),
        ("strength_potion", 18, 0, 2),
        ("anti_venom",      10, 0, 2),
        ("iron_sword",      45, 5, 1),
        ("iron_body",       55, 5, 1),
    ],
    "swamp": [
        ("super_potion",    20, 0, 2),
        ("anti_venom",      12, 0, 3),
        ("defense_potion",  18, 0, 2),
        ("steel_sword",     60, 10, 1),
        ("steel_body",      70, 10, 1),
    ],
    "desert": [
        ("super_potion",    22, 0, 3),
        ("defense_potion",  20, 0, 2),
        ("overload",        50, 20, 1),
        ("mithril_sword",   80, 15, 1),
        ("mithril_body",    90, 15, 1),
    ],
    "mountain": [
        ("super_potion",    25, 0, 3),
        ("overload",        55, 20, 2),
        ("strength_potion", 22, 0, 2),
        ("adamantite_sword",100, 25, 1),
        ("adamantite_body", 110, 25, 1),
    ],
    "void": [
        ("overload",        60, 20, 3),
        ("super_potion",    28, 0, 3),
        ("defense_potion",  25, 0, 2),
        ("rune_sword",      130, 40, 1),
        ("rune_body",       140, 40, 1),
    ],
    "raid": [
        ("overload",        65, 20, 4),
        ("super_potion",    30, 0, 4),
        ("defense_potion",  28, 0, 3),
        ("rune_staff",      140, 40, 1),
        ("magic_bow",       140, 40, 1),
    ],
}

_DEFAULT_STOCK: list[tuple[str, int, int, int]] = [
    ("basic_potion",  10, 0, 3),
    ("anti_venom",    8,  0, 2),
    ("cooked_trout",  5,  0, 4),
]


class MerchantShop:
    """
    One-time-use shop generated for a single merchant event room.
    Items deplete from stock as they are purchased.
    """

    def __init__(self, zone_id: str) -> None:
        self.zone_id = zone_id
        self._stock: list[MerchantItem] = self._generate(zone_id)

    # ─── Public API ───────────────────────────────────────────────────────

    def list_items(self) -> list[MerchantItem]:
        """Return items still in stock."""
        return [item for item in self._stock if item.stock > 0]

    def buy(self, item_id: str, player) -> dict:
        """
        Attempt to purchase one unit of item_id.
        Deducts zone_currency (and gold if required) and adds item to inventory.
        Returns {"success": bool, "reason": str}.
        """
        from data.items import WEAPONS, ARMORS, CONSUMABLES
        from copy import deepcopy

        item = next((i for i in self._stock if i.item_id == item_id and i.stock > 0), None)
        if not item:
            return {"success": False, "reason": "Item not available."}

        if not item.is_affordable(player.inventory.zone_currency, player.inventory.gold):
            needed = f"{item.price_currency} currency"
            if item.price_gold:
                needed += f" + {item.price_gold} gold"
            return {"success": False, "reason": f"Need {needed}."}

        # Resolve the actual item object
        game_item = (
            deepcopy(WEAPONS.get(item_id))
            or deepcopy(ARMORS.get(item_id))
            or deepcopy(CONSUMABLES.get(item_id))
        )
        if game_item is None:
            return {"success": False, "reason": "Item data not found."}

        if not player.inventory.add(game_item):
            return {"success": False, "reason": "Inventory full."}

        # Deduct costs
        player.inventory.zone_currency -= item.price_currency
        player.inventory.gold -= item.price_gold
        item.stock -= 1

        bus.emit(GameEvent(EVT_MERCHANT_PURCHASE, {
            "item_id": item_id,
            "price_currency": item.price_currency,
            "price_gold": item.price_gold,
        }))
        return {
            "success": True,
            "item_id": item_id,
            "name": item.display_name,
            "remaining_stock": item.stock,
        }

    def summary(self) -> str:
        items = self.list_items()
        if not items:
            return "The merchant has nothing left to sell."
        parts = [f"{i.display_name} ({i.price_currency}¤)" for i in items]
        return "For sale: " + ", ".join(parts)

    # ─── Internal ─────────────────────────────────────────────────────────

    def _generate(self, zone_id: str) -> list[MerchantItem]:
        template = _ZONE_STOCK.get(zone_id, _DEFAULT_STOCK)
        from data.items import WEAPONS, ARMORS, CONSUMABLES

        items: list[MerchantItem] = []
        # Always include all consumables from the template; randomise gear
        for entry in template:
            item_id, price_c, price_g, max_stock = entry
            if item_id in WEAPONS or item_id in ARMORS:
                if random.random() > 0.5:      # 50% chance gear appears
                    continue
            # Resolve display name
            obj = (WEAPONS.get(item_id) or ARMORS.get(item_id)
                   or CONSUMABLES.get(item_id))
            name = obj.name if obj else item_id.replace("_", " ").title()
            stock = random.randint(1, max_stock)
            items.append(MerchantItem(
                item_id=item_id,
                display_name=name,
                price_currency=price_c,
                price_gold=price_g,
                stock=stock,
            ))
        return items
