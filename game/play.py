"""Quick combat demo — run: python play.py"""
import sys, os, textwrap
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from copy import deepcopy
from core.constants import CombatAction
from data.items import WEAPONS, CONSUMABLES
from data.monsters import MONSTERS
from entities.player import Player
from entities.monster import MonsterInstance
from systems.combat import CombatEngine, CombatResult

def bar(hp, mx, w=20):
    f = round(w * hp / mx) if mx else 0
    return f"[{'█'*f}{'░'*(w-f)}] {hp}/{mx}"

def show(e):
    p, en = e.player, e.enemy
    pots = sum(i.quantity for i in p.inventory.items if hasattr(i, 'heal_amount'))
    print(f"\n{'═'*52}")
    print(f"  YOU   {p.name}  Lv{p.skills.combat_level}   Special {p.special_bar}%  Pots {pots}")
    print(f"  HP    {bar(p.hp, p.max_hp)}")
    print(f"  {'─'*48}")
    print(f"  ENEMY {en.name}  Lv{en.definition.level}")
    print(f"  HP    {bar(en.hp, en.max_hp)}")
    print(f"{'═'*52}")

MENU = [("1","Attack",CombatAction.ATTACK), ("2","Defend",CombatAction.DEFEND),
        ("3","Use Potion",CombatAction.USE_ITEM), ("4","Flee",CombatAction.FLEE),
        ("5","Special Strike",CombatAction.SPECIAL_STRIKE)]

def prompt(engine):
    valid = {a.value for a in engine.get_valid_actions()}
    print()
    for k, label, act in MENU:
        dim = "" if act.value in valid else "  (not ready)"
        print(f"  [{k}] {label}{dim}")
    while True:
        raw = input("\n  > ").strip()
        row = next((r for r in MENU if r[0] == raw), None)
        if row and row[2].value in valid:
            return row[2]
        print("  Invalid — pick from the list above.")

def run(player, enemy_id):
    enemy  = MonsterInstance(MONSTERS[enemy_id])
    engine = CombatEngine(player, enemy)
    engine.start()
    print(f"\n  ⚔  {player.name}  vs  {enemy.name}  ⚔")

    while engine.result == CombatResult.ONGOING:
        show(engine)
        action = prompt(engine)
        item_id = None
        if action == CombatAction.USE_ITEM:
            pot = next((i for i in player.inventory.items
                        if hasattr(i, 'heal_amount') and i.quantity > 0), None)
            if not pot:
                print("  No potions!"); continue
            item_id = pot.id
        log = engine.player_action(action, item_id=item_id)
        print(f"\n  {textwrap.fill(log.narrative, 50)}")
        if log.effects_applied: print(f"  + {', '.join(log.effects_applied)}")
        if log.effects_expired:  print(f"  - {', '.join(log.effects_expired)}")

    msgs = {CombatResult.PLAYER_WIN: "✓ Victory!", CombatResult.PLAYER_FLED: "~ Escaped.",
            CombatResult.PLAYER_DEAD: "✗ You died."}
    print(f"\n  {msgs.get(engine.result, 'Done.')}\n")
if __name__ == "__main__":
    p = Player("Hero")
    p.equipment.weapon = deepcopy(WEAPONS["bronze_sword"])
    pot = deepcopy(CONSUMABLES["basic_potion"]); pot.quantity = 3
    p.inventory.add(pot)

    print("Available enemies:", ", ".join(MONSTERS))
    choice = input("Fight which enemy? [goblin]: ").strip() or "goblin"
    if choice not in MONSTERS:
        print(f"Unknown: '{choice}'"); sys.exit(1)
    run(p, choice)
