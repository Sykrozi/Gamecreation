import sys
import os
import random
from enum import Enum, auto

import pygame

from entities.character import make_warrior, make_goblin, make_archer, make_mage, make_boss
from systems.combat import CombatSystem, CombatState, Action

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
W, H   = 800, 520
FPS    = 60
ASSETS = os.path.join(os.path.dirname(__file__), "assets")

BG      = ( 12,   8,  20)
BLACK   = (  0,   0,   0)
WHITE   = (255, 255, 255)
GREY    = ( 70,  70,  80)
DGREY   = ( 20,  18,  30)
RED     = (200,  30,  30)
GREEN   = ( 30, 180,  50)
YELLOW  = (220, 200,  50)
ORANGE  = (230, 120,  30)
LBLUE   = ( 60, 120, 210)


class GameState(Enum):
    MENU       = auto()
    COMBAT     = auto()
    TRANSITION = auto()
    WIN        = auto()
    LOSE       = auto()


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

    ENEMY_FACTORIES = [make_goblin, make_archer, make_mage, make_boss]

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption("Pixel RPG")
        self.clock  = pygame.time.Clock()

        self.font_sm = pygame.font.SysFont("consolas", 14)
        self.font_md = pygame.font.SysFont("consolas", 18)
        self.font_lg = pygame.font.SysFont("consolas", 28, bold=True)
        self.font_xl = pygame.font.SysFont("consolas", 42, bold=True)

        self._load_sprites()
        self._init_buttons()
        self._new_game()

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
        y = H - 68
        self.btn_attack = Button((210, y, 115, 42), "Attack", (150, 25, 25), (210, 55, 55))
        self.btn_defend = Button((340, y, 115, 42), "Defend", ( 25, 75,155), ( 55,115,210))
        self.btn_flee   = Button((470, y, 115, 42), "Flee",   ( 65, 65, 65), (110,110,110))
        self.btn_start  = Button((W//2-105, H-130, 210, 50), "Start Adventure",
                                 (35,110, 35), (60,160, 60))
        self.btn_next   = Button((W//2-100, H//2+70, 200, 46), "Continue",
                                 (35,110, 35), (60,160, 60))
        self.btn_replay = Button((W//2-100, H//2+80, 200, 46), "Play Again",
                                 (40, 40,110), (70, 70,160))

    def _new_game(self):
        self.player       = make_warrior()
        self.enemies      = [f() for f in self.ENEMY_FACTORIES]
        self.enemy_idx    = 0
        self.combat       = None
        self.state        = GameState.MENU
        self.log          = []
        self.trans_header = ""
        self.trans_sub    = ""
        # Two independent shake timers
        self.shake_p = 0   # player shake frames remaining
        self.shake_e = 0   # enemy shake frames remaining

    def _begin_combat(self):
        enemy         = self.enemies[self.enemy_idx]
        self.combat   = CombatSystem(self.player, enemy)
        self.log      = [f"Encounter: {enemy.name}!"]
        self.state    = GameState.COMBAT
        self.shake_p  = self.shake_e = 0
        self.player.end_turn()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        while True:
            self.clock.tick(FPS)
            events = pygame.event.get()

            for e in events:
                if e.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()

            dispatch = {
                GameState.MENU:       (self._handle_menu,       self._draw_menu),
                GameState.COMBAT:     (self._handle_combat,     self._draw_combat),
                GameState.TRANSITION: (self._handle_transition, self._draw_transition),
                GameState.WIN:        (self._handle_end,        self._draw_end),
                GameState.LOSE:       (self._handle_end,        self._draw_end),
            }
            handle, draw = dispatch[self.state]
            handle(events)
            draw()
            pygame.display.flip()

    # ------------------------------------------------------------------
    # MENU
    # ------------------------------------------------------------------

    def _handle_menu(self, events):
        for e in events:
            if self.btn_start.clicked(e):
                self._new_game()
                self._begin_combat()

    def _draw_menu(self):
        self.screen.fill(BG)

        title = self.font_xl.render("PIXEL  RPG", True, ORANGE)
        self.screen.blit(title, title.get_rect(center=(W // 2, 60)))

        sub = self.font_md.render("A turn-based pixel art adventure", True, GREY)
        self.screen.blit(sub, sub.get_rect(center=(W // 2, 105)))

        # Warrior sprite centred
        img = _scale(self.sprites["warrior"], (128, 128))
        self.screen.blit(img, img.get_rect(center=(W // 2, 220)))

        # Enemy roster
        self._text("Defeat them all:", W // 2 - 80, 300, self.font_sm, GREY)
        enemies_info = [
            ("Goblin",    YELLOW),
            ("Archer",    YELLOW),
            ("Mage",      YELLOW),
            ("Dark Lord", RED),
        ]
        for i, (name, col) in enumerate(enemies_info):
            self._text(f"  {i+1}. {name}", W // 2 - 80, 320 + i * 18, self.font_sm, col)

        self.btn_start.draw(self.screen, self.font_md)

    # ------------------------------------------------------------------
    # COMBAT
    # ------------------------------------------------------------------

    def _handle_combat(self, events):
        if self.combat.state is not CombatState.PLAYER_TURN:
            return
        for e in events:
            action = None
            if self.btn_attack.clicked(e): action = Action.ATTACK
            elif self.btn_defend.clicked(e): action = Action.DEFEND
            elif self.btn_flee.clicked(e):   action = Action.FLEE
            if action is None:
                continue

            result = self.combat.execute(action)
            self._push_log(*result.logs)
            if result.shake_player: self.shake_p = 10
            if result.shake_enemy:  self.shake_e = 10

            if result.state is CombatState.VICTORY:
                self.enemy_idx += 1
                if self.enemy_idx >= len(self.enemies):
                    self.state = GameState.WIN
                else:
                    nxt = self.enemies[self.enemy_idx].name
                    self.trans_header = f"{self.combat.enemy.name} defeated!"
                    self.trans_sub    = f"Next: {nxt}"
                    self.state = GameState.TRANSITION

            elif result.state is CombatState.DEFEAT:
                self.state = GameState.LOSE

            elif result.state is CombatState.FLED:
                self.trans_header = "You fled the dungeon!"
                self.trans_sub    = "Your adventure ends here."
                self.state = GameState.LOSE

    def _draw_combat(self):
        # UI strip below the combat area
        self.screen.fill(BG)

        # Dungeon background fills the combat area (full width, top 390px)
        self.screen.blit(self.bg_dungeon, (0, 0))

        # Compute shake offsets
        px_off = random.randint(-5, 5) if self.shake_p > 0 else 0
        ex_off = random.randint(-5, 5) if self.shake_e > 0 else 0
        if self.shake_p > 0: self.shake_p -= 1
        if self.shake_e > 0: self.shake_e -= 1

        enemy = self.combat.enemy

        # Player sprite
        p_img = _scale(self.sprites["warrior"], self.player.sprite_size)
        px = 150 - p_img.get_width() // 2 + px_off
        py = 235 - p_img.get_height() // 2
        self.screen.blit(p_img, (px, py))

        # Enemy sprite (flipped to face left)
        e_key = enemy.sprite_file.replace(".png", "")
        e_img = _flip_h(_scale(self.sprites[e_key], enemy.sprite_size))
        ex = 650 - e_img.get_width() // 2 + ex_off
        ey = 245 - e_img.get_height() // 2
        self.screen.blit(e_img, (ex, ey))

        # Separator between combat area and UI strip
        pygame.draw.line(self.screen, GREY, (0, 390), (W, 390), 1)

        # VS label
        vs = self.font_lg.render("VS", True, ORANGE)
        self.screen.blit(vs, vs.get_rect(center=(W // 2, 265)))

        # Progress
        prog = self.font_sm.render(
            f"Battle {self.enemy_idx + 1} of {len(self.enemies)}", True, GREY)
        self.screen.blit(prog, prog.get_rect(center=(W // 2, 22)))

        # HP bars
        self._draw_hp_bar(35,  48, 200, 16, self.player.hp, self.player.max_hp, self.player.name)
        self._draw_hp_bar(565, 48, 200, 16, enemy.hp,       enemy.max_hp,       enemy.name)

        # Stats under bars (compact)
        p_stats = self.font_sm.render(
            f"ATK {self.player.attack}  DEF {self.player.defense}  SPD {self.player.speed}",
            True, GREY)
        e_stats = self.font_sm.render(
            f"ATK {enemy.attack}  DEF {enemy.defense}  SPD {enemy.speed}",
            True, GREY)
        self.screen.blit(p_stats, (35, 74))
        self.screen.blit(e_stats, (565, 74))

        # Combat log
        self._draw_log_box()

        # Action buttons
        self.btn_attack.draw(self.screen, self.font_md)
        self.btn_defend.draw(self.screen, self.font_md)
        self.btn_flee.draw(self.screen, self.font_md)

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

        hdr = self.font_lg.render(self.trans_header, True, GREEN)
        self.screen.blit(hdr, hdr.get_rect(center=(W // 2, H // 2 - 55)))

        sub = self.font_md.render(self.trans_sub, True, YELLOW)
        self.screen.blit(sub, sub.get_rect(center=(W // 2, H // 2 - 10)))

        hp_info = self.font_md.render(
            f"Warrior HP carried over:  {self.player.hp} / {self.player.max_hp}",
            True, WHITE)
        self.screen.blit(hp_info, hp_info.get_rect(center=(W // 2, H // 2 + 30)))

        self.btn_next.draw(self.screen, self.font_md)

    # ------------------------------------------------------------------
    # END SCREENS
    # ------------------------------------------------------------------

    def _handle_end(self, events):
        for e in events:
            if self.btn_replay.clicked(e):
                self._new_game()

    def _draw_end(self):
        win = self.state is GameState.WIN
        self.screen.fill(BG)
        self._overlay(150)

        color = GREEN if win else RED
        title = "VICTORY!" if win else "DEFEATED"
        body  = ("You conquered the dungeon!" if win
                 else self.trans_sub or "Your quest ends here...")

        t = self.font_xl.render(title, True, color)
        self.screen.blit(t, t.get_rect(center=(W // 2, H // 2 - 65)))

        s = self.font_md.render(body, True, WHITE)
        self.screen.blit(s, s.get_rect(center=(W // 2, H // 2 - 15)))

        if win:
            sub2 = self.font_sm.render(
                f"Final HP: {self.player.hp} / {self.player.max_hp}", True, GREY)
            self.screen.blit(sub2, sub2.get_rect(center=(W // 2, H // 2 + 20)))

        self.btn_replay.draw(self.screen, self.font_md)

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
        box = pygame.Rect(10, 395, W - 20, 82)
        pygame.draw.rect(self.screen, DGREY, box)
        pygame.draw.rect(self.screen, GREY,  box, 1)
        lines = self.log[-4:]
        for i, line in enumerate(lines):
            brightness = 140 + i * 38
            col = (min(255, brightness),) * 3
            t = self.font_sm.render(line, True, col)
            self.screen.blit(t, (18, 401 + i * 19))

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
