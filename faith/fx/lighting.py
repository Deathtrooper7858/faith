"""Ciclo día/noche, iluminación dinámica (a baja resolución) y clima."""
import math
import random
import pygame
from .. import settings as S
from ..util import lerp, clamp

SCALE = 4   # la capa de luz se calcula a 1/4 de resolución y se amplía suavemente

# (hora 0..1, multiplicador de color de la luz ambiente, oscuridad 0..255 para la lógica del juego)
_KEYS = [
    (0.00, (50, 62, 124), 205),
    (0.20, (52, 64, 128), 200),
    (0.265, (190, 120, 112), 110),
    (0.32, (255, 206, 172), 36),
    (0.40, (255, 255, 255), 0),
    (0.64, (255, 255, 255), 0),
    (0.72, (255, 202, 152), 54),
    (0.79, (172, 96, 112), 130),
    (0.86, (54, 64, 126), 196),
    (1.00, (50, 62, 124), 205),
]


def ambient(t):
    """(color multiplicador, oscuridad) para la hora del día t (0..1; 0 = medianoche)."""
    t = t % 1.0
    for (t0, c0, a0), (t1, c1, a1) in zip(_KEYS, _KEYS[1:]):
        if t0 <= t <= t1:
            k = (t - t0) / (t1 - t0)
            k = k * k * (3 - 2 * k)
            return tuple(int(lerp(c0[i], c1[i], k)) for i in range(3)), lerp(a0, a1, k)
    return _KEYS[0][1], _KEYS[0][2]


def clock_text(t):
    minutes = int(((t * 24.0) % 24.0) * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


_glow_cache = {}


def _glow(radius, color, intensity):
    """Gradiente radial de luz de color (se SUMA a la capa ambiente)."""
    key = (int(radius), color, int(intensity) // 8)
    s = _glow_cache.get(key)
    if s is None:
        r = max(3, int(radius))
        s = pygame.Surface((r * 2, r * 2))
        s.fill((0, 0, 0))
        k_int = (int(intensity) // 8 * 8) / 255.0
        steps = max(8, min(40, r))
        for i in range(steps):
            k = i / steps                       # 0 = borde, 1 = centro
            f = (k ** 1.15) * k_int
            c = (int(color[0] * f), int(color[1] * f), int(color[2] * f))
            pygame.draw.circle(s, c, (r, r), max(1, int(r * (1 - k * 0.97))))
        _glow_cache[key] = s
    return s


class Lighting:
    def __init__(self):
        self.layer = pygame.Surface((S.SCREEN_W // SCALE + 2, S.SCREEN_H // SCALE + 2))
        self.scaled_layer = pygame.Surface((S.SCREEN_W + SCALE * 2, S.SCREEN_H + SCALE * 2))

    def render(self, screen, cx, cy, amb, darkness, lights):
        """amb: color multiplicador ambiente. lights: [(x, y, radio, intensidad 0..255, (r,g,b))]"""
        if min(amb) >= 252:
            return                                           # pleno día: nada que hacer
        lay = self.layer
        lay.fill(amb)
        w, h = lay.get_size()
        for (x, y, r, inten, col) in lights:
            sx, sy = (x - cx) / SCALE, (y - cy) / SCALE
            rr = r / SCALE
            if sx < -rr or sy < -rr or sx > w + rr or sy > h + rr:
                continue
            g = _glow(rr, col, inten)
            lay.blit(g, (int(sx - rr), int(sy - rr)), special_flags=pygame.BLEND_RGB_ADD)
        try:
            big = pygame.transform.smoothscale(lay, (S.SCREEN_W + SCALE * 2, S.SCREEN_H + SCALE * 2), self.scaled_layer)
        except TypeError:
            big = pygame.transform.smoothscale(lay, (S.SCREEN_W + SCALE * 2, S.SCREEN_H + SCALE * 2))
        screen.blit(big, (0, 0), special_flags=pygame.BLEND_RGB_MULT)


class Weather:
    """Lluvia ocasional (sólo en superficie). Sin nieve = lluvia; en bioma nevado = nieve."""

    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.intensity = 0.0
        self.target = 0.0
        self.timer = self.rng.uniform(60, 150)
        self.drops = []
        self.snow = False

    @property
    def raining(self):
        return self.intensity > 0.15

    def update(self, dt, outdoors=True, snow=False):
        self.snow = snow
        self.timer -= dt
        if self.timer <= 0:
            if self.target > 0:
                self.target = 0.0
                self.timer = self.rng.uniform(100, 260)
            else:
                self.target = self.rng.choice([0.5, 0.8, 1.0])
                self.timer = self.rng.uniform(40, 110)
        goal = self.target if outdoors else 0.0
        self.intensity += (goal - self.intensity) * min(1.0, dt * 0.4)
        want = int(self.intensity * (90 if not snow else 70))
        W, H = S.SCREEN_W, S.SCREEN_H
        while len(self.drops) < want:
            self.drops.append([self.rng.uniform(0, W), self.rng.uniform(-H, 0), self.rng.uniform(0.7, 1.2)])
        if len(self.drops) > want:
            del self.drops[want:]
        sp = 900 if not snow else 90
        for d in self.drops:
            d[1] += sp * d[2] * dt
            d[0] += (-80 if not snow else math.sin(d[1] * 0.02) * 30) * dt
            if d[1] > H:
                d[1] = self.rng.uniform(-60, -4)
                d[0] = self.rng.uniform(0, W + 80)

    def draw(self, screen):
        if self.intensity < 0.08:
            return
        if not self.snow:
            col = (176, 196, 232)
            for x, y, k in self.drops:
                pygame.draw.line(screen, col, (int(x), int(y)), (int(x - 4), int(y + 12 * k)), 1)
        else:
            for x, y, k in self.drops:
                pygame.draw.rect(screen, (245, 248, 255), (int(x), int(y), 3, 3))
