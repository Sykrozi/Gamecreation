"""
GameInterface — the single entry point for all game actions.

Every public method returns a structured dict so any frontend (terminal,
mobile, web) can drive the game without knowing internal class layout.

State machine:
  MAIN_MENU → CHARACTER_CREATION → HUB
  HUB → DUNGEON_SELECT → DUNGEON → COMBAT | SKILL | LOOT | EVENT → HUB
  HUB → INVENTORY | CHARACTER | BESTIARY

Persistence:
  save(filepath) / load(filepath) — JSON round-trip for the full game state
"""
from __future__ import annotations

import json
import os
from enum import Enum


class GameState(Enum):
    MAIN_MENU           = "main_menu"
    CHARACTER_CREATION  = "character_creation"
    HUB                 = "hub"
    DUNGEON_SELECT      = "dungeon_select"
    DUNGEON             = "dungeon"
    COMBAT              = "combat"
    INVENTORY           = "inventory"
    CHARACTER           = "character"
    BESTIARY_VIEW       = "bestiary"
    GAME_OVER           = "game_over"


class GameInterface:
    """
    Facade over all game systems.  Instantiate once per play session.
    """

    def __init__(self) -> None:
        self.state: GameState = GameState.MAIN_MENU
        self.player              = None
        self.hub                 = None
        self._progression        = None
        self._bestiary           = None
        self._runner             = None   # active DungeonRunner
        self._engine             = None   # active CombatEngine
        self._inventory_manager  = None
        self._gathering_engine   = None

    # ══════════════════════════════════════════════════════════════════════
    # CHARACTER CREATION
    # ══════════════════════════════════════════════════════════════════════

    def list_templates(self) -> list[dict]:
        from systems.character_creation import CharacterCreator, TEMPLATES
        return [
            {
                "id":          t.id,
                "name":        t.name,
                "description": t.description,
                "style":       t.starting_style.value,
                "is_ironman":  t.is_ironman,
            }
            for t in CharacterCreator.list_templates()
        ]

    def create_character(self, name: str, template_id: str) -> dict:
        from systems.character_creation import CharacterCreator, validate_name
        from systems.progression import ProgressionManager
        from systems.bestiary import Bestiary
        from systems.hub import Hub
        from systems.inventory_manager import InventoryManager
        from systems.gathering import GatheringEngine

        ok, reason = validate_name(name)
        if not ok:
            return {"success": False, "reason": reason}

        try:
            self.player = CharacterCreator.create(name, template_id)
        except ValueError as e:
            return {"success": False, "reason": str(e)}

        self._progression       = ProgressionManager()
        self._bestiary          = Bestiary()
        self.hub                = Hub(self.player)
        self._inventory_manager = InventoryManager(self.player)
        self._gathering_engine  = GatheringEngine(
            self.player.skills, self.player.inventory
        )
        self.state = GameState.HUB
        return {
            "success":  True,
            "name":     self.player.name,
            "template": template_id,
            "hp":       self.player.hp,
            "max_hp":   self.player.max_hp,
            "combat_level": self.player.skills.combat_level,
        }

    # ══════════════════════════════════════════════════════════════════════
    # HUB
    # ══════════════════════════════════════════════════════════════════════

    def hub_status(self) -> dict:
        self._require("hub")
        status = self.hub.status()
        status["player_hp"]    = self.player.hp
        status["player_max_hp"]= self.player.max_hp
        status["combat_level"] = self.player.skills.combat_level
        status["progression"]  = self._progression.summary()
        return status

    def hub_tick(self, ticks: int = 1) -> list[dict]:
        self._require("hub")
        outcomes = []
        for _ in range(ticks):
            for o in self.hub.tick(self._gathering_engine):
                outcomes.append({
                    "resource_id": o.resource_id,
                    "quantity":    o.quantity,
                    "xp_gained":   o.xp_gained,
                    "narrative":   o.narrative,
                })
        return outcomes

    def hub_build(self, building_id: str) -> dict:
        self._require("hub")
        return self.hub.build(building_id)

    def hub_upgrade(self, building_id: str) -> dict:
        self._require("hub")
        return self.hub.upgrade(building_id)

    def hub_available_buildings(self) -> list[str]:
        self._require("hub")
        return self.hub.available_to_build()

    def hub_deposit(self, resource_id: str, quantity: int) -> dict:
        self._require("hub")
        self.hub.deposit(resource_id, quantity)
        return {"success": True, "resource_id": resource_id, "quantity": quantity}

    def hub_withdraw(self, resource_id: str, quantity: int) -> dict:
        self._require("hub")
        if self.hub.withdraw(resource_id, quantity):
            return {"success": True}
        return {"success": False, "reason": "Insufficient stock."}

    # ══════════════════════════════════════════════════════════════════════
    # ZONE / DUNGEON
    # ══════════════════════════════════════════════════════════════════════

    def list_zones(self) -> dict:
        self._require("player")
        from data.zones import ZONES, ZONE_ORDER
        unlocked, locked = [], []
        for zid in ZONE_ORDER:
            zone = ZONES[zid]
            ok, reason = self._progression.can_enter(zid, self.player)
            entry = {
                "id":            zid,
                "name":          zone.name,
                "tier":          zone.tier.value,
                "recommended_level": zone.recommended_combat_level,
                "skill_challenge": zone.skill_challenge.value,
            }
            if ok:
                unlocked.append(entry)
            else:
                entry["lock_reason"] = reason
                locked.append(entry)
        return {"unlocked": unlocked, "locked": locked}

    def enter_zone(self, zone_id: str, luck: float = 0.0) -> dict:
        self._require("player")
        ok, reason = self._progression.can_enter(zone_id, self.player)
        if not ok:
            return {"success": False, "reason": reason}

        from systems.dungeon import DungeonRunner
        is_ironman = getattr(self.player, "is_ironman", False)
        self._runner = DungeonRunner(
            player=self.player,
            zone=zone_id,
            luck=luck,
            bestiary=self._bestiary,
            progression=self._progression,
        )
        self.state = GameState.DUNGEON
        run = self._runner.run
        return {
            "success":     True,
            "zone_id":     zone_id,
            "total_rooms": run.total_rooms,
            "first_room":  self._runner.enter_current_room(),
        }

    def current_room(self) -> dict:
        self._require("dungeon")
        return self._runner.enter_current_room()

    # ── Combat ────────────────────────────────────────────────────────────

    def start_combat(self) -> dict:
        self._require("dungeon")
        engine = self._runner.start_combat()
        if engine is None:
            return {"success": False, "reason": "No combat in this room."}
        self._engine = engine
        self.state   = GameState.COMBAT
        return {
            "success":   True,
            "enemy":     self._engine.enemy.name,
            "enemy_hp":  self._engine.enemy.hp,
            "enemy_max_hp": self._engine.enemy.max_hp,
            "weaknesses": self._engine.enemy_weakness_info(),
            "actions":   [a.value for a in self._engine.get_valid_actions()],
        }

    def combat_action(self, action_name: str, item_id: str | None = None) -> dict:
        self._require("combat")
        from core.constants import CombatAction
        from systems.combat import CombatResult
        try:
            action = CombatAction(action_name)
        except ValueError:
            return {"success": False, "reason": f"Unknown action '{action_name}'."}

        log = self._engine.player_action(action, item_id=item_id)
        result = {
            "turn":             log.turn,
            "narrative":        log.narrative,
            "damage":           log.damage,
            "heal":             log.heal,
            "effects_applied":  log.effects_applied,
            "effects_expired":  log.effects_expired,
            "player_hp":        self.player.hp,
            "player_max_hp":    self.player.max_hp,
            "enemy_hp":         self._engine.enemy.hp,
            "enemy_max_hp":     self._engine.enemy.max_hp,
            "combat_result":    self._engine.result.name,
        }

        if self._engine.result != CombatResult.ONGOING:
            resolve = self._runner.resolve_combat(self._engine)
            result["resolve"] = resolve
            self._engine = None
            if self._runner.run.is_complete or resolve.get("result") == "dead":
                self._finalize_run()
            else:
                self.state = GameState.DUNGEON

        return result

    def get_combat_actions(self) -> list[str]:
        self._require("combat")
        return [a.value for a in self._engine.get_valid_actions()]

    def combat_summary(self) -> dict:
        self._require("combat")
        return {
            "turn":        self._engine.turn,
            "summary":     self._engine.summary(),
            "player_hp":   self.player.hp,
            "enemy_hp":    self._engine.enemy.hp,
            "actions":     self.get_combat_actions(),
        }

    # ── Skill room ────────────────────────────────────────────────────────

    def skill_room_attempt(self, precision: float) -> dict:
        self._require("dungeon")
        result = self._runner.complete_skill_room(precision)
        if result.get("success"):
            self.state = GameState.DUNGEON
        return result

    # ── Loot room ─────────────────────────────────────────────────────────

    def collect_loot_room(self) -> dict:
        self._require("dungeon")
        return self._runner.collect_loot_room()

    # ── Events ────────────────────────────────────────────────────────────

    def handle_trap(self) -> dict:
        self._require("dungeon")
        return self._runner.handle_trap_event()

    def handle_treasure(self) -> dict:
        self._require("dungeon")
        return self._runner.handle_treasure_event()

    def get_merchant_shop(self) -> dict:
        self._require("dungeon")
        shop = self._runner.get_merchant_shop()
        if shop is None:
            return {"error": "No merchant in this room."}
        return {
            "items": [
                {
                    "item_id":        i.item_id,
                    "name":           i.display_name,
                    "price_currency": i.price_currency,
                    "price_gold":     i.price_gold,
                    "stock":          i.stock,
                }
                for i in shop.list_items()
            ]
        }

    def buy_from_merchant(self, item_id: str) -> dict:
        self._require("dungeon")
        shop = self._runner.get_merchant_shop()
        if shop is None:
            return {"success": False, "reason": "No merchant here."}
        if getattr(self.player, "is_ironman", False):
            return {"success": False, "reason": "Ironman mode — cannot use merchants."}
        return shop.buy(item_id, self.player)

    def dismiss_merchant(self) -> dict:
        self._require("dungeon")
        return self._runner.dismiss_merchant()

    def abandon_run(self) -> dict:
        self._require("dungeon")
        self._runner.run.is_complete = True
        self._finalize_run()
        return {"success": True, "message": "Run abandoned."}

    # ══════════════════════════════════════════════════════════════════════
    # INVENTORY
    # ══════════════════════════════════════════════════════════════════════

    def inventory_view(self) -> dict:
        self._require("player")
        return self._inventory_manager.full_view()

    def equip_item(self, item_id: str) -> dict:
        self._require("player")
        return self._inventory_manager.equip(item_id)

    def unequip_slot(self, slot: str) -> dict:
        self._require("player")
        return self._inventory_manager.unequip(slot)

    def use_item(self, item_id: str) -> dict:
        self._require("player")
        return self._inventory_manager.use_item(item_id)

    def drop_item(self, item_id: str) -> dict:
        self._require("player")
        return self._inventory_manager.drop(item_id)

    def compare_item(self, item_id: str) -> dict:
        self._require("player")
        return self._inventory_manager.compare(item_id)

    def item_info(self, item_id: str) -> dict:
        self._require("player")
        return self._inventory_manager.item_info(item_id)

    def sort_inventory(self, by: str = "type") -> dict:
        self._require("player")
        self._inventory_manager.sort(by)
        return {"success": True, "sorted_by": by}

    def filter_inventory(self, item_type: str) -> list[dict]:
        self._require("player")
        return self._inventory_manager.filter_by_type(item_type)

    # ══════════════════════════════════════════════════════════════════════
    # CHARACTER / PROGRESSION
    # ══════════════════════════════════════════════════════════════════════

    def character_stats(self) -> dict:
        self._require("player")
        p = self.player
        skills = {
            st.value: {"level": p.skills.level(st), "xp": p.skills.get(st).xp}
            for st in __import__("core.constants", fromlist=["SkillType"]).SkillType
        }
        return {
            "name":          p.name,
            "combat_level":  p.skills.combat_level,
            "hp":            p.hp,
            "max_hp":        p.max_hp,
            "active_style":  p.active_style.value,
            "special_bar":   p.special_bar,
            "is_ironman":    getattr(p, "is_ironman", False),
            "skills":        skills,
            "equipped":      self._inventory_manager.equipped_summary(),
        }

    def progression_stats(self) -> dict:
        self._require("player")
        return {
            "global":        self._progression.global_stats(),
            "summary":       self._progression.summary(),
            "run_history":   [
                {
                    "zone":    r.zone_id,
                    "rooms":   r.rooms_cleared,
                    "boss":    r.boss_killed,
                    "died":    r.player_died,
                    "drops":   r.drops_count,
                    "gold":    r.gold_earned,
                }
                for r in self._progression.run_history()[-10:]  # last 10
            ],
        }

    def bestiary_list(self, filter: str = "discovered") -> list[dict]:
        self._require("player")
        if filter == "studied":
            entries = self._bestiary.studied_entries()
        elif filter == "all":
            entries = self._bestiary.all_entries()
        else:
            entries = self._bestiary.discovered_entries()
        return [
            {
                "monster_id": e.monster_id,
                "name":       e.name,
                "kills":      e.kill_count,
                "is_boss":    e.is_boss,
                "is_studied": e.is_studied,
                "zones_seen": e.zones_seen,
                "weaknesses": e.weakness_summary(),
                "lore":       e.lore if e.is_studied else None,
            }
            for e in entries
        ]

    def bestiary_stats(self) -> dict:
        self._require("player")
        return self._bestiary.completion_stats()

    # ══════════════════════════════════════════════════════════════════════
    # SAVE / LOAD
    # ══════════════════════════════════════════════════════════════════════

    def save(self, filepath: str) -> dict:
        self._require("player")
        from data.items import WEAPONS, ARMORS
        p = self.player
        eq = p.equipment

        def _item_to_dict(item) -> dict | None:
            if item is None:
                return None
            return {"id": item.id, "durability": item.durability}

        data = {
            "player": {
                "name":         p.name,
                "active_style": p.active_style.value,
                "special_bar":  p.special_bar,
                "is_ironman":   getattr(p, "is_ironman", False),
                "skills":       {
                    st.value: {"xp": p.skills.get(st).xp, "level": p.skills.level(st)}
                    for st in __import__("core.constants", fromlist=["SkillType"]).SkillType
                },
                "equipment": {
                    "weapon": _item_to_dict(eq.weapon),
                    "head":   _item_to_dict(eq.head),
                    "body":   _item_to_dict(eq.body),
                    "legs":   _item_to_dict(eq.legs),
                    "hands":  _item_to_dict(eq.hands),
                    "feet":   _item_to_dict(eq.feet),
                    "shield": _item_to_dict(eq.shield),
                },
                "inventory": [
                    {"id": i.id, "quantity": i.quantity,
                     "doses": getattr(i, "doses", 1)}
                    for i in p.inventory.items
                ],
                "zone_currency": p.inventory.zone_currency,
                "gold":          p.inventory.gold,
            },
            "progression": self._progression.to_dict(),
            "bestiary": {
                mid: {
                    "kill_count":   e.kill_count,
                    "is_discovered": e.is_discovered,
                    "is_studied":   e.is_studied,
                    "zones_seen":   e.zones_seen,
                }
                for mid, e in self._bestiary._entries.items()
            },
            "hub": {
                "phase":    self.hub.phase,
                "storage":  self.hub.storage(),
                "buildings": {
                    bid: {
                        "upgrade_level":     b.upgrade_level,
                        "ticks_accumulated": b.ticks_accumulated,
                    }
                    for bid, b in self.hub._buildings.items()
                },
            },
        }
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        return {"success": True, "filepath": filepath}

    def load(self, filepath: str) -> dict:
        if not os.path.exists(filepath):
            return {"success": False, "reason": f"File not found: {filepath}"}
        try:
            with open(filepath) as f:
                data = json.load(f)
            self._restore_from_dict(data)
            return {"success": True, "name": self.player.name}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    # ══════════════════════════════════════════════════════════════════════
    # INTERNAL
    # ══════════════════════════════════════════════════════════════════════

    def _require(self, what: str) -> None:
        if what == "player" and self.player is None:
            raise RuntimeError("No character loaded. Call create_character() or load() first.")
        if what == "hub" and self.hub is None:
            raise RuntimeError("Hub not initialised.")
        if what == "dungeon" and self._runner is None:
            raise RuntimeError("Not in a dungeon. Call enter_zone() first.")
        if what == "combat" and self._engine is None:
            raise RuntimeError("Not in combat. Call start_combat() first.")

    def _finalize_run(self) -> None:
        if self._runner:
            gold = sum(d.get("gold", 0) for d in self._runner.run.drops_this_run)
            curr = sum(d.get("zone_currency", 0) for d in self._runner.run.drops_this_run)
            self._progression.finalize_run(
                self._runner.run,
                gold_earned=gold,
                currency_earned=curr,
            )
        self._runner = None
        self._engine = None
        self.state   = GameState.HUB

    def _restore_from_dict(self, data: dict) -> None:
        from copy import deepcopy
        from entities.player import Player
        from entities.skill import SkillSet
        from systems.progression import ProgressionManager
        from systems.bestiary import Bestiary, BestiaryEntry
        from systems.hub import Hub, BuiltBuilding
        from systems.inventory_manager import InventoryManager
        from systems.gathering import GatheringEngine
        from core.constants import SkillType, CombatStyle
        from data.items import WEAPONS, ARMORS, CONSUMABLES

        pd = data["player"]

        # Reconstruct player
        player = Player(name=pd["name"])
        player.active_style = CombatStyle(pd["active_style"])
        player.special_bar  = pd.get("special_bar", 0)
        player.is_ironman   = pd.get("is_ironman", False)

        # Skills
        for st in SkillType:
            sd = pd["skills"].get(st.value, {})
            skill = player.skills.get(st)
            skill.xp    = sd.get("xp", 0)
            skill.level = sd.get("level", 1)

        # Equipment
        for slot, entry in pd["equipment"].items():
            if entry is None:
                continue
            item = deepcopy(WEAPONS.get(entry["id"]) or ARMORS.get(entry["id"]))
            if item:
                item.durability = entry.get("durability", item.max_durability)
                setattr(player.equipment, slot, item)

        # Inventory
        for entry in pd["inventory"]:
            item = deepcopy(
                WEAPONS.get(entry["id"]) or ARMORS.get(entry["id"])
                or CONSUMABLES.get(entry["id"])
            )
            if item:
                item.quantity = entry.get("quantity", 1)
                if hasattr(item, "doses"):
                    item.doses = entry.get("doses", item.doses)
                player.inventory.add(item)

        player.inventory.zone_currency = pd.get("zone_currency", 0)
        player.inventory.gold          = pd.get("gold", 0)
        player._max_hp = player._calc_max_hp()
        player._hp     = player._max_hp

        self.player = player

        # Progression
        self._progression = ProgressionManager.from_dict(data.get("progression", {}))

        # Bestiary
        bestiary = Bestiary()
        for mid, bd in data.get("bestiary", {}).items():
            entry = bestiary._get_or_create(mid)
            entry.kill_count    = bd.get("kill_count", 0)
            entry.is_discovered = bd.get("is_discovered", False)
            entry.is_studied    = bd.get("is_studied", False)
            entry.zones_seen    = bd.get("zones_seen", [])
        self._bestiary = bestiary

        # Hub
        hub = Hub(player)
        hd  = data.get("hub", {})
        hub._stored_resources = hd.get("storage", {})
        for bid, bdata in hd.get("buildings", {}).items():
            b = BuiltBuilding(
                building_id=bid,
                upgrade_level=bdata.get("upgrade_level", 0),
                ticks_accumulated=bdata.get("ticks_accumulated", 0),
            )
            hub._buildings[bid] = b
        self.hub = hub

        self._inventory_manager = InventoryManager(player)
        self._gathering_engine  = GatheringEngine(player.skills, player.inventory)
        self.state = GameState.HUB
