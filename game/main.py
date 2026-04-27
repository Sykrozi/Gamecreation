"""
Game entry point — text-based demo of the combat and dungeon systems.
Run: python main.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.constants import CombatAction, CombatStyle, SkillType
from data.items import WEAPONS
from entities.player import Player
from systems.combat import CombatEngine, CombatResult
from systems.dungeon import DungeonRunner, RoomType, EventType


def pick_action(engine: CombatEngine) -> tuple[CombatAction, str | None]:
    actions = engine.get_valid_actions()
    print("\nAvailable actions:")
    for i, action in enumerate(actions):
        print(f"  {i + 1}. {action.value}")
    while True:
        try:
            choice = int(input("Choose action: ")) - 1
            if 0 <= choice < len(actions):
                chosen = actions[choice]
                item_id = None
                if chosen == CombatAction.USE_ITEM:
                    consumables = engine.player.inventory.get_consumables()
                    if not consumables:
                        print("No consumables in inventory.")
                        continue
                    for j, item in enumerate(consumables):
                        print(f"  {j + 1}. {item.name}")
                    ci = int(input("Choose item: ")) - 1
                    item_id = consumables[ci].id
                return chosen, item_id
        except (ValueError, IndexError):
            pass
        print("Invalid choice.")


def run_combat_room(runner: DungeonRunner) -> bool:
    engine = runner.start_combat()
    if not engine:
        print("No enemy in this room.")
        return True

    room = runner.current_room
    print(f"\n{'='*50}")
    print(f"  COMBAT: {engine.enemy.name}")
    weaknesses = engine.enemy_weakness_info()
    print(f"  Weaknesses: {weaknesses}")
    print(f"{'='*50}")

    while engine.result == CombatResult.ONGOING:
        print(f"\n{engine.summary()}")
        action, item_id = pick_action(engine)
        log = engine.player_action(action, item_id=item_id)
        print(f"\n>>> {log.narrative}")
        if log.effects_applied:
            print(f"    Effects applied: {log.effects_applied}")
        if log.effects_expired:
            print(f"    Effects expired: {log.effects_expired}")

    result = runner.resolve_combat(engine)
    if result["result"] == "win":
        print(f"\n[WIN] +{result['xp']} XP | Drops: {result['drops']}")
        return True
    elif result["result"] == "fled":
        print("\n[FLED] You escaped.")
        return True
    elif result["result"] == "dead":
        print(f"\n[DEAD] {result['message']}")
        return False
    return True


def run_dungeon(player: Player, zone: str) -> None:
    runner = DungeonRunner(player, zone)
    print(f"\n{'#'*50}")
    print(f"  ENTERING DUNGEON: {zone.upper()}")
    print(f"  Rooms: {runner.run.total_rooms}")
    print(f"{'#'*50}")

    while not runner.run.is_complete:
        room = runner.current_room
        if not room:
            break

        print(f"\n--- {runner.status()} ---")
        info = runner.enter_current_room()
        print(f"Room type: {info['type'].upper()}")

        if info["type"] == "combat":
            alive = run_combat_room(runner)
            if not alive:
                break

        elif info["type"] == "boss":
            print(f"BOSS FIGHT: {info['boss']} ({info['phases']} phases)")
            alive = run_combat_room(runner)
            if not alive:
                break

        elif info["type"] == "skill":
            print("SKILL CHALLENGE — Press Enter to attempt...")
            input()
            result = runner.complete_skill_room(success=True)
            print(f"Skill room: {result}")

        elif info["type"] == "loot":
            result = runner.collect_loot_room()
            print(f"Loot room drops: {result['drops']}")

        elif info["type"] == "event":
            event = info["event"]
            print(f"EVENT: {event.upper()}")
            if event == EventType.TRAP.value:
                result = runner.handle_trap_event()
                print(f"Trap! -{result['trap_damage']} HP | {result['drops']}")
            elif event == EventType.TREASURE.value:
                result = runner.handle_treasure_event()
                print(f"Treasure! {result['drops']}")
            elif event in (EventType.ELITE.value, EventType.RARE_MONSTER.value):
                alive = run_combat_room(runner)
                if not alive:
                    break
            elif event == EventType.MERCHANT.value:
                print("Mysterious Merchant appears... (shop not yet implemented)")
                runner.run.advance()
            else:
                runner.run.advance()

    if runner.run.is_complete and not runner.run.player_died:
        print(f"\n{'='*50}")
        print("  DUNGEON COMPLETE!")
        print(f"  Total drops this run: {runner.run.drops_this_run}")
        print(f"{'='*50}")


def main():
    print("=== Mobile RPG — Foundation Demo ===")
    name = input("Enter character name: ").strip() or "Hero"
    player = Player(name=name)
    player.equipment.weapon = WEAPONS["bronze_sword"]
    player.active_style = CombatStyle.MELEE

    print(f"\nCreated: {player}")
    print(f"Combat Level: {player.skills.combat_level}")

    while True:
        print("\n--- HUB ---")
        print("1. Enter Forest dungeon")
        print("2. View character")
        print("3. Quit")
        choice = input("> ").strip()

        if choice == "1":
            run_dungeon(player, "forest")
        elif choice == "2":
            print(f"\n{player}")
            for st in SkillType:
                skill = player.skills.get(st)
                print(f"  {skill.skill_type.value:<15} Lv {skill.level:>2} | XP: {skill.xp}")
        elif choice == "3":
            print("Goodbye!")
            break


if __name__ == "__main__":
    main()
