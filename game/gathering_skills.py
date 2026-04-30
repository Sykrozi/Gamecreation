# gathering_skills.py
# Mining, Woodcutting, Fishing, Farming — com mini-jogos únicos
# Segue o GDD: tap rítmico, tap de precisão, quick-time
# ─────────────────────────────────────────────────────────────

import pygame
import random
import math
import time

# ── Reutiliza a XP table do combat_skills
from combat_skills import level_for_xp, xp_to_next_level, XP_TABLE

# ── Cores
BLACK  = (0,   0,   0)
WHITE  = (255, 255, 255)
GREY   = (130, 130, 130)
DARK   = (18,  18,  28)
GOLD   = (255, 200,  50)
GREEN  = (80,  180,  80)
RED    = (200,  50,  50)
BLUE   = (60,  140, 220)
BROWN  = (139,  90,  43)
ORANGE = (220, 130,  30)
TEAL   = (40,  180, 160)
PURPLE = (150,  70, 210)


# ═══════════════════════════════════════════════════════════
#  BASE GATHERING SKILL
# ═══════════════════════════════════════════════════════════

class GatheringSkill:
    def __init__(self, name, skill_id, color, resources: list):
        self.name      = name
        self.skill_id  = skill_id
        self.color     = color
        self.xp        = 0
        self.resources = resources   # lista de Resource

    @property
    def level(self): return level_for_xp(self.xp)

    @property
    def xp_progress_ratio(self):
        lvl = self.level
        if lvl >= 99: return 1.0
        lo, hi = XP_TABLE[lvl], XP_TABLE[lvl + 1]
        return (self.xp - lo) / (hi - lo)

    def add_xp(self, amount: int) -> dict:
        old = self.level
        self.xp += amount
        new = self.level
        return {"leveled_up": new > old, "old_level": old, "new_level": new}

    def available_resources(self):
        return [r for r in self.resources if self.level >= r.req_level]

    def idle_rate(self) -> float:
        """Recursos/minuto em modo idle (hub, lv 50+)."""
        if self.level < 50: return 0.0
        return 0.5 + (self.level - 50) * 0.03


class Resource:
    def __init__(self, name, req_level, xp_reward, quantity_range=(1, 3),
                 tool_req=None):
        self.name           = name
        self.req_level      = req_level
        self.xp_reward      = xp_reward
        self.quantity_range = quantity_range
        self.tool_req       = tool_req  # nível mínimo de ferramenta

    def roll_quantity(self) -> int:
        return random.randint(*self.quantity_range)


# ═══════════════════════════════════════════════════════════
#  MINI-GAME BASE
# ═══════════════════════════════════════════════════════════

class MiniGame:
    """
    Cada mini-jogo dura N tentativas.
    Resultado: {"success": bool, "score": 0-100, "xp": int, "drops": list}
    """
    def __init__(self, skill: GatheringSkill, resource: Resource,
                 attempts: int = 5):
        self.skill    = skill
        self.resource = resource
        self.attempts = attempts
        self.hits     = 0
        self.done     = False
        self.result   = None
        self._start   = time.time()

    def handle_event(self, event: pygame.event.Event):
        raise NotImplementedError

    def update(self, dt: float):
        raise NotImplementedError

    def draw(self, surface: pygame.Surface, fonts: dict):
        raise NotImplementedError

    def _finish(self, score: int):
        self.done   = True
        xp_gained   = int(self.resource.xp_reward * (0.5 + score / 200))
        qty         = self.resource.roll_quantity() if score >= 40 else 0
        drops       = [(self.resource.name, qty)] if qty > 0 else []
        lu          = self.skill.add_xp(xp_gained)
        self.result = {
            "success" : score >= 40,
            "score"   : score,
            "xp"      : xp_gained,
            "drops"   : drops,
            "levelup" : lu,
        }


# ═══════════════════════════════════════════════════════════
#  MINING — Tap Rítmico (sweet spot)
# ═══════════════════════════════════════════════════════════

