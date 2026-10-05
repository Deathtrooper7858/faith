"""Objetos naturales del mundo: árboles, rocas, minerales, flores...
Cada objeto tiene vida, requisitos de herramienta y tabla de botín."""
import math
import pygame
from .. import assets, settings as S

# kind → especificación.
#   sprite: (archivo, ancho_px)   foot: píxeles entre la base del sprite y el "suelo"
#   col: (w, h) del colisionador centrado en los pies (None = atravesable)
#   hp: puntos de resistencia   tool: herramienta necesaria (None = a mano)
#   tier: nivel mínimo de herramienta   hand: potencia si se golpea sin herramienta (0 = no se puede)
#   yield: objeto que suelta por cada punto de vida perdido
#   bonus: [(objeto, min, max, prob)] al destruirse
SPECS = {
    "tree": dict(sprite=("objects/tree.png", 100), foot=7, col=(22, 14), hp=6, tool="axe", tier=0, hand=0.5,
                 yield_="wood", bonus=[("stick", 0, 2, 0.5), ("apple", 1, 1, 0.16)], shadow=(64, 22),
                 name="Árbol", sfx="chop", leaves=True),
    "bigtree": dict(sprite=("objects/big-tree.png", 176), foot=12, col=(36, 18), hp=12, tool="axe", tier=0,
                    hand=0.35, yield_="wood", bonus=[("apple", 1, 2, 0.45), ("green-apple", 1, 1, 0.3),
                                                     ("stick", 1, 3, 0.9)], shadow=(120, 34),
                    name="Árbol grande", sfx="chop", leaves=True),
    "stump": dict(sprite=("objects/stump.png", 54), foot=6, col=(26, 12), hp=3, tool="axe", tier=0, hand=0.6,
                  yield_="wood", bonus=[], shadow=(50, 16), name="Tocón", sfx="chop"),
    "rock": dict(sprite=("objects/rock.png", 88), foot=7, col=(62, 24), hp=8, tool="pickaxe", tier=1, hand=0,
                 yield_="stone", bonus=[("coal", 1, 2, 0.25)], shadow=(80, 22), name="Roca", sfx="mine"),
    "stone": dict(sprite=("objects/small_stone.png", 38), foot=4, col=None, hp=1, tool=None, tier=0, hand=2,
                  yield_="stone", bonus=[], shadow=(30, 10), name="Piedra", sfx="pickup"),
    "rose": dict(sprite=("objects/rose.png", 40), foot=3, col=None, hp=1, tool=None, tier=0, hand=2,
                 yield_="rose", bonus=[("fiber", 1, 2, 1.0)], shadow=(26, 8), name="Rosa", sfx="pickup"),
    "ore_coal": dict(sprite=("objects/coal-ore.png", 56), foot=5, col=(44, 20), hp=5, tool="pickaxe", tier=1,
                     hand=0, yield_="coal", bonus=[], shadow=(52, 16), name="Carbón", sfx="mine"),
    "ore_iron": dict(sprite=("objects/iron-ore.png", 56), foot=5, col=(44, 20), hp=6, tool="pickaxe", tier=2,
                     hand=0, yield_="iron-ore", bonus=[], shadow=(52, 16), name="Hierro", sfx="mine"),
    "ore_gold": dict(sprite=("objects/gold-ore.png", 56), foot=5, col=(44, 20), hp=7, tool="pickaxe", tier=3,
                     hand=0, yield_="gold-ore", bonus=[], shadow=(52, 16), name="Oro", sfx="mine"),
    "lootchest": dict(sprite=("objects/chest.png", 54), foot=3, col=(46, 22), hp=1, tool=None, tier=0, hand=0,
                      yield_=None, bonus=[], shadow=(56, 18), name="Cofre antiguo", sfx="pickup", interact=True),
    "cavedoor": dict(sprite=("objects/cave-door.png", 110), foot=2, col=None, hp=1, tool=None, tier=0, hand=0,
                     yield_=None, bonus=[], shadow=None, name="Cueva", sfx="door", interact=True, tile_solid=True),
}

_spr_cache = {}


def _sprite(kind, variant):
    key = (kind, variant)
    s = _spr_cache.get(key)
    if s is None:
        rel, w = SPECS[kind]["sprite"]
        base = assets.scaled(rel, w=w)
        base, _ = assets.trim(base)
        if variant & 1:                       # espejo horizontal para variedad
            base = assets.flipx(base)
        if variant & 2:                       # versión nevada
            base = assets.tint(base, (214, 230, 255))
        s = base
        _spr_cache[key] = s
    return s


def _flash_sprite(spr):
    return assets.tint(spr, (110, 110, 110), mult=False)


