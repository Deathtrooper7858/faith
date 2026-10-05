"""Estructuras construidas por el jugador (se colocan sobre la rejilla de tiles)."""
import math
import pygame
from .. import assets, settings as S
from ..inventory import ItemStack

TS = S.TILE

# asset, ancho dibujado, sólido, luz (radio, intensidad, color), altura de sombra
SPECS = {
    "crafting_table": dict(img="objects/crafting-table.png", w=60, solid=True, name="Mesa de crafteo", drop="crafting-table", interact=True),
    "oven": dict(img="objects/oven.png", w=62, solid=True, name="Horno", drop="oven", interact=True),
    "chest": dict(img="objects/chest.png", w=56, solid=True, name="Cofre", drop="chest", interact=True, storage=True),
    "bed": dict(img="objects/bed.png", w=58, solid=False, name="Cama", drop="bed", interact=True),
    "torch": dict(img="objects/torch.png", w=34, solid=False, name="Antorcha", drop="torch", light=(260, 200, (255, 190, 110))),
    "wood_wall": dict(img="objects/wood-wall.png", w=TS, solid=True, name="Muro de madera", drop="wood-wall", wall=True),
    "stone_wall": dict(img="objects/brick-wall.png", w=TS, solid=True, name="Muro de piedra", drop="stone-wall", wall=True),
    "door": dict(img="objects/door.png", w=56, solid=True, name="Puerta", drop="door", interact=True),
    "fence": dict(img="objects/fence.png", w=TS, solid=True, name="Valla", drop="fence", wall=True),
}
PLACE_FROM_ITEM = {"crafting_table": "crafting-table", "oven": "oven", "chest": "chest", "bed": "bed", "torch": "torch",
                   "wood_wall": "wood-wall", "stone_wall": "stone-wall", "door": "door", "fence": "fence"}

_cache = {}


def _img(kind, variant=""):
    key = (kind, variant)
    s = _cache.get(key)
    if s is None:
        sp = SPECS[kind]
        rel = sp["img"]
        if kind == "oven" and variant == "on":
            rel = "objects/on-oven.png"
        base, _ = assets.trim(assets.scaled(rel, w=sp["w"]))
        if kind == "door" and variant == "open":
            base = pygame.transform.scale(base, (max(8, base.get_width() // 4), base.get_height()))
        if sp.get("wall"):
            base = pygame.transform.scale(base, (TS, TS))
        s = base
        _cache[key] = s
    return s


class Structure:
    __slots__ = ("kind", "tx", "ty", "open", "lit_ms", "items", "spec", "anim")

    def __init__(self, kind, tx, ty):
        self.kind = kind
        self.tx, self.ty = tx, ty
        self.spec = SPECS[kind]
        self.open = False
        self.lit_ms = 0.0
        self.items = [None] * (S.GRID_COLS * S.GRID_ROWS) if self.spec.get("storage") else None
        self.anim = (tx * 7 + ty * 13) % 100

    @property
    def name(self):
        return self.spec["name"]

    @property
    def solid(self):
        if self.kind == "door":
            return not self.open
        return self.spec["solid"]

    @property
    def interactive(self):
        return bool(self.spec.get("interact"))

    @property
    def sort_y(self):
        return (self.ty + 1) * TS - 2

    def rect(self):
        return pygame.Rect(self.tx * TS, self.ty * TS, TS, TS)

    def center(self):
        return self.tx * TS + TS / 2, self.ty * TS + TS / 2

    def light(self, t):
        if self.kind == "torch":
            r, inten, col = self.spec["light"]
            f = 1.0 + 0.06 * math.sin(t * 9 + self.anim) + 0.04 * math.sin(t * 23 + self.anim * 2)
            return (self.tx * TS + TS / 2, self.ty * TS + TS * 0.35, r * f, inten, col)
        if self.kind == "oven" and self.lit_ms > 0:
            f = 1.0 + 0.08 * math.sin(t * 12 + self.anim)
            return (self.tx * TS + TS / 2, self.ty * TS + TS * 0.5, 170 * f, 190, (255, 150, 70))
        return None

    def update(self, dt):
        """dt en segundos."""
        if self.lit_ms > 0:
            self.lit_ms = max(0.0, self.lit_ms - dt * 1000.0)

    def draw(self, surf, cx, cy, t=0.0):
        k = self.kind
        variant = "on" if (k == "oven" and self.lit_ms > 0) else ("open" if (k == "door" and self.open) else "")
        spr = _img(k, variant)
        w, h = spr.get_size()
        bx = self.tx * TS + TS / 2 - cx
        by = (self.ty + 1) * TS - cy
        if k not in ("torch",) and not self.spec.get("wall"):
            sh = assets.shadow(int(w * 1.05), 16, 90)
            surf.blit(sh, (int(bx - w * 0.52), int(by - 14)))
        if self.spec.get("wall"):
            surf.blit(spr, (int(bx - TS / 2), int(by - TS)))      # los muros ocupan el tile completo
            return
        oy = 0
        if k == "torch":
            oy = int(math.sin(t * 8 + self.anim) * 1)
        surf.blit(spr, (int(bx - w / 2), int(by - h - 2 + oy)))
        if k == "torch":                      # llama animada
            fr = (int(t * 12) + self.anim) % 3
            fx = int(bx)
            fy = int(by - h + 2)
            col = ((255, 220, 120), (255, 170, 60), (255, 120, 40))[fr]
            pygame.draw.circle(surf, col, (fx, fy), 4 - (fr == 2))
            pygame.draw.circle(surf, (255, 250, 200), (fx, fy + 1), 2)

    def to_json(self):
        d = {"k": self.kind, "x": self.tx, "y": self.ty}
        if self.kind == "door":
            d["open"] = self.open
        if self.items is not None:
            d["items"] = [s.to_json() if s else None for s in self.items]
        return d

    @staticmethod
    def from_json(d):
        if d.get("k") not in SPECS:
            return None
        st = Structure(d["k"], d["x"], d["y"])
        st.open = bool(d.get("open", False))
        if st.items is not None:
            for i, v in enumerate(d.get("items", [])[:len(st.items)]):
                st.items[i] = ItemStack.from_json(v)
        return st
