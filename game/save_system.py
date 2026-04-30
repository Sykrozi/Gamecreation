"""
Save/load system — 3 JSON slots stored in game/saves/.
Public API used by main.py:
  save_game(player, slot)
  load_game(slot)          -> Character | None
  all_slots_info()         -> list[dict | None]
  draw_save_load_screen(screen, fonts, mode, slots_info, selected)
  handle_save_load_click(event, mode, slots_info, selected) -> dict | None
"""

import json
import os
import sys
from datetime import datetime

import pygame

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE      = os.path.dirname(os.path.abspath(__file__))
_SAVES_DIR = os.path.join(_HERE, "saves")


def _slot_path(slot: int) -> str:
    os.makedirs(_SAVES_DIR, exist_ok=True)
    return os.path.join(_SAVES_DIR, f"slot_{slot}.json")


# ---------------------------------------------------------------------------
# Colours (matching main.py palette)
# ---------------------------------------------------------------------------

_BG     = ( 12,   8,  20)
_WHITE  = (255, 255, 255)
_GREY   = ( 70,  70,  80)
_DGREY  = ( 20,  18,  30)
_GOLD   = (255, 200,  50)
_GREEN  = ( 30, 180,  50)
_RED    = (200,  30,  30)
_TEAL   = ( 40, 180, 160)
_PURPLE = (130,  60, 200)
_LBLUE  = ( 60, 120, 210)

# ---------------------------------------------------------------------------
# Layout (fixed for 800×520 window)
# ---------------------------------------------------------------------------

_W, _H = 800, 520

# Panel
_PX, _PY, _PW, _PH = 90, 50, 620, 410   # panel left/top/w/h

# Slots
_SLOT_X  = _PX + 14
_SLOT_W  = _PW - 28
_SLOT_H  = 78
_SLOT_Y0 = _PY + 60
_SLOT_GAP = 8

# Buttons (confirm / cancel)
_BTN_Y      = _PY + _PH - 54
_BTN_CONF   = (_PX + 110, _BTN_Y, 160, 42)
_BTN_CANCEL = (_PX + 350, _BTN_Y, 160, 42)


def _slot_rect(i: int) -> pygame.Rect:
    return pygame.Rect(_SLOT_X, _SLOT_Y0 + i * (_SLOT_H + _SLOT_GAP), _SLOT_W, _SLOT_H)


# ---------------------------------------------------------------------------
# Serialise / deserialise
# ---------------------------------------------------------------------------

