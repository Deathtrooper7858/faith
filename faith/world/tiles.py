"""Texturas de terreno procedurales + horneado de chunks.
Cada chunk se dibuja UNA vez en una superficie estática (suelo, arena, nieve, roca);
sólo agua y lava se animan, y se dibujan por separado."""
import math
import random
import pygame
from .. import assets, settings as S
from ..util import hash01
from . import terrain as T

TS = S.TILE
_variants = {}
_water_frames = {}
_lava_frames = {}


def _speckle(surf, rng, colors, n, size=(1, 3)):
    w, h = surf.get_size()
    for _ in range(n):
        c = rng.choice(colors)
        sw = rng.randint(*size)
        pygame.draw.rect(surf, c, (rng.randrange(w), rng.randrange(h), sw, rng.randint(1, max(1, sw - 1))))


def _grass_tile(rng, shade=0):
    s = pygame.Surface((TS, TS))
    base = (62 + shade, 137 + shade, 72 + shade)
    s.fill(base)
    _speckle(s, rng, [(54, 124, 64), (50, 116, 60), (58, 130, 68)], 34, (2, 4))
    _speckle(s, rng, [(78, 156, 84), (92, 170, 92), (70, 148, 78)], 22, (1, 3))
    for _ in range(rng.randint(2, 5)):            # briznas de hierba
        x, y = rng.randrange(4, TS - 4), rng.randrange(6, TS - 2)
        c = rng.choice([(44, 106, 56), (96, 176, 96)])
        pygame.draw.line(s, c, (x, y), (x + rng.choice((-1, 0, 1)), y - rng.randint(2, 4)))
    return s


def _flowers(s, rng):
    cols = [(240, 220, 90), (240, 240, 245), (230, 120, 170), (150, 150, 240)]
    x, y = rng.randrange(8, TS - 8), rng.randrange(8, TS - 8)
    c = rng.choice(cols)
    pygame.draw.rect(s, (40, 100, 52), (x, y + 1, 1, 3))
    pygame.draw.rect(s, c, (x - 1, y - 1, 3, 2))
    pygame.draw.rect(s, (255, 240, 160), (x, y - 1, 1, 1))


def _sand_tile(rng):
    s = pygame.Surface((TS, TS))
    s.fill((222, 198, 140))
    _speckle(s, rng, [(210, 184, 126), (200, 174, 118), (214, 190, 132)], 30, (2, 4))
    _speckle(s, rng, [(236, 216, 164), (240, 222, 172)], 22, (1, 3))
    return s


def _snow_tile(rng):
    s = pygame.Surface((TS, TS))
    s.fill((232, 240, 248))
    _speckle(s, rng, [(214, 226, 240), (206, 220, 238)], 26, (2, 5))
    _speckle(s, rng, [(250, 252, 255), (255, 255, 255)], 20, (1, 3))
    return s


def _rock_tile(rng):
    """Interior de montaña: textura de cueva oscura y rugosa."""
    src = assets.scaled("objects/cave.png", TS, TS)
    s = src.copy().convert()
    _speckle(s, rng, [(70, 70, 82), (52, 52, 62)], 14, (2, 5))
    return s


def _cave_floor(rng):
    s = pygame.Surface((TS, TS))
    s.fill((58, 52, 60))
    _speckle(s, rng, [(50, 45, 52), (64, 58, 68), (46, 41, 48)], 40, (2, 5))
    _speckle(s, rng, [(78, 70, 82)], 12, (1, 2))
    return s


def variants(kind):
    v = _variants.get(kind)
    if v is None:
        rng = random.Random(hash(kind) & 0xFFFF)
        make = {"grass": lambda: _grass_tile(rng, rng.randint(-1, 1)), "sand": lambda: _sand_tile(rng),
                "snow": lambda: _snow_tile(rng), "rock": lambda: _rock_tile(rng),
                "cavefloor": lambda: _cave_floor(rng)}[kind]
        v = [make() for _ in range(6)]
        if kind == "grass":
            for t in v[3:]:
                _flowers(t, rng)
        _variants[kind] = v
    return v


# ── Agua y lava animadas ─────────────────────────────────────────────────────
def water_frame(frame, mask, deep):
    """mask: bits 1=N tiene tierra, 2=E, 4=S, 8=O  (se dibuja orilla clara en ese lado)."""
    key = (frame, mask, deep)
    s = _water_frames.get(key)
    if s is None:
        s = pygame.Surface((TS, TS))
        base = (36, 100, 190) if deep else (62, 144, 218)
        s.fill(base)
        rng = random.Random(frame * 7 + (3 if deep else 0))
        light = (92, 170, 238) if not deep else (58, 122, 206)
        dark = (26, 82, 168) if deep else (48, 118, 200)
        for i in range(7):
            x = (i * 19 + frame * 9 + (i % 3) * 5) % TS
            y = (i * 29 + (i % 2) * 11) % TS
            pygame.draw.line(s, light, (x, y), (x + 10, y), 1)
            pygame.draw.line(s, dark, (x + 4, y + 4), (x + 12, y + 4), 1)
        w = 5
        shore = (214, 240, 252)
        if mask & 1: pygame.draw.rect(s, shore, (0, 0, TS, w)); pygame.draw.rect(s, (150, 206, 240), (0, w, TS, 2))
        if mask & 4: pygame.draw.rect(s, shore, (0, TS - w, TS, w)); pygame.draw.rect(s, (150, 206, 240), (0, TS - w - 2, TS, 2))
        if mask & 8: pygame.draw.rect(s, shore, (0, 0, w, TS)); pygame.draw.rect(s, (150, 206, 240), (w, 0, 2, TS))
        if mask & 2: pygame.draw.rect(s, shore, (TS - w, 0, w, TS)); pygame.draw.rect(s, (150, 206, 240), (TS - w - 2, 0, 2, TS))
        _water_frames[key] = s
    return s


