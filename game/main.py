import sys
import os
import random
from enum import Enum, auto

import pygame

from entities.character import Character, Item, make_health_potion
from zones import ALL_ZONES, zones_available_for_level
from systems.combat import CombatSystem, CombatState, Action
import save_system

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
W, H   = 800, 520
FPS    = 60
ASSETS = os.path.join(os.path.dirname(__file__), "assets")

BG     = ( 12,   8,  20)
WHITE  = (255, 255, 255)
GREY   = ( 70,  70,  80)
DGREY  = ( 20,  18,  30)
RED    = (200,  30,  30)
GREEN  = ( 30, 180,  50)
YELLOW = (220, 200,  50)
ORANGE = (230, 120,  30)
LBLUE  = ( 60, 120, 210)
PURPLE = (130,  60, 200)
GOLD   = (255, 200,  50)
TEAL   = ( 40, 180, 160)

SK_ATK_COL = (230, 110,  40)
SK_DEF_COL = ( 60, 130, 220)
SK_STR_COL = (210,  50,  50)

Y_BASE_BTN = H - 41
Y_ABIL_BTN = H - 73
H_BASE_BTN = 38
H_ABIL_BTN = 26


class GameState(Enum):
    CHAR_CREATE      = auto()
    ZONE_SELECT      = auto()
    COMBAT           = auto()
    TRANSITION       = auto()
    WIN              = auto()
    LOSE             = auto()
    SKILLS_SCREEN    = auto()
    SAVE_SCREEN      = auto()
    LOAD_SCREEN      = auto()
    HUB              = auto()
    GATHERING        = auto()
    GATHERING_RESULT = auto()