class MiningMiniGame(MiniGame):
    """
    Pendulo oscila sobre uma barra; o sweet spot (verde) da bonus.
    Jogador prime ESPACO / clique quando o cursor esta na zona certa.
    """
    BAR_W   = 300
    BAR_H   = 30
    SWEET_W = 60    # largura base do sweet spot

    def __init__(self, skill, resource, attempts=5):
        super().__init__(skill, resource, attempts)
        self._angle   = 0.0       # posição do cursor (0-1)
        self._speed   = 0.6 + skill.level * 0.004   # mais rápido com nível
        self._dir     = 1
        self._scores  = []
        self._flash   = 0.0       # feedback visual (segundos)
        self._flash_c = GREEN
        # sweet spot muda posição a cada tentativa
        self._sweet_x = 0.3 + random.random() * 0.4

    def update(self, dt):
        if self.done: return
        self._angle += self._speed * self._dir * dt
        if self._angle >= 1.0:
            self._angle = 1.0; self._dir = -1
        elif self._angle <= 0.0:
            self._angle = 0.0; self._dir = 1
        if self._flash > 0:
            self._flash -= dt

    def handle_event(self, event):
        if self.done: return
        if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            if (event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE) or \
               event.type == pygame.MOUSEBUTTONDOWN:
                self._strike()

    def _strike(self):
        sw  = self.SWEET_W / self.BAR_W
        dist = abs(self._angle - self._sweet_x)
        if dist < sw * 0.25:
            score = 100; self._flash_c = GOLD
        elif dist < sw * 0.5:
            score = 70;  self._flash_c = GREEN
        elif dist < sw * 0.8:
            score = 40;  self._flash_c = BLUE
        else:
            score = 10;  self._flash_c = RED
        self._scores.append(score)
        self._flash = 0.3
        # novo sweet spot
        self._sweet_x = 0.2 + random.random() * 0.6
        if len(self._scores) >= self.attempts:
            self._finish(int(sum(self._scores) / len(self._scores)))

    def draw(self, surface, fonts):
        W, H = surface.get_size()
        cx, cy = W // 2, H // 2

        # Título
        t = fonts["md"].render(
            f"Mining  {self.resource.name}", True, GOLD)
        surface.blit(t, t.get_rect(center=(cx, cy - 110)))

        # Instrução
        inst = fonts["sm"].render(
            "Press SPACE (or click) when the marker hits the sweet spot!", True, GREY)
        surface.blit(inst, inst.get_rect(center=(cx, cy - 80)))

        # Barra
        bar_x = cx - self.BAR_W // 2
        bar_y = cy - self.BAR_H // 2
        pygame.draw.rect(surface, (50, 50, 60),
                         (bar_x, bar_y, self.BAR_W, self.BAR_H), border_radius=6)

        # Sweet spot
        sw_px = int(self._sweet_x * self.BAR_W)
        sw_w  = self.SWEET_W
        pygame.draw.rect(surface, (40, 160, 60),
                         (bar_x + sw_px - sw_w // 2, bar_y,
                          sw_w, self.BAR_H), border_radius=4)

        # Cursor
        cur_x = bar_x + int(self._angle * self.BAR_W)
        col   = self._flash_c if self._flash > 0 else WHITE
        pygame.draw.rect(surface, col,
                         (cur_x - 4, bar_y - 6, 8, self.BAR_H + 12),
                         border_radius=3)

        # Tentativas restantes
        rem = fonts["sm"].render(
            f"Strikes: {len(self._scores)}/{self.attempts}", True, WHITE)
        surface.blit(rem, rem.get_rect(center=(cx, cy + 40)))

        # Score parcial
        if self._scores:
            avg = int(sum(self._scores) / len(self._scores))
            sc  = fonts["sm"].render(f"Avg score: {avg}", True, GOLD)
            surface.blit(sc, sc.get_rect(center=(cx, cy + 65)))


