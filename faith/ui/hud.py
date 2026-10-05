"""HUD de juego: vitales, hotbar, reloj, minimapa, avisos y retícula."""
import math
import pygame
from .. import items, settings as S
from ..fx import lighting
from ..inventory import Inventory
from . import widgets as W
from .minimap import Minimap

SLOT = 54
GAP = 6


def hotbar_rect(i):
    total = S.HOTBAR_SLOTS * SLOT + (S.HOTBAR_SLOTS - 1) * GAP
    x0 = (S.SCREEN_W - total) // 2
    return pygame.Rect(x0 + i * (SLOT + GAP), S.SCREEN_H - SLOT - 14, SLOT, SLOT)


def draw_item_in(surf, rect, stack, size=40, show_count=True):
    ic = items.icon(stack.id, size)
    surf.blit(ic, (rect.centerx - ic.get_width() // 2, rect.centery - ic.get_height() // 2 - 1))
    if show_count and stack.count > 1:
        W.text(surf, str(stack.count), (rect.right - 5, rect.bottom - 3), 20, S.C_TEXT, "bottomright")
    d = stack.d
    if d.durability and stack.dur is not None and stack.dur < d.durability:
        f = max(0.0, stack.dur / d.durability)
        col = (110, 220, 110) if f > 0.5 else (230, 200, 70) if f > 0.2 else (230, 80, 70)
        pygame.draw.rect(surf, (10, 10, 14), (rect.x + 6, rect.bottom - 8, rect.w - 12, 4))
        pygame.draw.rect(surf, col, (rect.x + 7, rect.bottom - 7, int((rect.w - 14) * f), 2))


def draw_slot(surf, rect, stack=None, selected=False, hover=False, fill=S.C_SLOT, edge=S.C_SLOT_EDGE, size=40):
    r = pygame.Rect(rect)
    pygame.draw.rect(surf, (8, 9, 14), r.inflate(4, 4), border_radius=8)
    pygame.draw.rect(surf, S.C_SLOT_HOVER if hover else fill, r, border_radius=7)
    pygame.draw.rect(surf, S.C_GOLD if selected else edge, r, 3 if selected else 2, border_radius=7)
    if stack:
        draw_item_in(surf, r, stack, size)


class Toasts:
    def __init__(self):
        self.items = []      # [texto, color, vida, icono, id, n]

    def add(self, text, color=S.C_TEXT, icon=None, key=None, n=0):
        if key is None:
            for t in self.items:                      # los avisos repetidos sólo refrescan su vida
                if t[0] == text and t[4] is None:
                    t[2] = 3.0
                    return
        for t in self.items:
            if key and t[4] == key and t[2] > 0.4:
                t[5] += n
                t[0] = f"+{t[5]} {text}"
                t[2] = 3.0
                return
        self.items.append([f"+{n} {text}" if key else text, color, 3.0, icon, key, n])
        if len(self.items) > 7:
            self.items.pop(0)

    def update(self, dt):
        for t in self.items:
            t[2] -= dt
        self.items = [t for t in self.items if t[2] > 0]

    def draw(self, surf):
        y = S.SCREEN_H // 2 + 40
        for text, col, life, icon, _k, _n in reversed(self.items):
            a = min(1.0, life / 0.6)
            s = W.render(text, 24, col)
            w = s.get_width() + (36 if icon else 0) + 18
            panel = W.panel_surface(w, 34, int(170 * a), 9, (60, 64, 90))
            surf.blit(panel, (16, y))
            x = 26
            if icon:
                ic = items.icon(icon, 26)
                if a < 1.0:
                    ic = ic.copy(); ic.set_alpha(int(255 * a))
                surf.blit(ic, (x, y + 4))
                x += 32
            if a < 1.0:
                s = s.copy(); s.set_alpha(int(255 * a))
            surf.blit(s, (x, y + 7))
            y += 38


class HUD:
    def __init__(self):
        self.toasts = Toasts()
        self.minimap = Minimap()
        self.held_name_t = 0.0
        self.last_sel = -1
        self.vignette = self._make_vignette()
        self.vig_red = self.vignette.copy()
        self.vig_red.fill((230, 20, 20, 255), special_flags=pygame.BLEND_RGBA_MULT)
        self.cursor_t = 0.0
        self.banner = None          # (texto, subtítulo, vida)

    def _make_vignette(self):
        w, h = S.SCREEN_W // 8, S.SCREEN_H // 8
        v = pygame.Surface((w, h), pygame.SRCALPHA)
        cx, cy = w / 2, h / 2
        for y in range(h):
            for x in range(w):
                d = math.hypot((x - cx) / cx, (y - cy) / cy)
                a = max(0.0, min(1.0, (d - 0.62) / 0.55))
                v.set_at((x, y), (255, 255, 255, int(255 * a * a)))
        return pygame.transform.smoothscale(v, (S.SCREEN_W, S.SCREEN_H))

    def show_banner(self, title, sub="", life=3.2):
        self.banner = [title, sub, life, life]

    def update(self, dt, player):
        self.toasts.update(dt)
        if player.inv.selected != self.last_sel:
            self.last_sel = player.inv.selected
            self.held_name_t = 2.2
        self.held_name_t = max(0.0, self.held_name_t - dt)
        if self.banner:
            self.banner[2] -= dt
            if self.banner[2] <= 0:
                self.banner = None

    # ── dibujo ────────────────────────────────────────────────────────────
    def draw(self, surf, game):
        p = game.player
        self._vignette(surf, p, game)
        self._vitals(surf, p)
        self._hotbar(surf, p)
        self._clock(surf, game)
        self.minimap.draw(surf, game.level, p, (S.SCREEN_W - 236, 20), game.level.t)
        self.toasts.draw(surf)
        self._prompt(surf, game)
        self._banner(surf)
        self._enemy_alert(surf, game)

    def _vignette(self, surf, p, game):
        frac = p.hp / S.MAX_HEALTH
        if frac < 0.4 or p.food <= 0 or p.thirst <= 0:
            k = (1 - frac / 0.4) if frac < 0.4 else 0.5
            pulse = 0.65 + 0.35 * math.sin(pygame.time.get_ticks() / 240.0)
            self.vig_red.set_alpha(int(255 * min(1, k * pulse)))
            surf.blit(self.vig_red, (0, 0))

    def _vitals(self, surf, p):
        x, y, w, h = 16, S.SCREEN_H - 136, 262, 118
        W.panel(surf, (x, y, w, h), 215, 12)
        rows = [("hp", p.hp, S.MAX_HEALTH, S.C_HP), ("food", p.food, S.MAX_FOOD, S.C_FOOD),
                ("thirst", p.thirst, S.MAX_THIRST, S.C_WATER), ("stam", p.stamina, S.MAX_STAMINA, S.C_STAMINA)]
        for i, (k, v, mx, col) in enumerate(rows):
            ry = y + 14 + i * 24
            if k == "hp":
                W.heart(surf, x + 22, ry + 6, 8, col)
            elif k == "food":
                surf.blit(items.icon("apple", 22), (x + 11, ry - 5))
            elif k == "thirst":
                surf.blit(items.icon("bwater", 22), (x + 11, ry - 5))
            else:
                W.bolt(surf, x + 22, ry + 6, col)
            low = v / mx < 0.22
            W.bar(surf, x + 42, ry, 150, 13, v / mx, (225, 70, 60) if low and k != "stam" else col, flash=low and k != "stam")
            W.text(surf, f"{int(math.ceil(v))}", (x + 202, ry - 2), 22, S.C_TEXT)
        # defensa
        d = p.inv.defense()
        if d > 0:
            W.text(surf, f"DEF {d}", (x + 214, y + 14 + 3 * 24 - 2), 20, (160, 220, 160))

    def _hotbar(self, surf, p):
        mx, my = pygame.mouse.get_pos()
        for i in range(S.HOTBAR_SLOTS):
            r = hotbar_rect(i)
            sel = i == p.inv.selected
            rr = r.inflate(6, 6) if sel else r
            if sel:
                rr.y -= 4
            draw_slot(surf, rr, p.inv.slots[i], selected=sel)
            W.text(surf, str(i + 1), (r.x + 6, r.y + 4), 18, S.C_DIM if not sel else S.C_GOLD)
        if self.held_name_t > 0:
            h = p.inv.held()
            if h:
                a = min(1.0, self.held_name_t / 0.6)
                s = W.render(h.d.name, 28, S.C_GOLD)
                if a < 1.0:
                    s = s.copy(); s.set_alpha(int(255 * a))
                surf.blit(s, (S.SCREEN_W // 2 - s.get_width() // 2, S.SCREEN_H - SLOT - 54))

    def _clock(self, surf, game):
        W.panel(surf, (16, 16, 188, 62), 215, 12)
        t = game.time_frac
        hour = (t * 24) % 24
        day = 6 <= hour < 18
        cx, cy = 44, 47
        pygame.draw.circle(surf, (255, 222, 110) if day else (214, 220, 240), (cx, cy), 12)
        if not day:
            pygame.draw.circle(surf, (18, 20, 30), (cx + 5, cy - 3), 10)
        else:
            for a in range(8):
                ang = a * math.pi / 4
                pygame.draw.line(surf, (255, 222, 110), (cx + math.cos(ang) * 15, cy + math.sin(ang) * 15),
                                 (cx + math.cos(ang) * 19, cy + math.sin(ang) * 19), 2)
        W.text(surf, lighting.clock_text(t), (70, 22), 34, S.C_TEXT)
        label = f"Día {game.day}" + ("  ·  " + ("Lluvia" if not game.weather.snow else "Nevada") if game.weather.raining and not game.level.is_cave else "")
        if game.level.is_cave:
            label = "Cueva"
        W.text(surf, label, (70, 54), 20, S.C_DIM)

    def _prompt(self, surf, game):
        if game.ui_open or not game.focus_text:
            return
        s = W.render(game.focus_text, 28, S.C_GOLD)
        w = s.get_width() + 36
        x = S.SCREEN_W // 2 - w // 2
        y = S.SCREEN_H - SLOT - 108
        W.panel(surf, (x, y, w, 40), 215, 10, (140, 120, 60))
        surf.blit(s, (x + 18, y + 9))

    def _banner(self, surf):
        if not self.banner:
            return
        title, sub, life, total = self.banner
        a = min(1.0, life / 0.7, (total - life) / 0.5)
        s = W.render(title, 62, S.C_GOLD).copy()
        s.set_alpha(int(255 * a))
        surf.blit(s, (S.SCREEN_W // 2 - s.get_width() // 2, 130))
        if sub:
            s2 = W.render(sub, 28, S.C_TEXT).copy()
            s2.set_alpha(int(220 * a))
            surf.blit(s2, (S.SCREEN_W // 2 - s2.get_width() // 2, 192))

    def _enemy_alert(self, surf, game):
        """Flechas en el borde de la pantalla hacia enemigos cercanos fuera de vista."""
        p = game.player
        cx, cy = S.SCREEN_W / 2, S.SCREEN_H / 2
        for m in game.level.mobs:
            if not m.hostile or m.dying:
                continue
            dx, dy = m.x - p.x, m.y - p.y
            d = math.hypot(dx, dy)
            if d > 900 or (abs(dx) < cx - 20 and abs(dy) < cy - 20):
                continue
            ang = math.atan2(dy, dx)
            ex = cx + math.cos(ang) * (cx - 30)
            ey = cy + math.sin(ang) * (cy - 30)
            ex = max(30, min(S.SCREEN_W - 30, ex)); ey = max(30, min(S.SCREEN_H - 30, ey))
            a = max(0.2, 1.0 - d / 900.0)
            c = (int(230 * a + 25), int(60 * a + 20), int(60 * a + 20))
            pts = [(ex + math.cos(ang) * 11, ey + math.sin(ang) * 11),
                   (ex + math.cos(ang + 2.5) * 9, ey + math.sin(ang + 2.5) * 9),
                   (ex + math.cos(ang - 2.5) * 9, ey + math.sin(ang - 2.5) * 9)]
            pygame.draw.polygon(surf, c, pts)

    def draw_cursor(self, surf, active):
        mx, my = pygame.mouse.get_pos()
        col = S.C_GOLD if active else (235, 235, 245)
        pygame.draw.circle(surf, (0, 0, 0), (mx, my), 8, 2)
        pygame.draw.circle(surf, col, (mx, my), 7, 1)
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            pygame.draw.line(surf, col, (mx + dx * 10, my + dy * 10), (mx + dx * 14, my + dy * 14), 2)
