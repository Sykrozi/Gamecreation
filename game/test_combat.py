import pygame
import sys
import os
import random

pygame.init()

# --- Constants ---
SCREEN_W, SCREEN_H = 800, 500
FPS = 60
ASSETS = os.path.join(os.path.dirname(__file__), "assets")

BLACK   = (0,   0,   0)
WHITE   = (255, 255, 255)
RED     = (200,  30,  30)
GREEN   = ( 30, 180,  30)
GREY    = ( 60,  60,  60)
DGREY   = ( 30,  30,  30)
YELLOW  = (220, 200,  50)
BLUE    = ( 50, 100, 200)
LBLUE   = ( 80, 140, 230)
ORANGE  = (220, 120,  30)

WARRIOR_MAX_HP = 100
GOBLIN_MAX_HP  = 60

FONT    = pygame.font.SysFont("consolas", 18)
BIGFONT = pygame.font.SysFont("consolas", 26, bold=True)
SMFONT  = pygame.font.SysFont("consolas", 14)

screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Combat Test")
clock = pygame.time.Clock()

# --- Load sprites ---
def load_sprite(name, scale=None):
    img = pygame.image.load(os.path.join(ASSETS, name)).convert_alpha()
    if scale:
        img = pygame.transform.scale(img, scale)
    return img

warrior_img = load_sprite("warrior.png", (128, 128))
goblin_img  = load_sprite("goblin.png",  (96, 96))

# Flip goblin so it faces left (toward warrior)
goblin_img = pygame.transform.flip(goblin_img, True, False)

# --- State ---
warrior_hp = WARRIOR_MAX_HP
goblin_hp  = GOBLIN_MAX_HP
log        = ["A goblin appears! Choose your action."]
defending  = False
game_over  = False
outcome    = ""

# Shake state for hit feedback
shake = {"who": None, "frames": 0, "offset": (0, 0)}

def add_log(msg):
    log.append(msg)
    if len(log) > 5:
        log.pop(0)