_GATHERING_META = {
    "mining"     : {"label": "Mining",      "color": (170, 170, 180)},
    "woodcutting": {"label": "Woodcutting", "color": (100, 180,  60)},
    "fishing"    : {"label": "Fishing",     "color": ( 40, 180, 160)},
    "farming"    : {"label": "Farming",     "color": (160, 220,  80)},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scale(img, size):
    return pygame.transform.scale(img, size)

def _flip_h(img):
    return pygame.transform.flip(img, True, False)


class Button:
    def __init__(self, rect, label, color, hover):
        self.rect  = pygame.Rect(rect)
        self.label = label
        self.color = color
        self.hover = hover

    def draw(self, surf, font):
        mx, my = pygame.mouse.get_pos()
        c = self.hover if self.rect.collidepoint(mx, my) else self.color
        pygame.draw.rect(surf, c, self.rect, border_radius=7)
        pygame.draw.rect(surf, WHITE, self.rect, 2, border_radius=7)
        t = font.render(self.label, True, WHITE)
        surf.blit(t, t.get_rect(center=self.rect.center))

    def clicked(self, event):
        return (event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and self.rect.collidepoint(event.pos))


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------

class Game:

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Pixel RPG")
        self.clock  = pygame.time.Clock()

        self.font_sm = pygame.font.SysFont("consolas", 14)
        self.font_md = pygame.font.SysFont("consolas", 18)
        self.font_lg = pygame.font.SysFont("consolas", 28, bold=True)
        self.font_xl = pygame.font.SysFont("consolas", 42, bold=True)

        self._fonts = {"sm": self.font_sm, "md": self.font_md,
                       "lg": self.font_lg, "xl": self.font_xl}

        self._load_sprites()
        self._init_buttons()
        self._to_char_create()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _load_sprites(self):
        names = ("warrior", "goblin", "archer", "mage", "boss")
        self.sprites = {
            n: pygame.image.load(os.path.join(ASSETS, f"{n}.png")).convert_alpha()
            for n in names
        }
        self.bg_dungeon = pygame.transform.scale(
            pygame.image.load(os.path.join(ASSETS, "bg_dungeon.png")).convert(),
            (W, 390),
        )

    def _init_buttons(self):
        y = Y_BASE_BTN
        h = H_BASE_BTN
        self.btn_attack    = Button((165, y, 110, h), "Attack",  (150, 25,  25), (210, 55,  55))
        self.btn_defend    = Button((285, y, 110, h), "Defend",  ( 25, 75, 155), ( 55,115, 210))
        self.btn_items     = Button((405, y, 110, h), "Items",   ( 90, 50, 120), (140, 80, 170))
        self.btn_flee      = Button((525, y, 110, h), "Flee",    ( 65, 65,  65), (110,110, 110))

        self.btn_next      = Button((W//2-100, H//2+80,  200, 46), "Continue",
                                    (35,110, 35), (60,160, 60))
        self.btn_end_main  = Button((W//2-100, H//2+70,  200, 46), "Choose Zone",
                                    (35,110, 35), (60,160, 60))
        self.btn_new_char  = Button((W//2-85,  H//2+125, 170, 34), "New Character",
                                    (40, 40, 80), (65, 65,120))
        self.btn_begin     = Button((W//2-110, H-100,    220, 46), "Begin Adventure",
                                    (35,110, 35), (60,160, 60))
        self.btn_inv_close = Button((W//2-60,  H//2+114, 120, 36), "Close",
                                    (65, 65,  65), (110,110,110))

        # Zone select extras (bottom corners)
        self.btn_skills    = Button((W-140, H-44, 130, 34), "Skills",
                                    (50, 30, 90), (80, 50, 140))
        self.btn_save      = Button((10, H-44, 120, 34), "Save",
                                    (28, 68, 28), (50, 100, 50))

        # Skills screen back
        self.btn_skills_back = Button((W//2-80, H-50, 160, 36), "Back",
                                      (50, 50, 60), (80, 80, 90))

        # Char create — load game
        self.btn_load_game = Button((W//2-80, H-50, 160, 36), "Load Game",
                                    (28, 50, 90), (50, 80, 140))

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _to_char_create(self):
        self.state           = GameState.CHAR_CREATE
        self.player          = None
        self.selected_zone   = None
        self.encounters      = []
        self.encounter_index = 0
        self.combat          = None
        self.log             = []
        self.trans_header    = ""
        self.trans_xp        = ""
        self.shake_p         = 0
        self.shake_e         = 0
        self._show_inventory = False
        self._last_xp_gained = 0
        self._zone_xp_total  = 0
        self._zone_rects     = {}
        self._char_name      = "Hero"
        self._cursor_show    = True
        self._cursor_tick    = 0
        self._last_save_msg  = ""
        # Save/load screen state
        self._sv_mode        = "save"
        self._sv_selected    = 0
        self._sv_slots       = []
        self._sv_from        = GameState.CHAR_CREATE
        # Gathering / hub state
        self._hub_skill_btns = {}
        self._hub_btns       = {}
        self._result_applied = False
        self._result_btn     = None
        self._dt             = 0.0
        self._skills_from    = GameState.ZONE_SELECT

    def _to_zone_select(self):
        if self.player:
            self.player.full_reset()
        self.selected_zone   = None
        self.encounters      = []
        self.encounter_index = 0
        self.combat          = None
        self.log             = []
        self.trans_header    = ""
        self.trans_xp        = ""
        self._show_inventory = False
        self._last_xp_gained = 0
        self._zone_xp_total  = 0
        self._zone_rects     = {}
        self.state           = GameState.ZONE_SELECT

    def _to_hub(self):
        if self.player:
            self.player.full_reset()
        self.selected_zone   = None
        self.encounters      = []
        self.encounter_index = 0
        self.combat          = None
        self.log             = []
        self._result_applied = False
        self.state           = GameState.HUB

    def _new_player(self, name):
        self.player = Character(
            name=name, max_hp=120, attack=20, defense=6, speed=10,
            sprite_file="warrior.png", sprite_size=(128, 128),
        )
        self.player.add_item(make_health_potion())
        self.player.add_item(make_health_potion())

    def _start_dungeon(self, zone):
        self.player.full_reset()
        self.selected_zone   = zone
        self.encounters      = zone.build_encounter_list()
        self.encounter_index = 0
        self._last_xp_gained = 0
        self._zone_xp_total  = 0
        self._show_inventory = False
        self.log             = [f"Entered {zone.name}!"]
        self._begin_combat()

    def _begin_combat(self):
        enemy        = self.encounters[self.encounter_index]
        self.combat  = CombatSystem(self.player, enemy)
        total        = len(self.encounters)
        room_num     = self.encounter_index + 1
        tag          = " [BOSS]" if enemy.is_boss else ""
        self.log.append(f"Room {room_num}/{total}{tag}: {enemy.name}!")
        self.state   = GameState.COMBAT
        self.shake_p = self.shake_e = 0
        self.player.end_turn()

    # ------------------------------------------------------------------
    # Save / load helpers
    # ------------------------------------------------------------------

    def _enter_save(self):
        self._sv_mode     = "save"
        self._sv_selected = 0
        self._sv_slots    = save_system.all_slots_info()
        self._sv_from     = self.state
        self.state        = GameState.SAVE_SCREEN

    def _enter_load(self):
        self._sv_mode     = "load"
        self._sv_selected = 0
        self._sv_slots    = save_system.all_slots_info()
        self._sv_from     = self.state
        self.state        = GameState.LOAD_SCREEN

    def _handle_sl_events(self, events):
        """Shared handler for both SAVE_SCREEN and LOAD_SCREEN."""
        for e in events:
            result = save_system.handle_save_load_click(
                e, self._sv_mode, self._sv_slots, self._sv_selected)
            if result is None:
                continue
            if result["type"] == "select":
                self._sv_selected = result["slot"]
            elif result["type"] == "close":
                self.state = self._sv_from
            elif result["type"] == "confirm":
                slot = result["slot"]
                if self._sv_mode == "save":
                    ok = save_system.save_game(self.player, slot=slot)
                    self._last_save_msg = f"Saved to Slot {slot + 1}!" if ok else "Save failed."
                    self._sv_slots = save_system.all_slots_info()
                    self.state     = self._sv_from
                else:
                    loaded = save_system.load_game(slot=slot)
                    if loaded:
                        self.player = loaded
                        self._last_save_msg = f"Loaded from Slot {slot + 1}."
                        self._to_zone_select()

    def _draw_sl_screen(self):
        """Shared draw for both SAVE_SCREEN and LOAD_SCREEN."""
        self.screen.fill(BG)
        if self.player:
            hdr = self.font_sm.render(
                f"{self.player.name}  Lv.{self.player.level}"
                f"  Gold: {self.player.gold}  Time: {save_system._fmt_time(self.player._play_time)}",
                True, GREY)
            self.screen.blit(hdr, hdr.get_rect(center=(W // 2, 20)))
        save_system.draw_save_load_screen(
            self.screen, self._fonts,
            self._sv_mode, self._sv_slots, self._sv_selected)

    # ------------------------------------------------------------------
    # Ability button helpers
    # ------------------------------------------------------------------

    def _ability_button_rects(self):
        if not self.player:
            return []
        abilities = self.player.combat_skills.unlocked_abilities()
        if not abilities:
            return []
        n     = len(abilities)
        btn_w = min(128, (W - 60) // n)
        total = btn_w * n + 8 * (n - 1)
        sx    = (W - total) // 2
        return [
            (ab, pygame.Rect(sx + i * (btn_w + 8), Y_ABIL_BTN, btn_w, H_ABIL_BTN))
            for i, ab in enumerate(abilities)
        ]

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        while True:
            dt         = self.clock.tick(FPS) / 1000.0
            self._dt   = dt
            events     = pygame.event.get()

            # Track play time (pause during save/load overlays)
            if self.player and self.state not in (
                    GameState.SAVE_SCREEN, GameState.LOAD_SCREEN):
                self.player._play_time += dt

            # Idle gathering drops (hub only, skills lv 50+)
            if self.player and self.state == GameState.HUB:
                for _sid, name, qty in self.player.gathering.idle_tick(dt):
                    self.player.add_item(Item(name, "material", qty))

            for e in events:
                if e.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    if self._show_inventory:
                        self._show_inventory = False
                    elif self.state == GameState.SKILLS_SCREEN:
                        self.state = self._skills_from
                    elif self.state in (GameState.SAVE_SCREEN, GameState.LOAD_SCREEN):
                        self.state = self._sv_from
                    elif self.state in (GameState.GATHERING, GameState.GATHERING_RESULT):
                        self.player.gathering.clear_minigame()
                        self._result_applied = False
                        self.state = GameState.HUB
                    elif self.state == GameState.HUB:
                        pass  # ESC does nothing in hub
                    else:
                        pygame.quit(); sys.exit()

            self._cursor_tick += 1
            if self._cursor_tick >= 30:
                self._cursor_tick = 0
                self._cursor_show = not self._cursor_show

            dispatch = {
                GameState.CHAR_CREATE:      (self._handle_char_create,      self._draw_char_create),
                GameState.ZONE_SELECT:      (self._handle_zone_select,      self._draw_zone_select),
                GameState.COMBAT:           (self._handle_combat,            self._draw_combat),
                GameState.TRANSITION:       (self._handle_transition,        self._draw_transition),
                GameState.WIN:              (self._handle_end,               self._draw_end),
                GameState.LOSE:             (self._handle_end,               self._draw_end),
                GameState.SKILLS_SCREEN:    (self._handle_skills_screen,    self._draw_skills_screen),
                GameState.SAVE_SCREEN:      (self._handle_save_screen,      self._draw_save_screen),
                GameState.LOAD_SCREEN:      (self._handle_load_screen,      self._draw_load_screen),
                GameState.HUB:              (self._handle_hub,              self._draw_hub),
                GameState.GATHERING:        (self._handle_gathering,        self._draw_gathering),
                GameState.GATHERING_RESULT: (self._handle_gathering_result, self._draw_gathering_result),
            }
            handle, draw = dispatch[self.state]
            handle(events)
            draw()
            pygame.display.flip()

    # ------------------------------------------------------------------
    # CHAR CREATE
    # ------------------------------------------------------------------

    def _handle_char_create(self, events):
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_BACKSPACE:
                    self._char_name = self._char_name[:-1]
                elif e.key == pygame.K_RETURN:
                    self._confirm_char(); return
                elif e.unicode.isprintable() and len(self._char_name) < 16:
                    self._char_name += e.unicode
            if self.btn_begin.clicked(e):
                self._confirm_char(); return
            if self.btn_load_game.clicked(e):
                self._enter_load(); return

    def _confirm_char(self):
        name = self._char_name.strip() or "Hero"
        self._new_player(name)
        self._to_zone_select()

    def _draw_char_create(self):
        self.screen.fill(BG)

        title = self.font_xl.render("CHARACTER CREATION", True, ORANGE)
        self.screen.blit(title, title.get_rect(center=(W // 2, 50)))

        img = _scale(self.sprites["warrior"], (128, 128))
        self.screen.blit(img, img.get_rect(center=(W // 2, 185)))

        cls_lbl = self.font_md.render("Class: Warrior", True, YELLOW)
        self.screen.blit(cls_lbl, cls_lbl.get_rect(center=(W // 2, 258)))

        name_hint = self.font_sm.render("Enter your name:", True, GREY)
        self.screen.blit(name_hint, name_hint.get_rect(center=(W // 2, 288)))

        box = pygame.Rect(W // 2 - 150, 304, 300, 36)
        pygame.draw.rect(self.screen, DGREY, box)
        pygame.draw.rect(self.screen, LBLUE, box, 2, border_radius=5)
        cursor = "|" if self._cursor_show else " "
        name_t = self.font_md.render(self._char_name + cursor, True, WHITE)
        self.screen.blit(name_t, name_t.get_rect(center=box.center))

        for i, line in enumerate([
            "Starting stats:",
            "  HP: 120   ATK: 20   DEF: 6   SPD: 10",
            "  Items: 2x Health Potion",
        ]):
            t = self.font_sm.render(line, True, GREY if i == 0 else WHITE)
            self.screen.blit(t, t.get_rect(center=(W // 2, 362 + i * 18)))

        self.btn_begin.draw(self.screen, self.font_md)
        self.btn_load_game.draw(self.screen, self.font_md)

        if self._last_save_msg:
            msg_t = self.font_sm.render(self._last_save_msg, True, TEAL)
            self.screen.blit(msg_t, msg_t.get_rect(center=(W // 2, H - 16)))

    # ------------------------------------------------------------------
    # ZONE SELECT
    # ------------------------------------------------------------------

    def _handle_zone_select(self, events):
        for e in events:
            if self.btn_skills.clicked(e):
                self._skills_from = GameState.ZONE_SELECT
                self.state = GameState.SKILLS_SCREEN
                return
            if self.btn_save.clicked(e):
                self._enter_save(); return
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for zone_id, rect in self._zone_rects.items():
                    if rect.collidepoint(e.pos):
                        self._start_dungeon(ALL_ZONES[zone_id])
                        return

    def _draw_zone_select(self):
        self._zone_rects.clear()
        self.screen.fill(BG)

        title = self.font_lg.render("Choose Your Dungeon", True, GOLD)
        self.screen.blit(title, title.get_rect(center=(W // 2, 32)))

        card_w  = 420
        card_h  = 76
        gap     = 8
        start_y = 58
        avail   = {z.zone_id for z in zones_available_for_level(self.player.level)}

        for i, zone in enumerate(ALL_ZONES):
            y         = start_y + i * (card_h + gap)
            rect      = pygame.Rect(W // 2 - card_w // 2, y, card_w, card_h)
            is_locked = zone.zone_id not in avail

            bg_col     = (22, 20, 32) if is_locked else (35, 30, 50)
            border_col = (45, 45, 55) if is_locked else zone.color_accent
            pygame.draw.rect(self.screen, bg_col, rect, border_radius=9)
            pygame.draw.rect(self.screen, border_col, rect, 2, border_radius=9)

            if is_locked:
                name_t = self.font_md.render(zone.name, True, (80, 80, 90))
                lock_t = self.font_sm.render(
                    f"  Requires Level {zone.min_level}", True, (80, 80, 90))
                self.screen.blit(name_t, (rect.x + 14, rect.y + 8))
                self.screen.blit(lock_t, (rect.x + 14, rect.y + 36))
            else:
                stars   = "★" * zone.stars + "☆" * (5 - zone.stars)
                name_t  = self.font_md.render(zone.name, True, zone.color_accent)
                diff_t  = self.font_sm.render(
                    f"{stars}  {zone.difficulty_label}  ·  Lv {zone.min_level}+",
                    True, WHITE)
                desc_t  = self.font_sm.render(
                    zone.description.split("\n")[0][:60], True, GREY)
                rooms_t = self.font_sm.render(
                    f"{zone.rooms} rooms + Boss", True, (150, 150, 160))
                self.screen.blit(name_t,  (rect.x + 14, rect.y + 6))
                self.screen.blit(diff_t,  (rect.x + 14, rect.y + 28))
                self.screen.blit(desc_t,  (rect.x + 14, rect.y + 50))
                self.screen.blit(rooms_t, (rect.right - rooms_t.get_width() - 14, rect.y + 50))

                mx, my = pygame.mouse.get_pos()
                if rect.collidepoint(mx, my):
                    glow = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
                    glow.fill((*zone.color_accent, 25))
                    self.screen.blit(glow, rect.topleft)

                self._zone_rects[zone.zone_id] = rect

        lv_t = self.font_sm.render(
            f"{self.player.name}  Lv.{self.player.level}  |  "
            f"XP {self.player.xp}/{self.player.xp_to_next}"
            f"  |  Gold: {self.player.gold}",
            True, GOLD)
        self.screen.blit(lv_t, lv_t.get_rect(center=(W // 2, H - 12)))

        self.btn_skills.draw(self.screen, self.font_md)
        self.btn_save.draw(self.screen, self.font_md)

        if self._last_save_msg:
            msg_t = self.font_sm.render(self._last_save_msg, True, TEAL)
            self.screen.blit(msg_t, msg_t.get_rect(bottomleft=(10, H - 48)))

    # ------------------------------------------------------------------
    # SAVE SCREEN / LOAD SCREEN
    # ------------------------------------------------------------------

    def _handle_save_screen(self, events): self._handle_sl_events(events)
    def _handle_load_screen(self, events): self._handle_sl_events(events)
    def _draw_save_screen(self):           self._draw_sl_screen()
    def _draw_load_screen(self):           self._draw_sl_screen()

    # ------------------------------------------------------------------
    # HUB
    # ------------------------------------------------------------------

    def _handle_hub(self, events):
        for e in events:
            if e.type != pygame.MOUSEBUTTONDOWN or e.button != 1:
                continue
            for sid, rect in self._hub_skill_btns.items():
                if rect.collidepoint(e.pos):
                    self.player.gathering.start_minigame(sid)
                    self.state = GameState.GATHERING
                    return
            for target, rect in self._hub_btns.items():
                if rect.collidepoint(e.pos):
                    if target is GameState.SAVE_SCREEN:
                        self._enter_save()
                    elif target is GameState.SKILLS_SCREEN:
                        self._skills_from = GameState.HUB
                        self.state = GameState.SKILLS_SCREEN
                    else:
                        self.state = target
                    return

    def _draw_hub(self):
        self._hub_skill_btns = {}
        self._hub_btns       = {}
        self.screen.fill(BG)

        title = self.font_lg.render("Hub", True, GOLD)
        self.screen.blit(title, title.get_rect(center=(W // 2, 35)))

        p = self.player
        info_t = self.font_sm.render(
            f"{p.name}  Lv {p.level}  HP {p.hp}/{p.max_hp}  "
            f"Gold {p.gold}  Time {save_system._fmt_time(p._play_time)}",
            True, WHITE)
        self.screen.blit(info_t, info_t.get_rect(center=(W // 2, 65)))

        # Gathering skill grid (2 × 2)
        btn_w, btn_h = 180, 80
        grid_x = W // 2 - (2 * btn_w + 16) // 2
        grid_y = 90

        for i, (sid, skill) in enumerate(p.gathering.all().items()):
            meta  = _GATHERING_META[sid]
            col_i = i % 2
            row_i = i // 2
            x     = grid_x + col_i * (btn_w + 16)
            y     = grid_y + row_i * (btn_h + 12)
            rect  = pygame.Rect(x, y, btn_w, btn_h)
            color = meta["color"]

            mx, my = pygame.mouse.get_pos()
            bg_col = (45, 40, 65) if rect.collidepoint(mx, my) else (28, 28, 42)
            pygame.draw.rect(self.screen, bg_col,  rect, border_radius=8)
            pygame.draw.rect(self.screen, color,   rect, 2, border_radius=8)

            name_t = self.font_md.render(meta["label"], True, color)
            lv_t   = self.font_sm.render(f"Lv {skill.level}", True, WHITE)
            idle_c = GREEN if skill.level >= 50 else GREY
            idle_t = self.font_sm.render(
                "Idle: active" if skill.level >= 50 else "Idle: lv 50+",
                True, idle_c)

            self.screen.blit(name_t, (rect.x + 10, rect.y + 8))
            self.screen.blit(lv_t,   (rect.x + 10, rect.y + 34))
            self.screen.blit(idle_t, (rect.x + 10, rect.y + 56))

            bw   = btn_w - 20
            fill = int(bw * skill.xp_progress_ratio)
            pygame.draw.rect(self.screen, (50, 50, 60),
                             (rect.x + 10, rect.y + btn_h - 10, bw, 5), border_radius=2)
            if fill > 0:
                pygame.draw.rect(self.screen, color,
                                 (rect.x + 10, rect.y + btn_h - 10, fill, 5), border_radius=2)

            self._hub_skill_btns[sid] = rect

        # Bottom navigation buttons
        hub_btn_defs = [
            ("Skills",   GameState.SKILLS_SCREEN, GOLD),
            ("Dungeons", GameState.ZONE_SELECT,   LBLUE),
            ("Save",     GameState.SAVE_SCREEN,   GREEN),
        ]
        btn_row_y = grid_y + 2 * (btn_h + 12) + 18
        total_w   = len(hub_btn_defs) * 120 + (len(hub_btn_defs) - 1) * 14
        bx        = W // 2 - total_w // 2
        for label, target, col in hub_btn_defs:
            r = pygame.Rect(bx, btn_row_y, 120, 36)
            pygame.draw.rect(self.screen, col, r, border_radius=7)
            pygame.draw.rect(self.screen, WHITE, r, 1, border_radius=7)
            t = self.font_sm.render(label, True, BG)
            self.screen.blit(t, t.get_rect(center=r.center))
            self._hub_btns[target] = r
            bx += 134

        if self._last_save_msg:
            msg_t = self.font_sm.render(self._last_save_msg, True, TEAL)
            self.screen.blit(msg_t, msg_t.get_rect(center=(W // 2, H - 16)))

    # ------------------------------------------------------------------
    # GATHERING (active mini-game)
    # ------------------------------------------------------------------

    def _handle_gathering(self, events):
        mg = self.player.gathering.active_minigame
        if mg is None:
            self.state = GameState.HUB
            return
        mg.update(self._dt)
        if mg.done:
            self.state = GameState.GATHERING_RESULT
            return
        for e in events:
            mg.handle_event(e)

    def _draw_gathering(self):
        self.screen.fill(BG)
        mg = self.player.gathering.active_minigame
        if mg and not mg.done:
            mg.draw(self.screen, self._fonts)
        hint = self.font_sm.render("ESC — cancel", True, GREY)
        self.screen.blit(hint, (8, H - 20))

    # ------------------------------------------------------------------
    # GATHERING RESULT
    # ------------------------------------------------------------------

    def _handle_gathering_result(self, events):
        # Apply drops to inventory exactly once
        if not self._result_applied:
            mg = self.player.gathering.active_minigame
            if mg and mg.result:
                for name, qty in mg.result["drops"]:
                    self.player.add_item(Item(name, "material", qty))
            self._result_applied = True

        for e in events:
            if (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                    and self._result_btn
                    and self._result_btn.collidepoint(e.pos)):
                self.player.gathering.clear_minigame()
                self._result_applied = False
                self.state = GameState.HUB

    def _draw_gathering_result(self):
        mg = self.player.gathering.active_minigame
        if not mg or not mg.result:
            self.state = GameState.HUB
            return

        self.screen.fill(BG)
        res   = mg.result
        skill = mg.skill
        meta  = _GATHERING_META.get(skill.skill_id, {"color": WHITE})
        color = meta["color"]

        title_col = GREEN if res["success"] else RED
        t = self.font_lg.render(
            "Success!" if res["success"] else "Failed...", True, title_col)
        self.screen.blit(t, t.get_rect(center=(W // 2, H // 2 - 110)))

        for i, (name, qty) in enumerate(res["drops"]):
            d = self.font_md.render(f"+ {qty}x  {name}", True, GOLD)
            self.screen.blit(d, d.get_rect(center=(W // 2, H // 2 - 68 + i * 32)))

        xp_t = self.font_md.render(
            f"+ {res['xp']} XP  ({skill.name})", True, color)
        self.screen.blit(xp_t, xp_t.get_rect(center=(W // 2, H // 2)))

        if res["levelup"]["leveled_up"]:
            lu = self.font_lg.render(
                f"LEVEL UP!  {skill.name}  Lv {res['levelup']['new_level']}",
                True, GOLD)
            self.screen.blit(lu, lu.get_rect(center=(W // 2, H // 2 + 44)))

        sc = self.font_sm.render(f"Score: {res['score']} / 100", True, GREY)
        self.screen.blit(sc, sc.get_rect(center=(W // 2, H // 2 + 84)))

        btn = pygame.Rect(W // 2 - 80, H // 2 + 115, 160, 38)
        mx, my = pygame.mouse.get_pos()
        btn_col = (200, 160, 20) if btn.collidepoint(mx, my) else GOLD
        pygame.draw.rect(self.screen, btn_col, btn, border_radius=7)
        bt = self.font_md.render("Continue", True, BG)
        self.screen.blit(bt, bt.get_rect(center=btn.center))
        self._result_btn = btn

    # ------------------------------------------------------------------
    # SKILLS SCREEN
    # ------------------------------------------------------------------

    def _handle_skills_screen(self, events):
        for e in events:
            if self.btn_skills_back.clicked(e):
                self.state = self._skills_from

    def _draw_skills_screen(self):
        self.screen.fill(BG)

        title = self.font_lg.render("COMBAT SKILLS", True, GOLD)
        self.screen.blit(title, title.get_rect(center=(W // 2, 28)))

        cs = self.player.combat_skills
        col_map = {"Attack": SK_ATK_COL, "Defense": SK_DEF_COL, "Strength": SK_STR_COL}

        panel_w = 238
        panel_h = 420
        panel_y = 52
        xs      = [18, 281, 544]

        for col_x, (skill, skill_label, ab_defs) in zip(xs, cs.skill_ability_defs()):
            color = col_map[skill_label]
            panel = pygame.Rect(col_x, panel_y, panel_w, panel_h)
            pygame.draw.rect(self.screen, DGREY, panel, border_radius=8)
            pygame.draw.rect(self.screen, color,  panel, 2, border_radius=8)

            hdr = self.font_md.render(skill_label.upper(), True, color)
            self.screen.blit(hdr, hdr.get_rect(centerx=panel.centerx, y=panel.y + 8))

            lvl_t = self.font_lg.render(f"Lv. {skill.level}", True, WHITE)
            self.screen.blit(lvl_t, lvl_t.get_rect(centerx=panel.centerx, y=panel.y + 34))

            bx = panel.x + 12
            by = panel.y + 74
            bw = panel_w - 24
            bh = 11
            prog = skill.xp_progress()
            pygame.draw.rect(self.screen, (30, 20, 40), (bx, by, bw, bh))
            if prog > 0:
                pygame.draw.rect(self.screen, color, (bx, by, int(bw * prog), bh))
            pygame.draw.rect(self.screen, GREY, (bx, by, bw, bh), 1)

            xp_needed = skill.xp_to_next()
            xp_label  = (f"XP {skill.xp} / {skill.xp + xp_needed}"
                         if skill.level < 99 else "MAX LEVEL")
            xp_t = self.font_sm.render(xp_label, True, GREY)
            self.screen.blit(xp_t, xp_t.get_rect(centerx=panel.centerx, y=by + 14))

            if skill_label == "Attack":
                bonus_str = f"ATK +{cs.attack_bonus}"
            elif skill_label == "Defense":
                bonus_str = f"DEF +{cs.defense_bonus}"
            else:
                bonus_str = f"HP +{cs.max_hp_bonus}"
            bon_t = self.font_sm.render(bonus_str, True, color)
            self.screen.blit(bon_t, bon_t.get_rect(centerx=panel.centerx, y=by + 30))

            sep_y = panel.y + 115
            pygame.draw.line(self.screen, GREY,
                             (panel.x + 8, sep_y), (panel.right - 8, sep_y), 1)
            ab_hdr = self.font_sm.render("ABILITIES", True, YELLOW)
            self.screen.blit(ab_hdr, (panel.x + 12, sep_y + 4))

            ent_y = sep_y + 22
            for req_lvl, ab in ab_defs:
                unlocked = skill.level >= req_lvl
                name_col = WHITE if unlocked else (70, 70, 80)
                lock_tag = "" if unlocked else f"  (Lv {req_lvl})"
                nm = self.font_sm.render(f"• {ab.name}{lock_tag}", True, name_col)
                self.screen.blit(nm, (panel.x + 12, ent_y))
                ent_y += 16
                if unlocked:
                    dc = self.font_sm.render(
                        f"  {ab.description}  [CD:{ab.cooldown_max}t]", True, GREY)
                    self.screen.blit(dc, (panel.x + 12, ent_y))
                    ent_y += 18

        self.btn_skills_back.draw(self.screen, self.font_md)

    # ------------------------------------------------------------------
    # COMBAT
    # ------------------------------------------------------------------

    def _handle_combat(self, events):
        if self._show_inventory:
            for e in events:
                if self.btn_inv_close.clicked(e):
                    self._show_inventory = False
                    return
                for i, item in enumerate(list(self.player.inventory)):
                    if (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                            and self._inv_slot_rect(i).collidepoint(e.pos)):
                        msg, costs_turn = self.player.use_item(item)
                        self._push_log(msg)
                        if costs_turn:
                            self._show_inventory = False
                            result = self.combat.execute(Action.ITEM)
                            self._push_log(*result.logs)
                            if result.shake_player: self.shake_p = 10
                            if result.state is CombatState.DEFEAT:
                                self.state = GameState.LOSE
                        return
            return

        if self.combat.state is not CombatState.PLAYER_TURN:
            return

        for e in events:
            for ab, rect in self._ability_button_rects():
                if (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                        and rect.collidepoint(e.pos)
                        and self.player.combat_skills.ability_ready(ab.action)):
                    self._execute_combat_action(Action.ABILITY, ability=ab.action)
                    return

            action = None
            if self.btn_attack.clicked(e):   action = Action.ATTACK
            elif self.btn_defend.clicked(e): action = Action.DEFEND
            elif self.btn_flee.clicked(e):   action = Action.FLEE
            elif self.btn_items.clicked(e):
                self._show_inventory = True
                continue
            if action is None:
                continue
            self._execute_combat_action(action)

    def _execute_combat_action(self, action, ability=None):
        result = self.combat.execute(action, ability=ability)
        self._push_log(*result.logs)
        if result.shake_player: self.shake_p = 10
        if result.shake_enemy:  self.shake_e = 10

        if result.state is CombatState.VICTORY:
            enemy    = self.combat.enemy
            levelled = self.player.gain_xp(enemy.xp_reward)
            self._last_xp_gained  = enemy.xp_reward
            self._zone_xp_total  += enemy.xp_reward
            self.encounter_index += 1

            # Award gold from loot
            for item_name, qty in enemy.roll_loot():
                if item_name == "Gold Coin":
                    self.player.gold += qty

            if self.encounter_index >= len(self.encounters):
                # Boss killed — auto-save to slot 0
                ok = save_system.save_game(self.player, slot=0)
                self._last_save_msg = "Auto-saved!" if ok else ""
                self.state = GameState.WIN
            else:
                xp_str = f"+{enemy.xp_reward} XP"
                if levelled:
                    xp_str += f"   LEVEL UP!  Lv.{self.player.level}"
                self.trans_header = f"{enemy.name} defeated!"
                self.trans_xp     = xp_str
                self.state        = GameState.TRANSITION

        elif result.state is CombatState.DEFEAT:
            self.state = GameState.LOSE

        elif result.state is CombatState.FLED:
            self.trans_xp = "You fled from battle."
            self.state    = GameState.LOSE

    def _draw_combat(self):
        self.screen.fill(BG)
        self.screen.blit(self.bg_dungeon, (0, 0))

        px_off = random.randint(-5, 5) if self.shake_p > 0 else 0
        ex_off = random.randint(-5, 5) if self.shake_e > 0 else 0
        if self.shake_p > 0: self.shake_p -= 1
        if self.shake_e > 0: self.shake_e -= 1

        enemy = self.combat.enemy

        p_img = _scale(self.sprites["warrior"], self.player.sprite_size)
        self.screen.blit(p_img, (150 - p_img.get_width() // 2 + px_off,
                                  235 - p_img.get_height() // 2))

        e_key = enemy.sprite_file.replace(".png", "")
        e_img = _flip_h(_scale(self.sprites[e_key], enemy.sprite_size))
        self.screen.blit(e_img, (650 - e_img.get_width() // 2 + ex_off,
                                   245 - e_img.get_height() // 2))

        pygame.draw.line(self.screen, GREY, (0, 390), (W, 390), 1)

        vs = self.font_lg.render("VS", True, ORANGE)
        self.screen.blit(vs, vs.get_rect(center=(W // 2, 265)))

        zone        = self.selected_zone
        room_num    = self.encounter_index + 1
        total_rooms = len(self.encounters)
        if enemy.is_boss:
            hdr_str = f"BOSS  {zone.name}  Room {room_num}/{total_rooms}"
            hdr_col = tuple(min(255, c + 60) for c in zone.color_accent)
        else:
            hdr_str = f"{zone.name}  ·  Room {room_num}/{total_rooms}"
            hdr_col = GREY
        prog = self.font_sm.render(hdr_str, True, hdr_col)
        self.screen.blit(prog, prog.get_rect(center=(W // 2, 22)))

        self._draw_hp_bar(35, 48, 200, 16,
                          self.player.hp, self.player.max_hp,
                          f"{self.player.name} Lv.{self.player.level}")
        self._draw_hp_bar(565, 48, 200, 16, enemy.hp, enemy.max_hp, enemy.name)

        self._draw_xp_bar(35, 68, 200, 8)

        p_stats = self.font_sm.render(
            f"ATK {self.player.attack}  DEF {self.player.defense}"
            f"  SPD {self.player.speed}  G:{self.player.gold}",
            True, GREY)
        e_stats = self.font_sm.render(
            f"ATK {enemy.attack}  DEF {enemy.defense}  SPD {enemy.speed}",
            True, GREY)
        self.screen.blit(p_stats, (35,  82))
        self.screen.blit(e_stats, (565, 74))

        # Status effects
        cs = self.player.combat_skills
        sx = 35
        if cs.berserk_active:
            bt = self.font_sm.render(f"[BERSERK {cs.berserk_turns_left}t]", True, (255, 80, 80))
            self.screen.blit(bt, (sx, 96))
            sx += bt.get_width() + 8
        if cs.iron_skin_active:
            ist = self.font_sm.render("[IRON SKIN]", True, (80, 160, 255))
            self.screen.blit(ist, (sx, 96))

        self._draw_log_box()
        self._draw_ability_buttons()

        self.btn_attack.draw(self.screen, self.font_md)
        self.btn_defend.draw(self.screen, self.font_md)
        self.btn_items.draw(self.screen, self.font_md)
        self.btn_flee.draw(self.screen, self.font_md)

        if self._show_inventory:
            self._draw_inventory_overlay()

    def _draw_ability_buttons(self):
        cs = self.player.combat_skills
        mx, my = pygame.mouse.get_pos()
        for ab, rect in self._ability_button_rects():
            ready = cs.ability_ready(ab.action)
            cd    = cs.get_cooldown(ab.action)
            if ready:
                bg_col     = (70, 40, 110)
                border_col = PURPLE
                lbl        = ab.name
                lbl_col    = WHITE
            else:
                bg_col     = (25, 20, 35)
                border_col = (60, 55, 70)
                lbl        = f"{ab.name}({cd})"
                lbl_col    = (90, 85, 100)

            pygame.draw.rect(self.screen, bg_col, rect, border_radius=5)
            pygame.draw.rect(self.screen, border_col, rect, 1, border_radius=5)

            if ready and rect.collidepoint(mx, my):
                glow = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                glow.fill((*PURPLE, 50))
                self.screen.blit(glow, rect.topleft)

            t = self.font_sm.render(lbl, True, lbl_col)
            self.screen.blit(t, t.get_rect(center=rect.center))

    def _draw_xp_bar(self, x, y, w, h):
        ratio = self.player.xp / self.player.xp_to_next
        pygame.draw.rect(self.screen, DGREY,  (x, y, w, h))
        pygame.draw.rect(self.screen, PURPLE, (x, y, int(w * ratio), h))
        pygame.draw.rect(self.screen, GREY,   (x, y, w, h), 1)
        lbl = self.font_sm.render(
            f"XP {self.player.xp}/{self.player.xp_to_next}", True, (160, 100, 220))
        self.screen.blit(lbl, (x + w + 6, y - 2))

    def _inv_slot_rect(self, i):
        return pygame.Rect(W // 2 - 190, H // 2 - 110 + i * 44, 380, 38)

    def _draw_inventory_overlay(self):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))
        self.screen.blit(s, (0, 0))

        panel = pygame.Rect(W // 2 - 200, H // 2 - 150, 400, 300)
        pygame.draw.rect(self.screen, DGREY, panel, border_radius=10)
        pygame.draw.rect(self.screen, GREY,  panel, 2, border_radius=10)

        hdr = self.font_md.render("Inventory", True, YELLOW)
        self.screen.blit(hdr, hdr.get_rect(centerx=panel.centerx, y=panel.y + 10))

        if not self.player.inventory:
            empty = self.font_sm.render("(empty)", True, GREY)
            self.screen.blit(empty, empty.get_rect(center=panel.center))
        else:
            mx, my = pygame.mouse.get_pos()
            for i, item in enumerate(self.player.inventory):
                slot     = self._inv_slot_rect(i)
                hovered  = slot.collidepoint(mx, my)
                bg_color = (60, 50, 80) if hovered else (30, 25, 45)
                pygame.draw.rect(self.screen, bg_color, slot, border_radius=5)
                pygame.draw.rect(self.screen, GREY, slot, 1, border_radius=5)
                equipped = (item is self.player._wpn or item is self.player._arm)
                tag = " [E]" if equipped else ""
                lbl = self.font_sm.render(
                    f"{item.name}{tag}  —  {item.describe()}", True, WHITE)
                self.screen.blit(lbl, (slot.x + 8, slot.y + 11))

        self.btn_inv_close.draw(self.screen, self.font_sm)

    # ------------------------------------------------------------------
    # TRANSITION
    # ------------------------------------------------------------------

    def _handle_transition(self, events):
        for e in events:
            if self.btn_next.clicked(e):
                self._begin_combat()

    def _draw_transition(self):
        self.screen.fill(BG)
        self._overlay(140)

        zone  = self.selected_zone
        done  = self.encounter_index
        total = len(self.encounters)

        zone_t = self.font_md.render(zone.name, True, zone.color_accent)
        self.screen.blit(zone_t, zone_t.get_rect(center=(W // 2, 38)))

        bar_w = 320
        bar_x = W // 2 - bar_w // 2
        bar_y = 58
        pygame.draw.rect(self.screen, DGREY, (bar_x, bar_y, bar_w, 14), border_radius=7)
        fill = int(bar_w * (done / total))
        if fill > 0:
            pygame.draw.rect(self.screen, zone.color_accent,
                             (bar_x, bar_y, fill, 14), border_radius=7)
        pygame.draw.rect(self.screen, GREY, (bar_x, bar_y, bar_w, 14), 1, border_radius=7)
        prog_t = self.font_sm.render(f"Room {done}/{total} complete", True, WHITE)
        self.screen.blit(prog_t, prog_t.get_rect(center=(W // 2, bar_y + 22)))

        hdr_t = self.font_lg.render(self.trans_header, True, GREEN)
        self.screen.blit(hdr_t, hdr_t.get_rect(center=(W // 2, 110)))
        xp_t = self.font_md.render(self.trans_xp, True, YELLOW)
        self.screen.blit(xp_t, xp_t.get_rect(center=(W // 2, 148)))

        nxt     = self.encounters[self.encounter_index]
        is_boss = nxt.is_boss
        lbl_str = "  BOSS INCOMING!" if is_boss else "Next Enemy:"
        lbl_col = RED if is_boss else WHITE
        lbl_t   = self.font_sm.render(lbl_str, True, lbl_col)
        self.screen.blit(lbl_t, lbl_t.get_rect(center=(W // 2, 188)))

        name_col = RED if is_boss else zone.color_accent
        name_t   = self.font_lg.render(nxt.name, True, name_col)
        self.screen.blit(name_t, name_t.get_rect(center=(W // 2, 220)))

        stats_t = self.font_sm.render(
            f"HP {nxt.max_hp}   ATK {nxt.attack}   DEF {nxt.defense}",
            True, GREY)
        self.screen.blit(stats_t, stats_t.get_rect(center=(W // 2, 252)))

        hp_xp = self.font_sm.render(
            f"Your HP: {self.player.hp}/{self.player.max_hp}   "
            f"Lv.{self.player.level}   XP: {self.player.xp}/{self.player.xp_to_next}",
            True, (160, 160, 170))
        self.screen.blit(hp_xp, hp_xp.get_rect(center=(W // 2, 290)))

        cs = self.player.combat_skills
        sk_t = self.font_sm.render(
            f"ATK skill Lv.{cs.attack.level}  "
            f"DEF skill Lv.{cs.defense.level}  "
            f"STR skill Lv.{cs.strength.level}",
            True, TEAL)
        self.screen.blit(sk_t, sk_t.get_rect(center=(W // 2, 310)))

        self.btn_next.draw(self.screen, self.font_md)

    # ------------------------------------------------------------------
    # END SCREENS
    # ------------------------------------------------------------------

    def _handle_end(self, events):
        for e in events:
            if self.btn_end_main.clicked(e):
                if self.state is GameState.WIN:
                    self._to_hub()
                else:
                    self._to_zone_select()
            if self.btn_new_char.clicked(e):
                self._to_char_create()

    def _draw_end(self):
        win = self.state is GameState.WIN
        self.screen.fill(BG)
        self._overlay(150)

        color = GREEN if win else RED
        t = self.font_xl.render("VICTORY!" if win else "DEFEATED", True, color)
        self.screen.blit(t, t.get_rect(center=(W // 2, H // 2 - 100)))

        zone = self.selected_zone
        if win:
            body = f"{zone.name} conquered!"
            self.btn_end_main.label = "Go to Hub"
        else:
            done  = self.encounter_index
            total = len(self.encounters)
            body  = (self.trans_xp or f"Fell in {zone.name}  (Room {done}/{total})")
            self.btn_end_main.label = "Try Again"

        body_t = self.font_md.render(body, True, WHITE)
        self.screen.blit(body_t, body_t.get_rect(center=(W // 2, H // 2 - 45)))

        if self.player:
            stats_t = self.font_sm.render(
                f"HP: {self.player.hp}/{self.player.max_hp}   "
                f"Level: {self.player.level}   Gold: {self.player.gold}   "
                f"XP this run: +{self._zone_xp_total}",
                True, GREY)
            self.screen.blit(stats_t, stats_t.get_rect(center=(W // 2, H // 2 + 5)))

        # Auto-save notification
        if win and self._last_save_msg:
            sv_t = self.font_sm.render(self._last_save_msg, True, TEAL)
            self.screen.blit(sv_t, sv_t.get_rect(center=(W // 2, H // 2 + 28)))

        self.btn_end_main.draw(self.screen, self.font_md)
        self.btn_new_char.draw(self.screen, self.font_sm)

    # ------------------------------------------------------------------
    # Drawing utilities
    # ------------------------------------------------------------------

    def _draw_hp_bar(self, x, y, w, h, hp, max_hp, name):
        ratio = max(0.0, hp / max_hp)
        color = GREEN if ratio > 0.5 else YELLOW if ratio > 0.25 else RED
        pygame.draw.rect(self.screen, DGREY, (x, y, w, h))
        pygame.draw.rect(self.screen, color,  (x, y, int(w * ratio), h))
        pygame.draw.rect(self.screen, WHITE,  (x, y, w, h), 2)
        label = self.font_sm.render(f"{name}   {hp}/{max_hp}", True, WHITE)
        self.screen.blit(label, (x, y - 16))

    def _draw_log_box(self):
        box = pygame.Rect(10, 393, W - 20, 50)
        pygame.draw.rect(self.screen, DGREY, box)
        pygame.draw.rect(self.screen, GREY,  box, 1)
        lines = self.log[-3:]
        for i, line in enumerate(lines):
            brightness = 150 + i * 40
            col = (min(255, brightness),) * 3
            t = self.font_sm.render(line, True, col)
            self.screen.blit(t, (18, 398 + i * 16))

    def _overlay(self, alpha):
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((0, 0, 0, alpha))
        self.screen.blit(s, (0, 0))

    def _text(self, msg, x, y, font, color):
        t = font.render(msg, True, color)
        self.screen.blit(t, (x, y))

    def _push_log(self, *msgs):
        self.log.extend(msgs)
        if len(self.log) > 20:
            self.log = self.log[-20:]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    Game().run()