def lava_frame(frame):
    s = _lava_frames.get(frame)
    if s is None:
        base = assets.scaled("objects/lava.png", TS, TS).copy().convert()
        # brillo pulsante barato
        k = 0.88 + 0.12 * math.sin(frame * math.pi / 2)
        v = int(255 * k)
        base.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
        rng = random.Random(frame)
        for _ in range(6):
            pygame.draw.rect(base, (255, 224, 120), (rng.randrange(TS - 4), rng.randrange(TS - 4), 3, 2))
        _lava_frames[frame] = base
        s = base
    return s


# ── Horneado de chunk ────────────────────────────────────────────────────────
_LAND = (T.GRASS, T.SAND, T.SNOW, T.CAVE_FLOOR)


def bake_chunk(level, cx, cy):
    """Devuelve la superficie de suelo estática del chunk y la lista de tiles animados."""
    n = S.CHUNK_TILES
    surf = pygame.Surface((S.CHUNK_PX, S.CHUNK_PX))
    animated = []   # (tipo, px, py, mask)
    t0x, t0y = cx * n, cy * n
    tile = level.tile
    for j in range(n):
        for i in range(n):
            tx, ty = t0x + i, t0y + j
            t = tile(tx, ty)
            px, py = i * TS, j * TS
            h = hash01(1, tx, ty)
            if t == T.GRASS:
                vs = variants("grass")
                # las flores sólo en ~12 % de los tiles
                surf.blit(vs[int(h * 3)] if h > 0.12 else vs[3 + int(h * 25) % 3], (px, py))
            elif t == T.SAND:
                surf.blit(variants("sand")[int(h * 6) % 6], (px, py))
            elif t == T.SNOW:
                surf.blit(variants("snow")[int(h * 6) % 6], (px, py))
            elif t == T.CAVE_FLOOR:
                surf.blit(variants("cavefloor")[int(h * 6) % 6], (px, py))
            elif t in (T.ROCK, T.CAVE_DOOR, T.CAVE_WALL):
                _bake_rock(surf, level, tx, ty, px, py, h)
            elif t in (T.SHALLOW, T.DEEP):
                # fondo de arena bajo el agua para los bordes
                surf.blit(variants("sand")[0], (px, py))
                mask = 0
                if tile(tx, ty - 1) not in T.WATER: mask |= 1
                if tile(tx + 1, ty) not in T.WATER: mask |= 2
                if tile(tx, ty + 1) not in T.WATER: mask |= 4
                if tile(tx - 1, ty) not in T.WATER: mask |= 8
                animated.append((t, px, py, mask))
            elif t == T.LAVA:
                surf.blit(variants("cavefloor")[0], (px, py))
                animated.append((t, px, py, 0))
    # transiciones suaves hierba/arena/nieve y sombras de acantilado
    for j in range(n):
        for i in range(n):
            tx, ty = t0x + i, t0y + j
            t = tile(tx, ty)
            px, py = i * TS, j * TS
            if t in (T.GRASS, T.SAND, T.SNOW, T.CAVE_FLOOR):
                _bake_edges(surf, level, t, tx, ty, px, py)
    return surf, animated


def _bake_rock(surf, level, tx, ty, px, py, h):
    surf.blit(variants("rock")[int(h * 6) % 6], (px, py))
    solid = (T.ROCK, T.CAVE_DOOR, T.CAVE_WALL)
    if level.tile(tx, ty - 1) not in solid:       # borde superior iluminado
        pygame.draw.rect(surf, (128, 128, 144), (px, py, TS, 5))
        pygame.draw.rect(surf, (96, 96, 110), (px, py + 5, TS, 3))
    if level.tile(tx, ty + 1) not in solid:       # cara del acantilado
        pygame.draw.rect(surf, (28, 26, 34), (px, py + TS - 14, TS, 14))
        pygame.draw.rect(surf, (44, 42, 52), (px, py + TS - 14, TS, 3))
    if level.tile(tx - 1, ty) not in solid:
        pygame.draw.rect(surf, (36, 34, 42), (px, py, 4, TS))
    if level.tile(tx + 1, ty) not in solid:
        pygame.draw.rect(surf, (36, 34, 42), (px + TS - 4, py, 4, TS))


def _bake_edges(surf, level, t, tx, ty, px, py):
    solid = (T.ROCK, T.CAVE_DOOR, T.CAVE_WALL)
    # sombra proyectada por montañas hacia el sur
    if level.tile(tx, ty - 1) in solid:
        shade = pygame.Surface((TS, 12), pygame.SRCALPHA)
        for k in range(12):
            pygame.draw.rect(shade, (0, 0, 0, 70 - k * 5), (0, k, TS, 1))
        surf.blit(shade, (px, py))
    if t == T.SAND and level.tile(tx, ty) == T.SAND:
        pass
    # borde oscuro de hierba contra arena/agua para dar definición
    if t == T.GRASS:
        for (dx, dy, rect) in ((0, -1, (0, 0, TS, 3)), (0, 1, (0, TS - 3, TS, 3)),
                               (-1, 0, (0, 0, 3, TS)), (1, 0, (TS - 3, 0, 3, TS))):
            nt = level.tile(tx + dx, ty + dy)
            if nt == T.SAND:
                pygame.draw.rect(surf, (118, 160, 82), (px + rect[0], py + rect[1], rect[2], rect[3]))
            elif nt == T.SNOW:
                pygame.draw.rect(surf, (170, 206, 190), (px + rect[0], py + rect[1], rect[2], rect[3]))
