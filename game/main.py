"""
Game entry point — text-based demo driven by GameInterface.
Run: python main.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ui.game_interface import GameInterface, GameState
from core.constants import CombatAction


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _hr(char="─", width=54):
    print(char * width)


def _header(text: str):
    _hr("═")
    print(f"  {text}")
    _hr("═")


# ─── Combat loop ─────────────────────────────────────────────────────────────

def _run_combat(gi: GameInterface) -> bool:
    """Returns True if player survived, False if dead."""
    info = gi.start_combat()
    if not info["success"]:
        return True

    print(f"\n  ENEMY: {info['enemy']}  ({info['enemy_hp']} HP)")
    print(f"  Weaknesses: {info['weaknesses']}")

    while gi.state == GameState.COMBAT:
        summary = gi.combat_summary()
        print(f"\n  [Turn {summary['turn']}] "
              f"You: {summary['player_hp']} HP  |  "
              f"Enemy: {summary['enemy_hp']} HP")

        actions = summary["actions"]
        for i, a in enumerate(actions, 1):
            print(f"    {i}. {a}")

        try:
            choice = int(input("  Action: ")) - 1
            if not (0 <= choice < len(actions)):
                raise ValueError
            action = actions[choice]
        except (ValueError, IndexError):
            print("  Invalid choice.")
            continue

        item_id = None
        if action == CombatAction.USE_ITEM.value:
            consumables = gi.filter_inventory("consumable")
            if not consumables:
                print("  No consumables!")
                continue
            for j, c in enumerate(consumables, 1):
                print(f"    {j}. {c['name']}")
            try:
                item_id = consumables[int(input("  Item: ")) - 1]["item_id"]
            except (ValueError, IndexError):
                continue

        result = gi.combat_action(action, item_id=item_id)
        print(f"\n  >>> {result['narrative']}")
        if result["effects_applied"]:
            print(f"      Applied: {result['effects_applied']}")
        if result["effects_expired"]:
            print(f"      Expired: {result['effects_expired']}")

        if result["combat_result"] == "VICTORY":
            resolve = result.get("resolve", {})
            print(f"\n  [WIN] +{resolve.get('xp', 0)} XP | Drops: {resolve.get('drops', [])}")
        elif result["combat_result"] == "DEFEAT":
            print("\n  [DEAD] You have fallen.")
            return False
        elif result["combat_result"] == "FLED":
            print("\n  [FLED] You escaped.")

    return True


# ─── Dungeon loop ─────────────────────────────────────────────────────────────

def _run_dungeon(gi: GameInterface, zone_id: str) -> None:
    result = gi.enter_zone(zone_id)
    if not result["success"]:
        print(f"  Cannot enter: {result['reason']}")
        return

    _header(f"DUNGEON: {zone_id.upper()}  ({result['total_rooms']} rooms)")

    while gi.state == GameState.DUNGEON:
        room = gi.current_room()
        rtype = room.get("type", "?")
        print(f"\n  ── {rtype.upper()} ──")

        if rtype in ("combat", "boss"):
            if rtype == "boss":
                print(f"  BOSS: {room.get('boss', '?')} — {room.get('phases', 1)} phase(s)")
            alive = _run_combat(gi)
            if not alive:
                break

        elif rtype == "skill":
            print(f"  Skill challenge: {room.get('skill', '?')}")
            try:
                prec = float(input("  Precision (0.0–1.0): "))
            except ValueError:
                prec = 0.5
            res = gi.skill_room_attempt(prec)
            print(f"  {'PASSED' if res.get('success') else 'FAILED'}: "
                  f"{res.get('narrative', '')}")

        elif rtype == "loot":
            res = gi.collect_loot_room()
            print(f"  Loot: {res.get('drops', [])}")

        elif rtype == "event":
            event = room.get("event", "")
            print(f"  Event: {event.upper()}")
            if event == "trap":
                res = gi.handle_trap()
                print(f"  Trap! -{res.get('trap_damage', 0)} HP")
            elif event == "treasure":
                res = gi.handle_treasure()
                print(f"  Treasure: {res.get('drops', [])}")
            elif event == "merchant":
                shop = gi.get_merchant_shop()
                print("  Merchant items:")
                for item in shop.get("items", []):
                    print(f"    {item['name']} — {item['price_currency']} tokens "
                          f"/ {item['price_gold']} gold (stock {item['stock']})")
                bid = input("  Buy item_id (or Enter to skip): ").strip()
                if bid:
                    print(f"  {gi.buy_from_merchant(bid)}")
                gi.dismiss_merchant()
            else:
                # elite / rare — combat
                _run_combat(gi)

        if gi.state == GameState.GAME_OVER:
            break

    if gi.state == GameState.HUB:
        _header("DUNGEON COMPLETE — Back at Hub")


# ─── Hub menu ────────────────────────────────────────────────────────────────

def _hub_menu(gi: GameInterface) -> bool:
    """Returns False when the user wants to quit."""
    status = gi.hub_status()
    print(f"\n  Level {status['combat_level']}  |  HP {status['player_hp']}/{status['player_max_hp']}")
    print(f"  {status['progression']}")
    _hr()
    zones = gi.list_zones()
    print("  Unlocked zones:", [z["id"] for z in zones["unlocked"]])
    _hr()
    print("  1. Enter dungeon")
    print("  2. Inventory")
    print("  3. Character stats")
    print("  4. Tick hub (gather resources)")
    print("  5. Save game")
    print("  6. Quit")
    choice = input("> ").strip()

    if choice == "1":
        unlocked = [z["id"] for z in zones["unlocked"]]
        for i, zid in enumerate(unlocked, 1):
            print(f"    {i}. {zid}")
        try:
            zid = unlocked[int(input("  Zone: ")) - 1]
        except (ValueError, IndexError):
            return True
        _run_dungeon(gi, zid)

    elif choice == "2":
        view = gi.inventory_view()
        print(f"\n  Gold: {view['gold']}  Tokens: {view['zone_currency']}")
        print(f"  Slots: {view['slots_used']}/{view['slots_used'] + view['slots_free']}")
        print("  Equipped:", view["equipped"])
        print("  Items:")
        for item in view["inventory"]:
            print(f"    [{item['type'][0]}] {item['name']} (Lv{item['level_req']}) x{item['quantity']}")

    elif choice == "3":
        stats = gi.character_stats()
        print(f"\n  {stats['name']}  |  Combat Lv {stats['combat_level']}")
        print(f"  HP: {stats['hp']}/{stats['max_hp']}")
        for skill_name, data in stats["skills"].items():
            print(f"    {skill_name:<15} Lv {data['level']:>2} | XP {data['xp']}")

    elif choice == "4":
        outcomes = gi.hub_tick(5)
        if outcomes:
            for o in outcomes:
                print(f"  +{o['quantity']} {o['resource_id']} | +{o['xp_gained']} XP | {o['narrative']}")
        else:
            print("  No gathering buildings active yet.")

    elif choice == "5":
        path = input("  Save file path [save.json]: ").strip() or "save.json"
        res = gi.save(path)
        print(f"  Saved to {res.get('filepath')}" if res["success"] else f"  Failed: {res.get('reason')}")

    elif choice == "6":
        return False

    return True


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    gi = GameInterface()
    _header("MOBILE RPG — GAME INTERFACE DEMO")

    # Check for existing save
    save_path = "save.json"
    if os.path.exists(save_path):
        ans = input(f"  Load existing save '{save_path}'? [y/N]: ").strip().lower()
        if ans == "y":
            result = gi.load(save_path)
            if result["success"]:
                print(f"  Loaded: {result['name']}")
            else:
                print(f"  Load failed: {result['reason']}")

    if gi.state == GameState.MAIN_MENU:
        _header("CHARACTER CREATION")
        templates = gi.list_templates()
        for t in templates:
            ironman_flag = " [IRONMAN]" if t["is_ironman"] else ""
            print(f"  {t['id']:<10} {t['name']}{ironman_flag}")
            print(f"             {t['description'][:70]}")

        _hr()
        name = input("  Character name: ").strip() or "Hero"
        template_id = input("  Template (warrior/ranger/mage/ironman): ").strip() or "warrior"

        result = gi.create_character(name, template_id)
        if not result["success"]:
            print(f"  Error: {result['reason']}")
            sys.exit(1)

        print(f"\n  Created {result['name']} — Combat Lv {result['combat_level']}")
        print(f"  HP: {result['hp']}/{result['max_hp']}")

    while _hub_menu(gi):
        pass

    print("\n  Goodbye!")


if __name__ == "__main__":
    main()
