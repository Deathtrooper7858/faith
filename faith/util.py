"""Utilidades matemáticas: hashing determinista y ruido de valor (sin numpy)."""
import math


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t):
    return t * t * (3.0 - 2.0 * t)


def sign(v):
    return -1 if v < 0 else (1 if v > 0 else 0)


def dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def normalize(dx, dy):
    d = math.hypot(dx, dy)
    if d < 1e-9:
        return 0.0, 0.0
    return dx / d, dy / d


def hash_int(seed, x, y):
    """Hash entero de 32 bits determinista (válido para x,y negativos)."""
    h = (x * 374761393 + y * 668265263 + seed * 1442695041) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return h ^ (h >> 16)


def hash01(seed, x, y):
    return hash_int(seed, x, y) / 4294967295.0


class Noise:
    """Ruido de valor 2D suave con fBm. Totalmente determinista por semilla."""

    def __init__(self, seed):
        self.seed = int(seed) & 0x7FFFFFFF

    def value(self, x, y):
        x0 = math.floor(x)
        y0 = math.floor(y)
        fx = smoothstep(x - x0)
        fy = smoothstep(y - y0)
        s = self.seed
        a = hash01(s, x0, y0)
        b = hash01(s, x0 + 1, y0)
        c = hash01(s, x0, y0 + 1)
        d = hash01(s, x0 + 1, y0 + 1)
        top = a + (b - a) * fx
        bot = c + (d - c) * fx
        return top + (bot - top) * fy

    def fbm(self, x, y, octaves=3, lacunarity=2.0, gain=0.5):
        total = 0.0
        amp = 1.0
        norm = 0.0
        for i in range(octaves):
            total += self.value(x, y) * amp
            norm += amp
            x *= lacunarity
            y *= lacunarity
            amp *= gain
        return total / norm
