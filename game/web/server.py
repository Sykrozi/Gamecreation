"""
Flask web server — exposes GameInterface as a REST API.
Run: python web/server.py  (from game/ directory)
"""
from __future__ import annotations

import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, request, session, render_template, send_from_directory
from flask_cors import CORS

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("GAME_SECRET", "pixel-rpg-secret-key-2024")
CORS(app, supports_credentials=True)

# ─── Session store ────────────────────────────────────────────────────────────

_sessions: dict[str, object] = {}


def _get_gi():
    sid = session.get("game_id")
    if sid and sid in _sessions:
        return _sessions[sid]
    return None


def _require_gi():
    gi = _get_gi()
    if gi is None:
        from flask import abort
        abort(400, "No active game session. Create a character first.")
    return gi


def _new_gi():
    from ui.game_interface import GameInterface
    sid = str(uuid.uuid4())
    session["game_id"] = sid
    gi = GameInterface()
    _sessions[sid] = gi
    return gi


# ─── Static / HTML ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ─── Character creation ───────────────────────────────────────────────────────

@app.route("/api/templates")
def list_templates():
    from ui.game_interface import GameInterface
    gi = GameInterface()
    return jsonify(gi.list_templates())


@app.route("/api/create", methods=["POST"])
def create_character():
    data = request.get_json(force=True)
    gi = _new_gi()
    result = gi.create_character(data.get("name", "Hero"), data.get("template", "warrior"))
    if result.get("success"):
        result["state"] = gi.state.value
    return jsonify(result)


# ─── State ────────────────────────────────────────────────────────────────────

@app.route("/api/state")
def get_state():
    gi = _require_gi()
    p = gi.player
    return jsonify({
        "state":        gi.state.value,
        "player_name":  p.name if p else None,
        "hp":           p.hp if p else None,
        "max_hp":       p.max_hp if p else None,
        "combat_level": p.skills.combat_level if p else None,
        "active_style": p.active_style.value if p else None,
        "is_ironman":   getattr(p, "is_ironman", False) if p else False,
        "special_bar":  p.special_bar if p else 0,
    })


# ─── Hub ──────────────────────────────────────────────────────────────────────

@app.route("/api/hub")
def hub_status():
    gi = _require_gi()
    return jsonify(gi.hub_status())


@app.route("/api/hub/tick", methods=["POST"])
def hub_tick():
    gi = _require_gi()
    data = request.get_json(force=True) or {}
    return jsonify(gi.hub_tick(int(data.get("ticks", 1))))


@app.route("/api/hub/build", methods=["POST"])
def hub_build():
    gi = _require_gi()
    data = request.get_json(force=True)
    return jsonify(gi.hub_build(data["building_id"]))


@app.route("/api/hub/upgrade", methods=["POST"])
def hub_upgrade():
    gi = _require_gi()
    data = request.get_json(force=True)
    return jsonify(gi.hub_upgrade(data["building_id"]))


@app.route("/api/hub/buildings")
def hub_buildings():
    gi = _require_gi()
    return jsonify(gi.hub_available_buildings())


# ─── Zones ────────────────────────────────────────────────────────────────────

@app.route("/api/zones")
def list_zones():
    gi = _require_gi()
    return jsonify(gi.list_zones())


# ─── Dungeon ──────────────────────────────────────────────────────────────────

@app.route("/api/dungeon/enter", methods=["POST"])
def dungeon_enter():
    gi = _require_gi()
    data = request.get_json(force=True)
    result = gi.enter_zone(data["zone_id"], float(data.get("luck", 0.0)))
    if result.get("success"):
        result["state"] = gi.state.value
    return jsonify(result)


@app.route("/api/dungeon/room")
def dungeon_room():
    gi = _require_gi()
    return jsonify(gi.current_room())


@app.route("/api/dungeon/combat/start", methods=["POST"])
def combat_start():
    gi = _require_gi()
    result = gi.start_combat()
    if result.get("success"):
        result["state"] = gi.state.value
    return jsonify(result)


@app.route("/api/dungeon/combat/action", methods=["POST"])
def combat_action():
    gi = _require_gi()
    data = request.get_json(force=True)
    result = gi.combat_action(data["action"], item_id=data.get("item_id"))
    result["state"] = gi.state.value
    return jsonify(result)


@app.route("/api/dungeon/combat/actions")
def combat_actions():
    gi = _require_gi()
    return jsonify(gi.get_combat_actions())


@app.route("/api/dungeon/combat/summary")
def combat_summary():
    gi = _require_gi()
    return jsonify(gi.combat_summary())