def save_game(player, slot: int = 0) -> bool:
    """Serialise *player* to JSON at *slot*. Returns True on success."""
    cs = player.combat_skills
    data = {
        "version":    2,
        "name":       player.name,
        "level":      player.level,
        "xp":         player.xp,
        "xp_to_next": player.xp_to_next,
        "base_hp":    player._base_hp,
        "base_atk":   player._base_atk,
        "base_def":   player._base_def,
        "speed":      player.speed,
        "gold":       getattr(player, "gold", 0),
        "play_time":  getattr(player, "_play_time", 0.0),
        "combat_skills": {
            "attack":   {"level": cs.attack.level,   "xp": cs.attack.xp},
            "defense":  {"level": cs.defense.level,  "xp": cs.defense.xp},
            "strength": {"level": cs.strength.level, "xp": cs.strength.xp},
        },
        "gathering_skills": {
            sid: sk.xp for sid, sk in player.gathering.all().items()
        },
        "inventory": [
            {"name": it.name, "kind": it.kind, "value": it.value}
            for it in player.inventory
        ],
        "equipped_weapon": player._wpn.name if player._wpn else None,
        "equipped_armor":  player._arm.name if player._arm else None,
        "saved_at":   datetime.now().isoformat(timespec="seconds"),
    }
    try:
        with open(_slot_path(slot), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except OSError:
        return False


def load_game(slot: int = 0):
    """Deserialise from *slot*. Returns a Character or None if empty/corrupt."""
    path = _slot_path(slot)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None

    # Import lazily to avoid circular imports at module level
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    from entities.character import Character, Item

    p = Character(
        name        = data["name"],
        max_hp      = data["base_hp"],
        attack      = data["base_atk"],
        defense     = data["base_def"],
        speed       = data.get("speed", 10),
        sprite_file = "warrior.png",
        sprite_size = (128, 128),
    )
    p.level      = data["level"]
    p.xp         = data["xp"]
    p.xp_to_next = data["xp_to_next"]
    p.gold       = data.get("gold", 0)
    p._play_time = data.get("play_time", 0.0)

    # Restore combat skills
    cs_data = data.get("combat_skills", {})
    for skill_name in ("attack", "defense", "strength"):
        sd    = cs_data.get(skill_name, {})
        skill = getattr(p.combat_skills, skill_name)
        skill.level = sd.get("level", 1)
        skill.xp    = sd.get("xp", 0)

    # Restore gathering skills (XP only; level is computed from XP)
    gs_data = data.get("gathering_skills", {})
    for sid, xp in gs_data.items():
        sk = p.gathering.get(sid)
        if sk:
            sk.xp = xp

    # Restore inventory + equipment
    equipped_wpn = data.get("equipped_weapon")
    equipped_arm = data.get("equipped_armor")
    for it_d in data.get("inventory", []):
        it = Item(it_d["name"], it_d["kind"], it_d["value"])
        p.add_item(it)
        if it.kind == "weapon" and it.name == equipped_wpn:
            p._wpn = it
        if it.kind == "armor" and it.name == equipped_arm:
            p._arm = it

    return p


# ---------------------------------------------------------------------------
# Slot metadata
# ---------------------------------------------------------------------------

def slot_info(slot: int) -> dict | None:
    path = _slot_path(slot)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        cs = data.get("combat_skills", {})
        return {
            "slot":      slot,
            "name":      data.get("name", "?"),
            "level":     data.get("level", 1),
            "gold":      data.get("gold", 0),
            "play_time": data.get("play_time", 0.0),
            "saved_at":  data.get("saved_at", ""),
            "cs_atk":    cs.get("attack",   {}).get("level", 1),
            "cs_def":    cs.get("defense",  {}).get("level", 1),
            "cs_str":    cs.get("strength", {}).get("level", 1),
        }
    except (OSError, json.JSONDecodeError, KeyError):
        return None


def all_slots_info() -> list:
    return [slot_info(i) for i in range(3)]


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_time(seconds: float) -> str:
    s   = int(seconds)
    h   = s // 3600
    m   = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}"


# ---------------------------------------------------------------------------
# Draw
# ---------------------------------------------------------------------------

