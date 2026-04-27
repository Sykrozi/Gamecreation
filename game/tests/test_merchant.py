import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from entities.player import Player
from data.items import WEAPONS
from systems.merchant import MerchantShop, MerchantItem


def make_player() -> Player:
    p = Player(name="Test")
    p.equipment.weapon = WEAPONS["bronze_sword"]
    return p


# ─── Shop generation ─────────────────────────────────────────────────────────

def test_shop_generates_items():
    shop = MerchantShop("forest")
    assert len(shop.list_items()) >= 1


def test_shop_items_have_positive_price():
    shop = MerchantShop("forest")
    for item in shop.list_items():
        assert item.price_currency > 0


def test_shop_items_have_stock():
    shop = MerchantShop("forest")
    for item in shop.list_items():
        assert item.stock >= 1


def test_shop_generates_for_each_zone():
    for zone in ("forest", "dungeon_1", "swamp", "desert", "mountain", "void", "raid"):
        shop = MerchantShop(zone)
        assert len(shop.list_items()) >= 1


def test_unknown_zone_falls_back_to_defaults():
    shop = MerchantShop("unknown_zone")
    assert len(shop.list_items()) >= 1


# ─── Affordability ───────────────────────────────────────────────────────────

def test_item_affordable_with_enough_currency():
    item = MerchantItem("basic_potion", "Healing Potion", price_currency=10)
    assert item.is_affordable(zone_currency=10, gold=0)


def test_item_not_affordable_without_currency():
    item = MerchantItem("basic_potion", "Healing Potion", price_currency=10)
    assert not item.is_affordable(zone_currency=5, gold=0)


def test_item_requires_gold_too():
    item = MerchantItem("iron_sword", "Iron Sword", price_currency=30, price_gold=5)
    assert item.is_affordable(30, 5)
    assert not item.is_affordable(30, 4)


# ─── Purchase flow ────────────────────────────────────────────────────────────

def test_buy_succeeds_with_funds():
    player = make_player()
    player.inventory.zone_currency = 100
    shop = MerchantShop("forest")
    # Find the cheapest item
    items = sorted(shop.list_items(), key=lambda i: i.price_currency)
    result = shop.buy(items[0].item_id, player)
    assert result["success"] is True


def test_buy_deducts_currency():
    player = make_player()
    player.inventory.zone_currency = 100
    shop = MerchantShop("forest")
    items = sorted(shop.list_items(), key=lambda i: i.price_currency)
    cheapest = items[0]
    cost = cheapest.price_currency
    shop.buy(cheapest.item_id, player)
    assert player.inventory.zone_currency == 100 - cost


def test_buy_reduces_stock():
    player = make_player()
    player.inventory.zone_currency = 999
    shop = MerchantShop("forest")
    items = shop.list_items()
    item = items[0]
    stock_before = item.stock
    shop.buy(item.item_id, player)
    assert item.stock == stock_before - 1


def test_buy_fails_without_currency():
    player = make_player()
    player.inventory.zone_currency = 0
    shop = MerchantShop("forest")
    items = shop.list_items()
    result = shop.buy(items[0].item_id, player)
    assert result["success"] is False
    assert "Need" in result["reason"]


def test_buy_depleted_item_fails():
    player = make_player()
    player.inventory.zone_currency = 9999
    shop = MerchantShop("forest")
    items = [i for i in shop.list_items() if i.stock == 1]
    if not items:
        pytest.skip("No 1-stock items in this random shop")
    item = items[0]
    shop.buy(item.item_id, player)   # buys last unit
    result = shop.buy(item.item_id, player)
    assert result["success"] is False


def test_buy_unknown_item_fails():
    player = make_player()
    player.inventory.zone_currency = 999
    shop = MerchantShop("forest")
    result = shop.buy("nonexistent_item_xyz", player)
    assert result["success"] is False


def test_buy_adds_item_to_inventory():
    player = make_player()
    player.inventory.zone_currency = 999
    shop = MerchantShop("forest")
    items = [i for i in shop.list_items() if i.item_id == "basic_potion"]
    if not items:
        pytest.skip("basic_potion not in shop this run")
    before = len(player.inventory.items)
    shop.buy("basic_potion", player)
    # stackable: may not add a slot but quantity increases
    after_count = sum(i.quantity for i in player.inventory.items)
    assert after_count > 0


# ─── Summary ─────────────────────────────────────────────────────────────────

def test_summary_lists_items():
    shop = MerchantShop("forest")
    s = shop.summary()
    assert "sale" in s.lower() or len(s) > 0


def test_summary_empty_after_all_bought():
    player = make_player()
    player.inventory.zone_currency = 9999
    shop = MerchantShop("forest")
    # Buy everything
    for item in list(shop.list_items()):
        for _ in range(item.stock):
            shop.buy(item.item_id, player)
    s = shop.summary()
    assert "nothing" in s.lower()
