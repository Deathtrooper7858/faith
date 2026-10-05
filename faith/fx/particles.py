"""Partículas baratas (rectángulos/círculos directos a pantalla) y textos flotantes."""
import math
import random
import pygame
from .. import settings as S

_rng = random.Random()
MAX_PARTICLES = 700


class ParticleSystem:
    def __init__(self):
        self.p = []          # [x, y, vx, vy, life, max, size, color, gravity, kind]
        self.texts = []      # [x, y, vy, life, max, surface]
        self._font = None
        self._text_cache = {}

    # ── emisores ─────────────────────────────────────────────────────────
    def _add(self, *a):
        if len(self.p) < MAX_PARTICLES:
            self.p.append(list(a))

    def burst(self, x, y, colors, n=10, speed=(40, 150), life=(0.3, 0.7), size=(2, 5), gravity=420, up=60,
              kind="rect"):
        for _ in range(n):
            ang = _rng.uniform(0, math.tau)
            sp = _rng.uniform(*speed)
            l = _rng.uniform(*life)
            self._add(x, y, math.cos(ang) * sp, math.sin(ang) * sp - up, l, l, _rng.uniform(*size),
                      _rng.choice(colors), gravity, kind)

    def chips(self, x, y, kind, n=8):
        pal = {"wood": [(139, 90, 50), (170, 112, 62), (104, 66, 36)],
               "leaf": [(66, 150, 70), (98, 180, 84), (44, 112, 56)],
               "stone": [(150, 150, 160), (110, 110, 122), (190, 190, 200)],
               "blood": [(168, 30, 36), (210, 52, 52)],
               "bone": [(230, 226, 210), (190, 184, 168)],
               "spark": [(255, 226, 120), (255, 170, 60)],
               "water": [(130, 190, 240), (200, 230, 250)],
               "dust": [(150, 140, 120), (180, 170, 150)],
               "snow": [(240, 246, 255), (210, 224, 240)]}[kind]
        self.burst(x, y, pal, n=n, kind="spark" if kind == "spark" else "rect",
                   gravity=0 if kind == "spark" else 460, speed=(60, 200) if kind == "spark" else (40, 140))

    def smoke(self, x, y, n=3):
        for _ in range(n):
            l = _rng.uniform(0.8, 1.6)
            g = _rng.randint(80, 150)
            self._add(x + _rng.uniform(-6, 6), y, _rng.uniform(-10, 10), _rng.uniform(-40, -18), l, l,
                      _rng.uniform(4, 8), (g, g, g), -10, "smoke")

    def ember(self, x, y, n=2):
        for _ in range(n):
            l = _rng.uniform(0.5, 1.1)
            self._add(x + _rng.uniform(-8, 8), y, _rng.uniform(-14, 14), _rng.uniform(-60, -25), l, l, 2,
                      (255, 170, 70), -20, "spark")

    def ring(self, x, y, color=(255, 255, 255)):
        self._add(x, y, 0, 0, 0.28, 0.28, 8, color, 0, "ring")

    def slash(self, x, y, angle, color=(255, 255, 255)):
        self._add(x, y, math.cos(angle), math.sin(angle), 0.16, 0.16, 30, color, 0, "slash")

    def text(self, x, y, msg, color=(255, 255, 255), size=22):
        key = (msg, color, size)
        surf = self._text_cache.get(key)
        if surf is None:
            if self._font is None or self._font[0] != size:
                self._font = (size, pygame.font.Font(None, size))
            f = self._font[1]
            base = f.render(msg, True, color)
            sh = f.render(msg, True, (0, 0, 0))
            surf = pygame.Surface((base.get_width() + 2, base.get_height() + 2), pygame.SRCALPHA)
            surf.blit(sh, (2, 2))
            surf.blit(base, (0, 0))
            if len(self._text_cache) > 200:
                self._text_cache.clear()
            self._text_cache[key] = surf
        self.texts.append([x - surf.get_width() / 2, y, -42.0, 0.9, 0.9, surf])

    # ── ciclo ────────────────────────────────────────────────────────────
    def update(self, dt):
        alive = []
        for q in self.p:
            q[4] -= dt
            if q[4] <= 0:
                continue
            q[0] += q[2] * dt
            q[1] += q[3] * dt
            q[3] += q[8] * dt
            if q[9] == "smoke":
                q[6] += dt * 5
            alive.append(q)
        self.p = alive
        t2 = []
        for t in self.texts:
            t[3] -= dt
            if t[3] > 0:
                t[1] += t[2] * dt
                t[2] *= 0.92
                t2.append(t)
        self.texts = t2

    def draw(self, surf, cx, cy):
        W, H = S.SCREEN_W, S.SCREEN_H
        for x, y, vx, vy, life, mx, size, col, g, kind in self.p:
            sx, sy = int(x - cx), int(y - cy)
            if sx < -20 or sy < -20 or sx > W + 20 or sy > H + 20:
                continue
            k = life / mx
            if kind == "rect":
                s = max(1, int(size * (0.5 + 0.5 * k)))
                pygame.draw.rect(surf, col, (sx, sy, s, s))
            elif kind == "spark":
                s = max(1, int(size * k) + 1)
                pygame.draw.rect(surf, col, (sx, sy, s, s))
            elif kind == "smoke":
                s = int(size)
                d = pygame.Surface((s * 2, s * 2), pygame.SRCALPHA)
                pygame.draw.circle(d, (*col, int(110 * k)), (s, s), s)
                surf.blit(d, (sx - s, sy - s))
            elif kind == "ring":
                r = int(size + (1 - k) * 26)
                pygame.draw.circle(surf, col, (sx, sy), r, 2)
            elif kind == "slash":
                ang = math.atan2(vy, vx)
                r = size + 6 * (1 - k)
                rect = pygame.Rect(sx - int(r), sy - int(r), int(r * 2), int(r * 2))
                pygame.draw.arc(surf, col, rect, -ang - 1.0, -ang + 1.0, 3)

    def draw_texts(self, surf, cx, cy):
        for x, y, vy, life, mx, s in self.texts:
            a = min(1.0, life / mx * 1.8)
            if a < 1.0:
                s = s.copy()
                s.set_alpha(int(255 * a))
            surf.blit(s, (int(x - cx), int(y - cy)))