# ═══════════════════════════════════════════════════════════
#  WOODCUTTING — Tap de Precisão (zonas frágeis)
# ═══════════════════════════════════════════════════════════

class WoodcuttingMiniGame(MiniGame):
    """
    Circulos (zonas frageis) aparecem na arvore e desaparecem.
    Clica dentro do circulo antes que desapareca.
    """
    NUM_ZONES = 6

    def __init__(self, skill, resource, attempts=6):
        super().__init__(skill, resource, attempts)
        self._zones   = []   # lista de {x,y,r,ttl,max_ttl}
        self._scores  = []
        self._misses  = 0
        self._spawn_t = 0.0
        self._spawn_interval = max(0.5, 1.5 - skill.level * 0.01)
        self._spawn_next()

    def _spawn_next(self):
        W, H = 480, 320
        r = random.randint(28, 48)
        x = random.randint(60 + r, W - 60 - r)
        y = random.randint(80 + r, H - 60 - r)
        ttl = max(0.6, 1.8 - self.skill.level * 0.012)
        self._zones.append({"x": x, "y": y, "r": r,
                             "ttl": ttl, "max_ttl": ttl})

    def update(self, dt):
        if self.done: return
        self._spawn_t += dt
        # Tick zonas
        for z in self._zones[:]:
            z["ttl"] -= dt
            if z["ttl"] <= 0:
                self._zones.remove(z)
                self._misses += 1
                self._scores.append(0)
                if len(self._scores) >= self.attempts:
                    self._finish(int(sum(self._scores) / len(self._scores)))
                    return
        # Spawn
        if (self._spawn_t >= self._spawn_interval and
                len(self._zones) < 3 and
                len(self._scores) < self.attempts):
            self._spawn_next()
            self._spawn_t = 0

    def handle_event(self, event):
        if self.done: return
        if event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos
            # offset para centro do ecrã
            W, H = pygame.display.get_surface().get_size()
            ox, oy = W // 2 - 240, H // 2 - 160
            for z in self._zones[:]:
                dx, dy = (mx - ox) - z["x"], (my - oy) - z["y"]
                if math.hypot(dx, dy) <= z["r"]:
                    ratio = z["ttl"] / z["max_ttl"]
                    score = int(40 + 60 * ratio)  # mais rápido = mais pontos
                    self._scores.append(score)
                    self._zones.remove(z)
                    if len(self._scores) >= self.attempts:
                        self._finish(int(sum(self._scores) /
                                        len(self._scores)))
                    return

    def draw(self, surface, fonts):
        W, H = surface.get_size()
        cx, cy = W // 2, H // 2
        ox, oy = cx - 240, cy - 160

        t = fonts["md"].render(
            f"Woodcutting  {self.resource.name}", True, GREEN)
        surface.blit(t, t.get_rect(center=(cx, oy - 30)))

        inst = fonts["sm"].render(
            "Click the weak spots before they disappear!", True, GREY)
        surface.blit(inst, inst.get_rect(center=(cx, oy - 10)))

        # Zona de jogo
        pygame.draw.rect(surface, (25, 35, 25),
                         (ox, oy, 480, 320), border_radius=10)
        pygame.draw.rect(surface, GREEN,
                         (ox, oy, 480, 320), width=2, border_radius=10)

        for z in self._zones:
            ratio = z["ttl"] / z["max_ttl"]
            # cor verde → vermelho conforme ttl diminui
            r_c = int(80 + 175 * (1 - ratio))
            g_c = int(200 * ratio)
            col = (r_c, g_c, 40)
            pygame.draw.circle(surface, col,
                                (ox + z["x"], oy + z["y"]), z["r"])
            pygame.draw.circle(surface, WHITE,
                                (ox + z["x"], oy + z["y"]), z["r"], 2)
            # barra ttl
            bar_w = int(z["r"] * 2 * ratio)
            pygame.draw.rect(surface, col,
                             (ox + z["x"] - z["r"],
                              oy + z["y"] + z["r"] + 4,
                              bar_w, 5), border_radius=2)

        rem = fonts["sm"].render(
            f"Hits: {len(self._scores)}/{self.attempts}  "
            f"Misses: {self._misses}", True, WHITE)
        surface.blit(rem, rem.get_rect(center=(cx, oy + 335)))


