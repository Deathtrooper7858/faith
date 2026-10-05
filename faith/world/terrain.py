"""Generación procedural del terreno del mundo (determinista por semilla).
Puro Python: se puede ejecutar y visualizar sin pygame."""
import math
from ..util import Noise, hash01

# Tipos de tile
GRASS, SAND, SHALLOW, DEEP, SNOW, ROCK, LAVA, CAVE_DOOR, CAVE_FLOOR, CAVE_WALL = range(10)

SOLID = frozenset((DEEP, ROCK, CAVE_DOOR, CAVE_WALL))
WATER = frozenset((SHALLOW, DEEP))
GROUND = frozenset((GRASS, SAND, SNOW))        # donde pueden crecer objetos
WALKABLE_GROUND = frozenset((GRASS, SAND, SNOW, CAVE_FLOOR))

MINIMAP_COLORS = {
    GRASS: (70, 140, 74), SAND: (222, 198, 140), SHALLOW: (74, 156, 224), DEEP: (36, 100, 190),
    SNOW: (232, 240, 248), ROCK: (96, 96, 108), LAVA: (240, 110, 30), CAVE_DOOR: (40, 36, 44),
    CAVE_FLOOR: (118, 108, 126), CAVE_WALL: (26, 24, 32),
}


class _CachedNoise(Noise):
    """Ruido con caché de la rejilla de enteros (los octavos bajos se reutilizan mucho)."""

    def __init__(self, seed):
        super().__init__(seed)
        self._lat = {}

    def _h(self, x, y):
        k = (x, y)
        v = self._lat.get(k)
        if v is None:
            v = hash01(self.seed, x, y)
            if len(self._lat) > 400000:
                self._lat.clear()
            self._lat[k] = v
        return v

    def value(self, x, y):
        x0 = math.floor(x)
        y0 = math.floor(y)
        fx = x - x0
        fy = y - y0
        fx = fx * fx * (3.0 - 2.0 * fx)
        fy = fy * fy * (3.0 - 2.0 * fy)
        h = self._h
        a = h(x0, y0)
        b = h(x0 + 1, y0)
        c = h(x0, y0 + 1)
        d = h(x0 + 1, y0 + 1)
        top = a + (b - a) * fx
        bot = c + (d - c) * fx
        return top + (bot - top) * fy


class Terrain:
    def __init__(self, seed):
        self.seed = seed
        self.n_mount = _CachedNoise(seed + 11)
        self.n_lake = _CachedNoise(seed + 23)
        self.n_river = _CachedNoise(seed + 37)
        self.n_temp = _CachedNoise(seed + 41)
        self.n_lava = _CachedNoise(seed + 53)
        self.n_forest = _CachedNoise(seed + 67)
        self._cache = {}

    # ── campos continuos ──────────────────────────────────────────────────
    def forest(self, tx, ty):
        return self.n_forest.fbm(tx * 0.045, ty * 0.045, 3)

    def _base(self, tx, ty):
        d2 = tx * tx + ty * ty
        if d2 < 49:                       # claro de inicio
            return GRASS
        dist = math.sqrt(d2)

        m = self.n_mount.fbm(tx * 0.03, ty * 0.03, 3)
        mount_thr = 0.685 + max(0.0, (22 - dist) * 0.012)   # sin montañas pegadas al inicio
        if m > mount_thr:
            return ROCK

        lk = self.n_lake.fbm(tx * 0.04, ty * 0.04, 3)
        lake_thr = 0.635 + max(0.0, (16 - dist) * 0.02)
        if lk > lake_thr + 0.06:
            return DEEP
        if lk > lake_thr:
            return SHALLOW

        rv = abs(self.n_river.fbm(tx * 0.022, ty * 0.022, 2) - 0.5)
        if dist > 10:
            if rv < 0.010:
                return SHALLOW
            if rv < 0.028:
                return SAND

        if lk > lake_thr - 0.035:
            return SAND

        if m > 0.625:
            lv = self.n_lava.fbm(tx * 0.09, ty * 0.09, 2)
            if lv > 0.67:
                return LAVA

        temp = self.n_temp.fbm(tx * 0.017 + 50, ty * 0.017 - 30, 3)
        temp += max(0.0, 1.0 - dist / 34.0) * 0.30
        if temp < 0.40:
            return SNOW
        return GRASS

    def tile(self, tx, ty):
        key = (tx, ty)
        t = self._cache.get(key)
        if t is not None:
            return t
        t = self._base(tx, ty)
        if t == ROCK:
            if self._is_door_site(tx, ty):
                t = CAVE_DOOR
        if len(self._cache) > 120000:
            self._cache.clear()
        self._cache[key] = t
        return t

    def _door_candidate(self, tx, ty):
        return (hash01(self.seed + 91, tx, ty) < 0.16 and self._base(tx, ty) == ROCK
                and self._base(tx, ty + 1) in GROUND)

    def _is_door_site(self, tx, ty):
        """Entradas a cuevas: raras y nunca pegadas entre sí (gana el candidato de la izquierda)."""
        if not self._door_candidate(tx, ty):
            return False
        return not (self._door_candidate(tx - 1, ty) or self._door_candidate(tx - 2, ty))

    def near_water(self, tx, ty, r=1):
        for oy in range(-r, r + 1):
            for ox in range(-r, r + 1):
                if self.tile(tx + ox, ty + oy) in WATER:
                    return True
        return False


def preview(seed=1234, half=140, step=2, path="/tmp/world.png"):
    """Genera una imagen de depuración del mapa (requiere Pillow)."""
    from PIL import Image
    t = Terrain(seed)
    n = (half * 2) // step
    im = Image.new("RGB", (n, n))
    px = im.load()
    for j in range(n):
        for i in range(n):
            px[i, j] = MINIMAP_COLORS[t.tile(-half + i * step, -half + j * step)]
    im.save(path)
    return im