@app.route("/api/dungeon/skill", methods=["POST"])
def skill_room():
    gi = _require_gi()
    data = request.get_json(force=True)
    result = gi.skill_room_attempt(float(data.get("precision", 0.5)))
    result["state"] = gi.state.value
    return jsonify(result)


@app.route("/api/dungeon/loot", methods=["POST"])
def loot_room():
    gi = _require_gi()
    result = gi.collect_loot_room()
    result["state"] = gi.state.value
    return jsonify(result)


@app.route("/api/dungeon/trap", methods=["POST"])
def trap_event():
    gi = _require_gi()
    result = gi.handle_trap()
    result["state"] = gi.state.value
    return jsonify(result)


@app.route("/api/dungeon/treasure", methods=["POST"])
def treasure_event():
    gi = _require_gi()
    result = gi.handle_treasure()
    result["state"] = gi.state.value
    return jsonify(result)


@app.route("/api/dungeon/merchant")
def get_merchant():
    gi = _require_gi()
    return jsonify(gi.get_merchant_shop())


@app.route("/api/dungeon/merchant/buy", methods=["POST"])
def merchant_buy():
    gi = _require_gi()
    data = request.get_json(force=True)
    return jsonify(gi.buy_from_merchant(data["item_id"]))


@app.route("/api/dungeon/merchant/dismiss", methods=["POST"])
def merchant_dismiss():
    gi = _require_gi()
    result = gi.dismiss_merchant()
    result["state"] = gi.state.value
    return jsonify(result)


@app.route("/api/dungeon/abandon", methods=["POST"])
def dungeon_abandon():
    gi = _require_gi()
    result = gi.abandon_run()
    result["state"] = gi.state.value
    return jsonify(result)


# ─── Inventory ────────────────────────────────────────────────────────────────

@app.route("/api/inventory")
def inventory():
    gi = _require_gi()
    return jsonify(gi.inventory_view())


@app.route("/api/inventory/equip", methods=["POST"])
def equip():
    gi = _require_gi()
    data = request.get_json(force=True)
    return jsonify(gi.equip_item(data["item_id"]))


@app.route("/api/inventory/unequip", methods=["POST"])
def unequip():
    gi = _require_gi()
    data = request.get_json(force=True)
    return jsonify(gi.unequip_slot(data["slot"]))


@app.route("/api/inventory/use", methods=["POST"])
def use_item():
    gi = _require_gi()
    data = request.get_json(force=True)
    return jsonify(gi.use_item(data["item_id"]))


@app.route("/api/inventory/drop", methods=["POST"])
def drop_item():
    gi = _require_gi()
    data = request.get_json(force=True)
    return jsonify(gi.drop_item(data["item_id"]))


@app.route("/api/inventory/compare")
def compare_item():
    gi = _require_gi()
    return jsonify(gi.compare_item(request.args.get("item_id", "")))


@app.route("/api/inventory/info")
def item_info():
    gi = _require_gi()
    return jsonify(gi.item_info(request.args.get("item_id", "")))


@app.route("/api/inventory/sort", methods=["POST"])
def sort_inventory():
    gi = _require_gi()
    data = request.get_json(force=True) or {}
    return jsonify(gi.sort_inventory(data.get("by", "type")))


# ─── Character / Progression ─────────────────────────────────────────────────

@app.route("/api/character")
def character_stats():
    gi = _require_gi()
    return jsonify(gi.character_stats())


@app.route("/api/progression")
def progression_stats():
    gi = _require_gi()
    return jsonify(gi.progression_stats())


@app.route("/api/bestiary")
def bestiary():
    gi = _require_gi()
    filter_type = request.args.get("filter", "discovered")
    return jsonify(gi.bestiary_list(filter_type))


# ─── Save / Load ──────────────────────────────────────────────────────────────

@app.route("/api/save", methods=["POST"])
def save_game():
    gi = _require_gi()
    data = request.get_json(force=True) or {}
    filepath = data.get("filepath", "savegame.json")
    return jsonify(gi.save(filepath))


@app.route("/api/load", methods=["POST"])
def load_game():
    data = request.get_json(force=True) or {}
    filepath = data.get("filepath", "savegame.json")
    gi = _new_gi()
    result = gi.load(filepath)
    if result.get("success"):
        result["state"] = gi.state.value
    return jsonify(result)


# ─── Error handlers ───────────────────────────────────────────────────────────

@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": str(e)}), 400


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": str(e)}), 500


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting Pixel RPG web server at http://localhost:5000")
    app.run(debug=True, port=5000, host="0.0.0.0")