# ═══════════════════════════════════════════════════════════
#  FISHING — Quick-time (tensão da linha)
# ═══════════════════════════════════════════════════════════

class FishingMiniGame(MiniGame):
    """
    Barra de tensao sobe/desce aleatoriamente.
    Mante ESPACO premido para puxar a linha.
    Mante a tensao na zona verde (nao demasiado, nao demasiado pouco).
    """
    def __init__(self, skill, resource, attempts=1):
        super().__init__(skill, resource, attempts)
        self._tension    = 0.5   # 0.0 - 1.0
        self._pull       = False
        self._fish_force = 0.0
        self._time_total = 8.0   # segundos para apanhar
        self._time_left  = self._time_total
        self._progress   = 0.0   # 0 → 1 (peixe apanhado)
        self._good_time  = 0.0   # tempo na zona verde
        self._bad_time   = 0.0
        # zona verde: 0.35–0.65 de tensão
        self._green_lo   = 0.35
        self._green_hi   = 0.65
        self._fish_dir   = 1
        self._fish_t     = 0.0

    def handle_event(self, event):
        if self.done: return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self._pull = True
        if event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            self._pull = False
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._pull = True
        if event.type == pygame.MOUSEBUTTONUP:
            self._pull = False

    def update(self, dt):
        if self.done: return
        self._time_left -= dt
        if self._time_left <= 0:
            score = int(self._good_time / self._time_total * 100)
            self._finish(score)
            return

        # Força do peixe (aleatória com oscilação)
        self._fish_t += dt
        self._fish_force = 0.3 + 0.25 * math.sin(
            self._fish_t * (1.5 + self.skill.level * 0.02)) + \
            random.uniform(-0.05, 0.05)

        # Tensão
        pull_force = 0.6 if self._pull else 0.0
        delta = pull_force - self._fish_force
        self._tension = max(0.0, min(1.0, self._tension + delta * dt))

        # Progresso
        in_zone = self._green_lo <= self._tension <= self._green_hi
        if in_zone:
            self._progress = min(1.0, self._progress + dt * 0.15)
            self._good_time += dt
        else:
            self._progress = max(0.0, self._progress - dt * 0.08)

        # Linha rebentada ou peixe apanhado
        if self._tension >= 0.95:
            self._finish(10)   # linha rebentada
        elif self._progress >= 1.0:
            self._finish(95)   # peixe apanhado!

    def draw(self, surface, fonts):
        W, H = surface.get_size()
        cx, cy = W // 2, H // 2

        t = fonts["md"].render(
            f"Fishing  {self.resource.name}", True, TEAL)
        surface.blit(t, t.get_rect(center=(cx, cy - 130)))

        inst = fonts["sm"].render(
            "Hold SPACE (or click) to reel in - keep tension in the green zone!",
            True, GREY)
        surface.blit(inst, inst.get_rect(center=(cx, cy - 105)))

        # Barra de tensão vertical
        bar_h  = 200
        bar_w  = 28
        bar_x  = cx - bar_w // 2
        bar_y  = cy - bar_h // 2
        pygame.draw.rect(surface, (40, 40, 55),
                         (bar_x, bar_y, bar_w, bar_h), border_radius=8)

        # Zona verde
        gz_y = bar_y + int(self._green_lo * bar_h)
        gz_h = int((self._green_hi - self._green_lo) * bar_h)
        pygame.draw.rect(surface, (30, 120, 50),
                         (bar_x, gz_y, bar_w, gz_h))

        # Fill tensão
        fill_h = int(self._tension * bar_h)
        t_col  = RED if self._tension > 0.85 else \
                 GOLD if self._tension > self._green_hi else \
                 GREEN if self._tension >= self._green_lo else BLUE
        pygame.draw.rect(surface, t_col,
                         (bar_x, bar_y + bar_h - fill_h,
                          bar_w, fill_h), border_radius=6)
        pygame.draw.rect(surface, WHITE,
                         (bar_x, bar_y, bar_w, bar_h), width=2, border_radius=8)

        # Label
        ten_lbl = fonts["sm"].render("Tension", True, WHITE)
        surface.blit(ten_lbl, ten_lbl.get_rect(center=(cx, bar_y - 18)))

        # Barra de progresso (peixe)
        prog_w = 220
        prog_x = cx - prog_w // 2
        prog_y = cy + 115
        pygame.draw.rect(surface, (40, 40, 55),
                         (prog_x, prog_y, prog_w, 18), border_radius=6)
        fill_p = int(self._progress * prog_w)
        if fill_p > 0:
            pygame.draw.rect(surface, TEAL,
                             (prog_x, prog_y, fill_p, 18), border_radius=6)
        pygame.draw.rect(surface, WHITE,
                         (prog_x, prog_y, prog_w, 18), width=2, border_radius=6)
        p_lbl = fonts["sm"].render("Fish Progress", True, WHITE)
        surface.blit(p_lbl, p_lbl.get_rect(center=(cx, prog_y - 16)))

        # Tempo restante
        tr = fonts["sm"].render(
            f"Time: {self._time_left:.1f}s", True, WHITE)
        surface.blit(tr, tr.get_rect(center=(cx, prog_y + 34)))