class WorldObject:
    __slots__ = ("kind", "x", "y", "uid", "hp", "variant", "flash", "shake", "hit_t", "spec")

    def __init__(self, kind, x, y, uid=None, variant=0):
        self.kind = kind
        self.spec = SPECS[kind]
        self.x = float(x)
        self.y = float(y)
        self.uid = uid
        self.hp = float(self.spec["hp"])
        self.variant = variant
        self.flash = 0.0
        self.shake = 0.0
        self.hit_t = 0.0

    # ── propiedades ───────────────────────────────────────────────────────
    @property
    def sort_y(self):
        return self.y

    @property
    def interactive(self):
        return bool(self.spec.get("interact"))

    def collider(self):
        c = self.spec["col"]
        if self.spec.get("tile_solid"):
            tx, ty = int(self.x // S.TILE), int((self.y - 2) // S.TILE)
            return pygame.Rect(tx * S.TILE, ty * S.TILE, S.TILE, S.TILE)
        if not c:
            return None
        return pygame.Rect(int(self.x - c[0] / 2), int(self.y - c[1]), c[0], c[1])

    def center(self):
        r = _sprite(self.kind, self.variant).get_height()
        return self.x, self.y - min(r, 60) * 0.45

    def radius(self):
        c = self.spec["col"]
        return max(18, (c[0] / 2 + 8) if c else 16)

    # ── daño ──────────────────────────────────────────────────────────────
    def hit(self, tool, tier, power):
        """Golpea el objeto. Devuelve (estado, unidades, destruido):
        estado: 'ok' | 'tool' (herramienta incorrecta) | 'tier' (nivel insuficiente)."""
        sp = self.spec
        need = sp["tool"]
        if need is None:
            eff = power if power > 0 else sp["hand"]
            if eff <= 0:
                return "tool", 0, False
        elif tool == need:
            if tier < sp["tier"]:
                return "tier", 0, False
            eff = power
        else:
            if sp["hand"] <= 0 or tool not in (None, "shovel", "sword", "bow"):
                return "tool", 0, False
            eff = sp["hand"]
        before = math.ceil(self.hp - 1e-6)
        self.hp -= eff
        after = max(0, math.ceil(self.hp - 1e-6))
        units = before - after
        self.shake = 1.0
        self.flash = 0.12
        self.hit_t = 2.0
        return "ok", units, self.hp <= 1e-6

    def loot(self, rng):
        """Botín extra al destruirse: [(item, n)]."""
        out = []
        for item, lo, hi, p in self.spec["bonus"]:
            if rng.random() <= p:
                n = rng.randint(lo, hi)
                if n > 0:
                    out.append((item, n))
        return out

    # ── animación / dibujo ────────────────────────────────────────────────
    def update(self, dt):
        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt * 4.0)
        if self.flash > 0:
            self.flash = max(0.0, self.flash - dt)
        if self.hit_t > 0:
            self.hit_t -= dt

    def draw(self, surf, cx, cy):
        spr = _sprite(self.kind, self.variant)
        w, h = spr.get_size()
        sx = self.x - cx
        sy = self.y - cy
        sh = self.spec["shadow"]
        if sh:
            s = assets.shadow(sh[0], sh[1], 80)
            surf.blit(s, (int(sx - sh[0] / 2), int(sy - sh[1] / 2 - 1)))
        ox = math.sin(self.shake * 38.0) * 3.0 * self.shake if self.shake > 0 else 0
        px, py = int(sx - w / 2 + ox), int(sy - h + self.spec["foot"])
        surf.blit(spr, (px, py))
        if self.flash > 0:
            surf.blit(_flash_sprite(spr), (px, py))
        if self.hit_t > 0 and self.hp < self.spec["hp"] and self.spec["hp"] > 1:
            bw = 36
            frac = max(0.0, self.hp / self.spec["hp"])
            bx, by = int(sx - bw / 2), int(sy - h - 6 + self.spec["foot"])
            pygame.draw.rect(surf, (20, 20, 24), (bx - 1, by - 1, bw + 2, 6))
            pygame.draw.rect(surf, (220, 200, 90) if frac > 0.34 else (230, 90, 70), (bx, by, int(bw * frac), 4))


def make_ore_kind(depth_roll):
    """Elige el tipo de mineral según un valor 0..1 (más hondo = más raro)."""
    if depth_roll < 0.55:
        return "ore_coal"
    if depth_roll < 0.86:
        return "ore_iron"
    return "ore_gold"


CAVE_LOOT = [  # (objeto, mínimo, máximo, peso)
    ("coal", 2, 6, 10), ("iron-ingot", 1, 4, 8), ("gold-ingot", 1, 3, 5), ("arrow", 6, 16, 8),
    ("torch", 3, 8, 8), ("cooked-meat", 1, 3, 7), ("apple", 2, 4, 6), ("iron-ore", 2, 5, 6),
    ("stone-brick", 4, 10, 5), ("bone", 1, 3, 3),
]
RARE_LOOT = [("katana", 1, 1, 2), ("shield", 1, 1, 3), ("iron-chest", 1, 1, 3), ("iron-helmet", 1, 1, 3),
             ("bow", 1, 1, 3), ("iron-sword", 1, 1, 3), ("gold-pickaxe", 1, 1, 2)]


def roll_loot(rng, rare_chance=0.35):
    out = []
    for _ in range(rng.randint(2, 4)):
        item, lo, hi, _w = rng.choices(CAVE_LOOT, weights=[e[3] for e in CAVE_LOOT])[0]
        out.append((item, rng.randint(lo, hi)))
    if rng.random() < rare_chance:
        item, lo, hi, _w = rng.choices(RARE_LOOT, weights=[e[3] for e in RARE_LOOT])[0]
        out.append((item, rng.randint(lo, hi)))
    return out
