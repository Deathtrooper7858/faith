"""Niveles de juego: el mundo abierto infinito (Overworld) y las cuevas (Cave).
Un Level contiene terreno, objetos, estructuras, mobs, proyectiles y partículas."""
import math
import random
import pygame
from .. import settings as S
from ..fx.particles import ParticleSystem
from ..util import dist, hash01
from . import terrain as T
from . import tiles as tilegfx
from . import cavegen
from .objects import WorldObject, make_ore_kind, SPECS as OBJ_SPECS
from .structures import Structure, SPECS as STRUCT_SPECS

TS = S.TILE
CN = S.CHUNK_TILES
CPX = S.CHUNK_PX
PLACEABLE_GROUND = (T.GRASS, T.SAND, T.SNOW, T.CAVE_FLOOR)
MAX_BAKED = 14


class Chunk:
    __slots__ = ("cx", "cy", "objects", "surf", "animated", "last_draw")

    def __init__(self, cx, cy, objects):
        self.cx, self.cy = cx, cy
        self.objects = objects
        self.surf = None
        self.animated = None
        self.last_draw = 0


class Level:
    is_cave = False
    outdoors = True

    def __init__(self, seed):
        self.seed = seed
        self.chunks = {}
        self.structs = {}
        self.removed = set()
        self.mobs = []
        self.projectiles = []
        self.fx = ParticleSystem()
        self.rng = random.Random(seed ^ 0x5F3759DF)
        self.t = 0.0
        self._frame = 0
        self._active_objs = []
        self.spawn_timer = 2.0
        self.animal_timer = 3.0
        self.player_ref = None
        self.darkness = 0.0
        self.drops = []

    # ── a implementar ─────────────────────────────────────────────────────
    def tile(self, tx, ty):
        raise NotImplementedError

    def make_objects(self, cx, cy):
        raise NotImplementedError

    # ── chunks ────────────────────────────────────────────────────────────
    def get_chunk(self, cx, cy):
        ch = self.chunks.get((cx, cy))
        if ch is None:
            objs = [o for o in self.make_objects(cx, cy) if o.uid not in self.removed]
            ch = Chunk(cx, cy, objs)
            self.chunks[(cx, cy)] = ch
        return ch

    def ensure(self, px, py, radius=2, budget=3):
        """Genera chunks alrededor de (px, py), con un tope por fotograma."""
        ccx, ccy = int(px // CPX), int(py // CPX)
        made = 0
        order = sorted(((dx, dy) for dx in range(-radius, radius + 1) for dy in range(-radius, radius + 1)),
                       key=lambda d: d[0] * d[0] + d[1] * d[1])
        for dx, dy in order:
            if (ccx + dx, ccy + dy) not in self.chunks:
                self.get_chunk(ccx + dx, ccy + dy)
                made += 1
                if made >= budget:
                    break

    def chunk_range(self, x0, y0, x1, y1):
        return range(int(x0 // CPX), int(x1 // CPX) + 1), range(int(y0 // CPX), int(y1 // CPX) + 1)

    # ── objetos ───────────────────────────────────────────────────────────
    def objects_in_rect(self, x0, y0, x1, y1):
        out = []
        xs, ys = self.chunk_range(x0 - 160, y0 - 160, x1 + 160, y1 + 160)
        for cx in xs:
            for cy in ys:
                ch = self.chunks.get((cx, cy))
                if ch:
                    out.extend(ch.objects)
        return out

    def objects_near(self, x, y, r):
        r2 = r * r
        return [o for o in self.objects_in_rect(x - r, y - r, x + r, y + r)
                if (o.x - x) ** 2 + (o.y - y) ** 2 <= r2]

    def remove_object(self, obj):
        ch = self.chunks.get((int(obj.x // CPX), int(obj.y // CPX)))
        if ch is None:
            for c in self.chunks.values():
                if obj in c.objects:
                    ch = c
                    break
        if ch and obj in ch.objects:
            ch.objects.remove(obj)
        if obj.uid:
            self.removed.add(obj.uid)

    def add_object(self, obj):
        self.get_chunk(int(obj.x // CPX), int(obj.y // CPX)).objects.append(obj)

    def activate(self, obj):
        if obj not in self._active_objs:
            self._active_objs.append(obj)

    # ── colisiones ────────────────────────────────────────────────────────
    def collides(self, rect, flying=False, ignore_mobs=True):
        if flying:
            return False
        x0, y0 = rect.left // TS, rect.top // TS
        x1, y1 = (rect.right - 1) // TS, (rect.bottom - 1) // TS
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                if self.tile(tx, ty) in T.SOLID:
                    return True
                st = self.structs.get((tx, ty))
                if st and st.solid:
                    return True
        for o in self.objects_in_rect(rect.left, rect.top, rect.right, rect.bottom):
            c = o.collider()
            if c and c.colliderect(rect):
                return True
        return False

    def in_lava(self, x, y):
        return self.tile(int(x // TS), int(y // TS)) == T.LAVA

    def in_shallow(self, x, y):
        return self.tile(int(x // TS), int(y // TS)) == T.SHALLOW

    def walkable_spot(self, tx, ty):
        return self.tile(tx, ty) in (T.GRASS, T.SAND, T.SNOW, T.CAVE_FLOOR) and (tx, ty) not in self.structs

    # ── estructuras ───────────────────────────────────────────────────────
    def can_place(self, kind, tx, ty, blockers=()):
        if self.tile(tx, ty) not in PLACEABLE_GROUND or (tx, ty) in self.structs:
            return False
        r = pygame.Rect(tx * TS, ty * TS, TS, TS)
        for o in self.objects_in_rect(r.left, r.top, r.right, r.bottom):
            c = o.collider()
            if c and c.colliderect(r):
                return False
            if o.kind in ("stone", "rose") and r.collidepoint(o.x, o.y - 6):
                return False
        if STRUCT_SPECS[kind]["solid"]:
            for b in blockers:
                if r.colliderect(b):
                    return False
        return True

    def add_structure(self, kind, tx, ty, blockers=()):
        if not self.can_place(kind, tx, ty, blockers):
            return None
        st = Structure(kind, tx, ty)
        self.structs[(tx, ty)] = st
        return st

    def remove_structure(self, st):
        self.structs.pop((st.tx, st.ty), None)

    def structs_near(self, x, y, r):
        out = []
        for ty in range(int((y - r) // TS), int((y + r) // TS) + 1):
            for tx in range(int((x - r) // TS), int((x + r) // TS) + 1):
                st = self.structs.get((tx, ty))
                if st and (st.center()[0] - x) ** 2 + (st.center()[1] - y) ** 2 <= r * r:
                    out.append(st)
        return out

    def station_near(self, x, y, kind, r=TS * 3.2):
        return any(s.kind == kind for s in self.structs_near(x, y, r))

    # ── actualización ─────────────────────────────────────────────────────
    def update(self, dt, player, darkness, day):
        self.t += dt
        self.darkness = darkness
        self.player_ref = player
        self.ensure(player.x, player.y, S.KEEP_RADIUS - 1)
        for o in list(self._active_objs):
            o.update(dt)
            if o.shake <= 0 and o.flash <= 0 and o.hit_t <= 0:
                self._active_objs.remove(o)
        for st in self.structs.values():
            if st.lit_ms > 0:
                st.update(dt)
                if self.rng.random() < dt * 6:
                    self.fx.smoke(st.tx * TS + TS / 2, st.ty * TS + 6, 1)
        for m in self.mobs:
            m.update(dt, self, player)
        self.mobs = [m for m in self.mobs if not m.remove]
        for d in self.drops:
            d.update(dt, self, player)
        self.drops = [d for d in self.drops if d.alive]
        for p in self.projectiles:
            p.update(dt, self, player)
        self.projectiles = [p for p in self.projectiles if p.alive]
        self.fx.update(dt)
        self._spawn(dt, player, darkness, day)

    def _spawn(self, dt, player, darkness, day):
        pass

    # ── luces ─────────────────────────────────────────────────────────────
    def collect_lights(self, cx, cy):
        lights = []
        x0, y0 = int(cx // TS) - 6, int(cy // TS) - 6
        x1, y1 = int((cx + S.SCREEN_W) // TS) + 6, int((cy + S.SCREEN_H) // TS) + 6
        for ty in range(y0, y1):
            for tx in range(x0, x1):
                st = self.structs.get((tx, ty))
                if st:
                    l = st.light(self.t)
                    if l:
                        lights.append(l)
        xs, ys = self.chunk_range(cx - 200, cy - 200, cx + S.SCREEN_W + 200, cy + S.SCREEN_H + 200)
        for ccx in xs:
            for ccy in ys:
                ch = self.chunks.get((ccx, ccy))
                if ch and ch.animated:
                    for (t, px, py, _m) in ch.animated:
                        if t == T.LAVA:
                            lights.append((ccx * CPX + px + TS / 2, ccy * CPX + py + TS / 2, 120, 150, (255, 120, 50)))
        return lights

    # ── dibujo ────────────────────────────────────────────────────────────
    def draw(self, surf, cx, cy, extra_drawables=()):
        self._frame += 1
        cx, cy = int(cx), int(cy)
        xs, ys = self.chunk_range(cx, cy, cx + S.SCREEN_W, cy + S.SCREEN_H)
        wf = int(self.t * 3.0) % 4
        for ccx in xs:
            for ccy in ys:
                ch = self.get_chunk(ccx, ccy)
                if ch.surf is None:
                    ch.surf, ch.animated = tilegfx.bake_chunk(self, ccx, ccy)
                ch.last_draw = self._frame
                ox, oy = ccx * CPX - cx, ccy * CPX - cy
                surf.blit(ch.surf, (ox, oy))
                for (t, px, py, mask) in ch.animated:
                    sx, sy = ox + px, oy + py
                    if sx < -TS or sy < -TS or sx > S.SCREEN_W or sy > S.SCREEN_H:
                        continue
                    if t == T.LAVA:
                        surf.blit(tilegfx.lava_frame(wf), (sx, sy))
                    else:
                        surf.blit(tilegfx.water_frame((wf + (px // TS + py // TS)) % 4, mask, t == T.DEEP), (sx, sy))
        self._trim_baked()
        # elementos ordenados por profundidad
        draw = []
        m = 140
        for ccx in range(int((cx - m) // CPX), int((cx + S.SCREEN_W + m) // CPX) + 1):
            for ccy in range(int((cy - m) // CPX), int((cy + S.SCREEN_H + m) // CPX) + 1):
                ch = self.chunks.get((ccx, ccy))
                if not ch:
                    continue
                for o in ch.objects:
                    if cx - m < o.x < cx + S.SCREEN_W + m and cy - m < o.y < cy + S.SCREEN_H + m + 120:
                        draw.append((o.sort_y, 0, o))
        for ty in range(cy // TS - 1, (cy + S.SCREEN_H) // TS + 2):
            for tx in range(cx // TS - 1, (cx + S.SCREEN_W) // TS + 2):
                st = self.structs.get((tx, ty))
                if st:
                    draw.append((st.sort_y, 1, st))
        for mob in self.mobs:
            if cx - 120 < mob.x < cx + S.SCREEN_W + 120 and cy - 120 < mob.y < cy + S.SCREEN_H + 160:
                draw.append((mob.sort_y, 2, mob))
        for p in self.projectiles:
            draw.append((p.y + 14, 3, p))
        for d in self.drops:
            draw.append((d.y, 3, d))
        for e in extra_drawables:
            draw.append((e.sort_y, 2, e))
        draw.sort(key=lambda d: (d[0], d[1]))
        for _y, _k, d in draw:
            if isinstance(d, Structure):
                d.draw(surf, cx, cy, self.t)
            else:
                d.draw(surf, cx, cy)
        self.fx.draw(surf, cx, cy)

    def _trim_baked(self):
        baked = [c for c in self.chunks.values() if c.surf is not None]
        if len(baked) > MAX_BAKED:
            baked.sort(key=lambda c: c.last_draw)
            for c in baked[:len(baked) - MAX_BAKED]:
                if c.last_draw < self._frame - 2:
                    c.surf = None
                    c.animated = None


# ═════════════════════════════════════════════════════════════════════════════
class Overworld(Level):
    def __init__(self, seed):
        super().__init__(seed)
        self.terrain = T.Terrain(seed)

    def tile(self, tx, ty):
        return self.terrain.tile(tx, ty)

    def biome(self, x, y):
        t = self.tile(int(x // TS), int(y // TS))
        return "snow" if t == T.SNOW else "grass"

    def make_objects(self, cx, cy):
        seed = (self.seed * 1000003) ^ (cx * 73856093) ^ (cy * 19349663)
        rng = random.Random(seed)
        tx0, ty0 = cx * CN, cy * CN
        tile = self.terrain.tile
        f = self.terrain.forest(tx0 + CN // 2, ty0 + CN // 2)
        tree_p = max(0.06, min(0.62, 0.08 + (f - 0.40) * 1.7))
        objs = []

        # entradas de cueva
        for j in range(CN):
            for i in range(CN):
                tx, ty = tx0 + i, ty0 + j
                if tile(tx, ty) == T.CAVE_DOOR:
                    objs.append(WorldObject("cavedoor", (tx + 0.5) * TS, (ty + 1) * TS, f"door:{tx}:{ty}"))

        def ok_ground(px, py, cw, ch_, allowed):
            for yy in (py - ch_, py):
                for xx in (px - cw / 2, px + cw / 2):
                    if tile(int(xx // TS), int(yy // TS)) not in allowed:
                        return False
            return True

        for _ in range(26):
            tx, ty = tx0 + rng.randrange(CN), ty0 + rng.randrange(CN)
            t = tile(tx, ty)
            if t not in T.GROUND or tx * tx + ty * ty < 36:
                continue
            px = (tx + rng.random()) * TS
            py = (ty + 0.25 + rng.random() * 0.7) * TS
            roll = rng.random()
            near_rock = any(tile(tx + a, ty + b) == T.ROCK for a in (-3, 0, 3) for b in (-3, 0, 3))
            if roll < tree_p:
                kind = "bigtree" if rng.random() < 0.13 else "tree"
            elif roll < tree_p + 0.07:
                kind = "rock" if (near_rock or rng.random() < 0.25) else "stone"
            elif roll < tree_p + 0.13 and t == T.GRASS:
                kind = "rose"
            elif roll < tree_p + 0.145:
                kind = "stump"
            else:
                continue
            col = OBJ_SPECS[kind]["col"] or (20, 10)
            allowed = (T.GRASS, T.SNOW) if kind in ("tree", "bigtree", "stump", "rose") else T.GROUND
            if not ok_ground(px, py, col[0] + 6, col[1] + 6, allowed):
                continue
            gap = {"bigtree": 92, "tree": 58, "rock": 66, "stump": 40}.get(kind, 34)
            if any((o.x - px) ** 2 + (o.y - py) ** 2 < gap * gap for o in objs):
                continue
            uid = f"{kind}:{int(px)}:{int(py)}"
            variant = (1 if rng.random() < 0.5 else 0) | (2 if t == T.SNOW else 0)
            objs.append(WorldObject(kind, px, py, uid, variant))
        return objs

    # ── apariciones ───────────────────────────────────────────────────────
    def _spawn(self, dt, player, darkness, day):
        from ..entities import mobs as M
        self.spawn_timer -= dt
        self.animal_timer -= dt
        night = darkness > 110
        undead = [m for m in self.mobs if m.hostile]
        animals = [m for m in self.mobs if not m.hostile]
        cap = min(S.MAX_ENEMIES_SURFACE, 4 + day)
        if night and self.spawn_timer <= 0 and len(undead) < cap:
            self.spawn_timer = max(2.5, 6.0 - day * 0.4) + self.rng.random() * 2
            p = self._random_spot(player, 520, 880)
            if p:
                kinds, weights = M.surface_table(day)
                M.spawn(self, self.rng.choices(kinds, weights)[0], p[0], p[1])
        if self.animal_timer <= 0 and len(animals) < S.MAX_ANIMALS:
            self.animal_timer = 3.5 + self.rng.random() * 3
            p = self._random_spot(player, 380, 900)
            if p:
                biome = self.biome(*p)
                kinds, weights = M.animal_table(biome)
                M.spawn(self, self.rng.choices(kinds, weights)[0], p[0], p[1])

    def _random_spot(self, player, rmin, rmax):
        for _ in range(8):
            a = self.rng.random() * math.tau
            d = self.rng.uniform(rmin, rmax)
            x, y = player.x + math.cos(a) * d, player.y + math.sin(a) * d
            tx, ty = int(x // TS), int(y // TS)
            if self.tile(tx, ty) in T.GROUND and (tx, ty) not in self.structs and (int(x // CPX), int(y // CPX)) in self.chunks:
                r = pygame.Rect(int(x) - 14, int(y) - 14, 28, 28)
                if not self.collides(r):
                    return x, y
        return None


# ═════════════════════════════════════════════════════════════════════════════
class Cave(Level):
    is_cave = True
    outdoors = False

    def __init__(self, seed, door_tile):
        super().__init__(seed)
        self.door_tile = door_tile          # puerta de la superficie a la que está vinculada
        g = cavegen.generate(seed)
        self.tiles = g["tiles"]
        self.spawn_tile = g["spawn"]
        self.exit_door = g["door"]
        self._pre = {}
        rng = random.Random(seed + 5)
        self._add_pre(WorldObject("cavedoor", (g["door"][0] + 0.5) * TS, (g["door"][1] + 1) * TS, "cave-exit"))
        for (tx, ty), kind in g["ores"]:
            self._add_pre(WorldObject(kind, (tx + 0.5) * TS, (ty + 0.9) * TS, f"{kind}:{tx}:{ty}"))
        for (tx, ty) in g["chests"]:
            self._add_pre(WorldObject("lootchest", (tx + 0.5) * TS, (ty + 0.9) * TS, f"lootchest:{tx}:{ty}"))
        self.floor = g["floor"]
        self.populated = False

    def _add_pre(self, o):
        self._pre.setdefault((int(o.x // CPX), int(o.y // CPX)), []).append(o)

    def tile(self, tx, ty):
        return self.tiles.get((tx, ty), T.CAVE_WALL)

    def make_objects(self, cx, cy):
        return list(self._pre.get((cx, cy), []))

    @property
    def spawn_pos(self):
        return (self.spawn_tile[0] + 0.5) * TS, (self.spawn_tile[1] + 0.5) * TS

    def populate(self, day):
        """Población inicial de monstruos lejos de la entrada."""
        from ..entities import mobs as M
        if self.populated:
            return
        self.populated = True
        kinds, weights = M.cave_table(day)
        far = [p for p in self.floor if abs(p[0] - self.spawn_tile[0]) + abs(p[1] - self.spawn_tile[1]) > 16
               and self.tiles[p] == T.CAVE_FLOOR]
        self.rng.shuffle(far)
        for (tx, ty) in far[:11]:
            M.spawn(self, self.rng.choices(kinds, weights)[0], (tx + 0.5) * TS, (ty + 0.5) * TS)

    def _spawn(self, dt, player, darkness, day):
        from ..entities import mobs as M
        self.spawn_timer -= dt
        if self.spawn_timer <= 0 and len([m for m in self.mobs if m.hostile]) < S.MAX_ENEMIES_CAVE:
            self.spawn_timer = 9.0 + self.rng.random() * 6
            kinds, weights = M.cave_table(day)
            for _ in range(10):
                tx, ty = self.rng.choice(self.floor)
                x, y = (tx + 0.5) * TS, (ty + 0.5) * TS
                d = dist(x, y, player.x, player.y)
                if 520 < d < 1100 and self.tiles[(tx, ty)] == T.CAVE_FLOOR:
                    M.spawn(self, self.rng.choices(kinds, weights)[0], x, y)
                    break