def goblin_attack(reduced=False):
    dmg = random.randint(4, 12)
    if reduced:
        dmg = max(1, dmg // 2)
    return dmg

def warrior_attack():
    return random.randint(10, 22)

# --- Button ---
class Button:
    def __init__(self, rect, label, color, hover_color):
        self.rect        = pygame.Rect(rect)
        self.label       = label
        self.color       = color
        self.hover_color = hover_color

    def draw(self, surf, enabled=True):
        mouse = pygame.mouse.get_pos()
        hovered = self.rect.collidepoint(mouse) and enabled
        c = self.hover_color if hovered else self.color
        if not enabled:
            c = GREY
        pygame.draw.rect(surf, c, self.rect, border_radius=6)
        pygame.draw.rect(surf, WHITE, self.rect, 2, border_radius=6)
        lbl = FONT.render(self.label, True, WHITE if enabled else (120, 120, 120))
        surf.blit(lbl, lbl.get_rect(center=self.rect.center))

    def clicked(self, event, enabled=True):
        return (enabled
                and event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1
                and self.rect.collidepoint(event.pos))

btn_attack  = Button((260, 420, 120, 44), "Attack",  (160, 30, 30),  (210, 50, 50))
btn_defend  = Button((400, 420, 120, 44), "Defend",  ( 30, 80, 160), ( 50,120, 210))
btn_flee    = Button((540, 420, 120, 44), "Flee",    ( 80, 80,  80), (120,120, 120))
buttons = [btn_attack, btn_defend, btn_flee]

def draw_hp_bar(surf, x, y, w, h, current, maximum, label):
    ratio = max(0, current / maximum)
    color = GREEN if ratio > 0.5 else YELLOW if ratio > 0.25 else RED
    pygame.draw.rect(surf, DGREY, (x, y, w, h))
    pygame.draw.rect(surf, color,  (x, y, int(w * ratio), h))
    pygame.draw.rect(surf, WHITE,  (x, y, w, h), 2)
    txt = FONT.render(f"{label}  {current}/{maximum}", True, WHITE)
    surf.blit(txt, (x + w // 2 - txt.get_width() // 2, y - 22))

def apply_shake(who):
    shake["who"]    = who
    shake["frames"] = 8

def do_attack():
    global goblin_hp, warrior_hp, game_over, outcome, defending
    # Warrior attacks goblin
    dmg = warrior_attack()
    goblin_hp = max(0, goblin_hp - dmg)
    add_log(f"You attack for {dmg} damage!")
    apply_shake("goblin")
    if goblin_hp == 0:
        add_log("Goblin defeated! You win!")
        game_over = True
        outcome   = "VICTORY"
        return
    # Goblin counter-attacks
    gdmg = goblin_attack()
    warrior_hp = max(0, warrior_hp - gdmg)
    add_log(f"Goblin strikes back for {gdmg} damage!")
    apply_shake("warrior")
    if warrior_hp == 0:
        add_log("You have been defeated...")
        game_over = True
        outcome   = "DEFEAT"

def do_defend():
    global warrior_hp, game_over, outcome
    gdmg = goblin_attack(reduced=True)
    warrior_hp = max(0, warrior_hp - gdmg)
    add_log(f"You defend! Goblin hits for only {gdmg} damage.")
    apply_shake("warrior")
    if warrior_hp == 0:
        add_log("You have been defeated...")
        game_over = True
        outcome   = "DEFEAT"

def do_flee():
    global game_over, outcome
    if random.random() < 0.5:
        add_log("You fled successfully!")
        game_over = True
        outcome   = "FLED"
    else:
        gdmg = goblin_attack()
        global warrior_hp
        warrior_hp = max(0, warrior_hp - gdmg)
        add_log(f"Couldn't flee! Goblin hits for {gdmg} damage.")
        apply_shake("warrior")
        if warrior_hp == 0:
            add_log("You have been defeated...")
            game_over = True
            outcome   = "DEFEAT"

# --- Main loop ---
while True:
    dt = clock.tick(FPS)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit()

        if not game_over:
            if btn_attack.clicked(event):
                do_attack()
            elif btn_defend.clicked(event):
                do_defend()
            elif btn_flee.clicked(event):
                do_flee()
        else:
            # Press R to restart
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                warrior_hp = WARRIOR_MAX_HP
                goblin_hp  = GOBLIN_MAX_HP
                log        = ["A goblin appears! Choose your action."]
                game_over  = False
                outcome    = ""

    # Update shake
    wx_off, wy_off = 0, 0
    gx_off, gy_off = 0, 0
    if shake["frames"] > 0:
        shake["frames"] -= 1
        off = random.randint(-6, 6)
        if shake["who"] == "warrior":
            wx_off = off
        elif shake["who"] == "goblin":
            gx_off = off

    # --- Draw ---
    screen.fill((15, 10, 20))

    # Arena floor line
    pygame.draw.line(screen, GREY, (0, 370), (SCREEN_W, 370), 2)

    # Warrior position: left-center
    wx = 140 - warrior_img.get_width() // 2 + wx_off
    wy = 230 - warrior_img.get_height() // 2 + wy_off
    screen.blit(warrior_img, (wx, wy))

    # Goblin position: right-center
    gx = 660 - goblin_img.get_width() // 2 + gx_off
    gy = 245 - goblin_img.get_height() // 2 + gy_off
    screen.blit(goblin_img, (gx, gy))

    # HP bars
    draw_hp_bar(screen, 50,  60, 180, 18, warrior_hp, WARRIOR_MAX_HP, "Warrior")
    draw_hp_bar(screen, 570, 60, 180, 18, goblin_hp,  GOBLIN_MAX_HP,  "Goblin")

    # VS label
    vs = BIGFONT.render("VS", True, ORANGE)
    screen.blit(vs, vs.get_rect(center=(SCREEN_W // 2, 280)))

    # Divider
    pygame.draw.line(screen, GREY, (SCREEN_W // 2, 80), (SCREEN_W // 2, 370), 1)

    # Combat log
    pygame.draw.rect(screen, DGREY, (20, 378, SCREEN_W - 40, 32))
    pygame.draw.rect(screen, GREY,  (20, 378, SCREEN_W - 40, 32), 1)
    if log:
        msg = FONT.render(log[-1], True, WHITE)
        screen.blit(msg, (30, 385))

    # Buttons
    if not game_over:
        for btn in buttons:
            btn.draw(screen)
    else:
        # Game-over overlay
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))

        color = GREEN if outcome == "VICTORY" else (RED if outcome == "DEFEAT" else YELLOW)
        title = BIGFONT.render(outcome, True, color)
        screen.blit(title, title.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 - 20)))
        hint = FONT.render("Press R to restart  |  ESC to quit", True, WHITE)
        screen.blit(hint, hint.get_rect(center=(SCREEN_W // 2, SCREEN_H // 2 + 20)))

    pygame.display.flip()