# ═══════════════════════════════════════════════════════════
#  FARMING — Tap de Precisão com timing de colheita
# ═══════════════════════════════════════════════════════════

class FarmingMiniGame(MiniGame):
    """
    Um indicador sobe numa barra (maturidade da planta).
    Colhe no momento certo (zona dourada) para qualidade maxima.
    Colheita cedo - menos quantidade. Colheita tarde - planta morre.
    """
    def __init__(self, skill, resource, attempts=4):
        super().__init__(skill, resource, attempts)
        self._growth    = 0.0       # 0 → 1
        self._speed     = 0.08 + skill.level * 0.001
        self._scores    = []
        self._phase     = "growing"  # "growing" | "flash"
        self._flash_t   = 0.0
        self._flash_col = GREEN
        # zona dourada: 0.60 – 0.85
        self._gold_lo   = 0.60
        self._gold_hi   = 0.85

    def update(self, dt):
        if self.done: return
        if self._phase == "growing":
            self._growth += self._speed * dt
            if self._growth >= 1.0:
                # Planta morreu (colheita demasiado tarde)
                self._scores.append(0)
                self._next_plant()
        elif self._phase == "flash":
            self._flash_t -= dt
            if self._flash_t <= 0:
                self._phase = "growing"

    def handle_event(self, event):
        if self.done: return
        if self._phase != "growing": return
        if event.type in (pygame.MOUSEBUTTONDOWN,) or \
           (event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE):
            g = self._growth
            if self._gold_lo <= g <= self._gold_hi:
                score = int(70 + 30 * (1 - abs(g - 0.725) / 0.125))
                self._flash_col = GOLD
            elif g < self._gold_lo:
                score = int(g / self._gold_lo * 50)
                self._flash_col = BLUE
            else:
                score = max(5, int((1 - g) / (1 - self._gold_hi) * 40))
                self._flash_col = ORANGE
            self._scores.append(score)
            self._next_plant()

    def _next_plant(self):
        if len(self._scores) >= self.attempts:
            self._finish(int(sum(self._scores) / len(self._scores)))
            return
        self._growth  = 0.0
        self._phase   = "flash"
        self._flash_t = 0.4
        self._speed   = 0.08 + self.skill.level * 0.001 + \
                        random.uniform(0, 0.02)

    def draw(self, surface, fonts):
        W, H = surface.get_size()
        cx, cy = W // 2, H // 2

        t = fonts["md"].render(
            f"Farming  {self.resource.name}", True, ORANGE)
        surface.blit(t, t.get_rect(center=(cx, cy - 130)))

        inst = fonts["sm"].render(
            "Press SPACE (or click) when the plant is in the golden zone!",
            True, GREY)
        surface.blit(inst, inst.get_rect(center=(cx, cy - 105)))

        # Barra de crescimento vertical
        bar_h = 200
        bar_w = 36
        bar_x = cx - bar_w // 2
        bar_y = cy - bar_h // 2
        pygame.draw.rect(surface, (40, 40, 30),
                         (bar_x, bar_y, bar_w, bar_h), border_radius=8)

        # Zona dourada
        gz_top = bar_y + int((1 - self._gold_hi) * bar_h)
        gz_h   = int((self._gold_hi - self._gold_lo) * bar_h)
        pygame.draw.rect(surface, (140, 110, 20),
                         (bar_x, gz_top, bar_w, gz_h))

        # Fill crescimento (de baixo para cima)
        fill_h = int(self._growth * bar_h)
        g      = self._growth
        if g < self._gold_lo:
            col = (60, 160, 60)
        elif g <= self._gold_hi:
            col = GOLD
        else:
            col = RED
        if self._phase == "flash":
            col = self._flash_col
        pygame.draw.rect(surface, col,
                         (bar_x, bar_y + bar_h - fill_h,
                          bar_w, fill_h), border_radius=6)
        pygame.draw.rect(surface, WHITE,
                         (bar_x, bar_y, bar_w, bar_h), width=2, border_radius=8)

        # Labels zona
        gl = fonts["sm"].render("Golden zone", True, GOLD)
        surface.blit(gl, (bar_x + bar_w + 10, gz_top + gz_h // 2 - 8))

        # Tentativas
        rem = fonts["sm"].render(
            f"Plants: {len(self._scores)}/{self.attempts}", True, WHITE)
        surface.blit(rem, rem.get_rect(center=(cx, cy + 120)))

        if self._scores:
            avg = int(sum(self._scores) / len(self._scores))
            sc  = fonts["sm"].render(f"Avg quality: {avg}%", True, GOLD)
            surface.blit(sc, sc.get_rect(center=(cx, cy + 145)))


# ═══════════════════════════════════════════════════════════
#  SKILL DEFINITIONS
# ═══════════════════════════════════════════════════════════

def make_mining() -> GatheringSkill:
    resources = [
        Resource("Copper Ore",    1,  15, (1, 3)),
        Resource("Tin Ore",       1,  15, (1, 3)),
        Resource("Iron Ore",     15,  35, (1, 2)),
        Resource("Coal",         20,  40, (1, 2)),
        Resource("Mithril Ore",  35,  60, (1, 2)),
        Resource("Adamantite",   50,  90, (1, 1)),
        Resource("Runite Ore",   55, 110, (1, 1)),
        Resource("Magic Crystal",70, 150, (1, 1)),
        Resource("Legendary Ore",90, 250, (1, 1)),
    ]
    return GatheringSkill("Mining", "mining", GREY, resources)

def make_woodcutting() -> GatheringSkill:
    resources = [
        Resource("Pine Log",      1,  12, (2, 4)),
        Resource("Oak Log",       5,  20, (2, 3)),
        Resource("Willow Log",   15,  35, (1, 3)),
        Resource("Maple Log",    25,  50, (1, 2)),
        Resource("Yew Log",      40,  75, (1, 2)),
        Resource("Magic Log",    60, 110, (1, 1)),
        Resource("Enchanted Log",75, 160, (1, 1)),
        Resource("Legendary Log",90, 280, (1, 1)),
    ]
    return GatheringSkill("Woodcutting", "woodcutting", (100, 180, 60), resources)

def make_fishing() -> GatheringSkill:
    resources = [
        Resource("Sardine",       1,  10, (1, 3)),
        Resource("Trout",         5,  20, (1, 2)),
        Resource("Salmon",       15,  35, (1, 2)),
        Resource("Tuna",         25,  50, (1, 2)),
        Resource("Swordfish",    40,  80, (1, 1)),
        Resource("Squid",        50,  95, (1, 1)),
        Resource("Abyssal Fish", 65, 140, (1, 1)),
        Resource("Legendary Fish",80,220, (1, 1)),
    ]
    return GatheringSkill("Fishing", "fishing", TEAL, resources)

def make_farming() -> GatheringSkill:
    resources = [
        Resource("Guam Herb",     1,  14, (1, 3)),
        Resource("Marrentill",    5,  22, (1, 2)),
        Resource("Tarromin",     15,  38, (1, 2)),
        Resource("Harralander",  25,  55, (1, 2)),
        Resource("Ranarr",       35,  80, (1, 1)),
        Resource("Snapdragon",   50, 110, (1, 1)),
        Resource("Toadflax",     60, 140, (1, 1)),
        Resource("Magic Herb",   75, 200, (1, 1)),
        Resource("Legendary Seed",90,320, (1, 1)),
    ]
    return GatheringSkill("Farming", "farming", (160, 220, 80), resources)


# Mini-jogo associado a cada skill
MINIGAME_CLASS = {
    "mining"     : MiningMiniGame,
    "woodcutting": WoodcuttingMiniGame,
    "fishing"    : FishingMiniGame,
    "farming"    : FarmingMiniGame,
}


# ═══════════════════════════════════════════════════════════
#  PLAYER GATHERING SKILLS  (agrupa as 4)
# ═══════════════════════════════════════════════════════════

class PlayerGatheringSkills:
    """
    Attach ao Player:
        self.gathering = PlayerGatheringSkills()

    Acesso:
        player.gathering.mining.level
        player.gathering.start_minigame("mining", resource)
    """
    def __init__(self):
        self.mining      = make_mining()
        self.woodcutting = make_woodcutting()
        self.fishing     = make_fishing()
        self.farming     = make_farming()
        self._skills     = {
            "mining"     : self.mining,
            "woodcutting": self.woodcutting,
            "fishing"    : self.fishing,
            "farming"    : self.farming,
        }
        self._active_minigame: MiniGame | None = None

    def get(self, skill_id: str) -> GatheringSkill:
        return self._skills[skill_id]

    def all(self) -> dict:
        return self._skills

    def start_minigame(self, skill_id: str,
                       resource: Resource | None = None) -> MiniGame:
        skill = self._skills[skill_id]
        if resource is None:
            avail = skill.available_resources()
            resource = avail[-1] if avail else skill.resources[0]
        cls = MINIGAME_CLASS[skill_id]
        self._active_minigame = cls(skill, resource)
        return self._active_minigame

    @property
    def active_minigame(self) -> MiniGame | None:
        return self._active_minigame

    def clear_minigame(self):
        self._active_minigame = None

    def idle_tick(self, dt: float) -> list[tuple[str, str, int]]:
        """
        Chama no game loop para skills idle (lv 50+ no hub).
        Devolve lista de (skill_id, resource_name, qty) drops gerados.
        """
        drops = []
        for sid, skill in self._skills.items():
            rate = skill.idle_rate()
            if rate > 0 and random.random() < rate * dt / 60:
                avail = skill.available_resources()
                if avail:
                    res = avail[-1]
                    qty = res.roll_quantity()
                    skill.add_xp(int(res.xp_reward * 0.5))
                    drops.append((sid, res.name, qty))
        return drops

    def summary(self) -> dict:
        return {sid: {"level": s.level, "xp": s.xp}
                for sid, s in self._skills.items()}