def draw_save_load_screen(screen, fonts: dict,
                          mode: str, slots_info: list, selected: int) -> None:
    """
    Draws the save/load overlay on *screen*.
    mode: 'save' | 'load'
    slots_info: list of 3 items, each None or dict
    selected: active slot index (0-2), or -1
    """
    sm = fonts["sm"]
    md = fonts["md"]
    lg = fonts["lg"]

    # dim overlay
    dim = pygame.Surface((_W, _H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 200))
    screen.blit(dim, (0, 0))

    panel = pygame.Rect(_PX, _PY, _PW, _PH)
    pygame.draw.rect(screen, _DGREY, panel, border_radius=10)
    pygame.draw.rect(screen, _GREY,  panel, 2, border_radius=10)

    title_str = "SAVE GAME" if mode == "save" else "LOAD GAME"
    title_col = _GOLD if mode == "save" else _TEAL
    t = lg.render(title_str, True, title_col)
    screen.blit(t, t.get_rect(center=(_W // 2, _PY + 30)))

    mx, my = pygame.mouse.get_pos()

    # Slot cards
    for i, info in enumerate(slots_info):
        rect   = _slot_rect(i)
        is_sel = (i == selected)
        hov    = rect.collidepoint(mx, my)

        bg  = (48, 36, 72) if is_sel else ((30, 26, 46) if hov else (18, 15, 30))
        brd = _PURPLE if is_sel else (_GREY if hov else (40, 40, 55))
        pygame.draw.rect(screen, bg,  rect, border_radius=7)
        pygame.draw.rect(screen, brd, rect, 2, border_radius=7)

        slot_lbl = sm.render(f"Slot {i + 1}", True, (110, 90, 150))
        screen.blit(slot_lbl, (rect.x + 10, rect.y + 6))

        if info is None:
            empty_t = md.render("(empty)", True, (50, 50, 70))
            screen.blit(empty_t, empty_t.get_rect(center=rect.center))
        else:
            name_t  = md.render(f"{info['name']}  Lv.{info['level']}", True, _WHITE)
            gold_t  = sm.render(f"Gold: {info['gold']}", True, _GOLD)
            skill_t = sm.render(
                f"ATK Lv.{info['cs_atk']}  DEF Lv.{info['cs_def']}  STR Lv.{info['cs_str']}",
                True, _TEAL)
            time_t  = sm.render(_fmt_time(info["play_time"]), True, _GREY)
            date_t  = sm.render(info["saved_at"][:16].replace("T", "  "), True, (80, 80, 95))

            screen.blit(name_t,  (rect.x + 10,  rect.y + 24))
            screen.blit(gold_t,  (rect.x + 10,  rect.y + 50))
            screen.blit(skill_t, (rect.x + 115, rect.y + 50))
            screen.blit(time_t,  (rect.right - time_t.get_width()  - 10, rect.y + 24))
            screen.blit(date_t,  (rect.right - date_t.get_width()  - 10, rect.y + 50))

    # Buttons
    can_confirm = (selected >= 0
                   and (mode == "save" or slots_info[selected] is not None))

    for (bx, by, bw, bh), label, active, acc in [
        (_BTN_CONF,   "Save" if mode == "save" else "Load", can_confirm, _GREEN),
        (_BTN_CANCEL, "Cancel",                              True,        _GREY),
    ]:
        br = pygame.Rect(bx, by, bw, bh)
        if active:
            bg_c  = (22, 72, 26) if acc == _GREEN else (38, 38, 50)
            brd_c = acc
            lc    = _WHITE
            if br.collidepoint(mx, my):
                bg_c = tuple(min(255, c + 22) for c in bg_c)
        else:
            bg_c  = (16, 16, 24)
            brd_c = (38, 38, 50)
            lc    = (55, 55, 68)
        pygame.draw.rect(screen, bg_c,  br, border_radius=7)
        pygame.draw.rect(screen, brd_c, br, 2, border_radius=7)
        bt = md.render(label, True, lc)
        screen.blit(bt, bt.get_rect(center=br.center))

    tip = sm.render("Press ESC to cancel", True, (50, 50, 68))
    screen.blit(tip, tip.get_rect(center=(_W // 2, panel.bottom + 16)))


# ---------------------------------------------------------------------------
# Event handling
# ---------------------------------------------------------------------------

def handle_save_load_click(event, mode: str,
                           slots_info: list, selected: int) -> dict | None:
    """
    Returns one of:
      {'type': 'select',  'slot': i}
      {'type': 'confirm', 'slot': i}
      {'type': 'close'}
    or None for unhandled events.
    """
    if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
        return None

    pos = event.pos

    for i in range(3):
        if _slot_rect(i).collidepoint(pos):
            return {"type": "select", "slot": i}

    bx, by, bw, bh = _BTN_CONF
    if pygame.Rect(bx, by, bw, bh).collidepoint(pos):
        can_confirm = (selected >= 0
                       and (mode == "save" or slots_info[selected] is not None))
        if can_confirm:
            return {"type": "confirm", "slot": selected}
        return None

    bx, by, bw, bh = _BTN_CANCEL
    if pygame.Rect(bx, by, bw, bh).collidepoint(pos):
        return {"type": "close"}

    return None
