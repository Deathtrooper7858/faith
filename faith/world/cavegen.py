"""Generación de cuevas (autómata celular + flood fill) – puro Python, determinista."""
import random
from . import terrain as T

W = H = 64


def generate(seed):
    rng = random.Random(seed)
    for _attempt in range(12):
        grid = [[rng.random() < 0.455 for _ in range(W)] for _ in range(H)]    # True = muro
        for x in range(W):
            grid[0][x] = grid[H - 1][x] = True
        for y in range(H):
            grid[y][0] = grid[y][W - 1] = True
        ex, ey = W // 2, H - 5                                                  # punto de aparición
        for _ in range(5):
            new = [row[:] for row in grid]
            for y in range(1, H - 1):
                for x in range(1, W - 1):
                    n = sum(grid[y + j][x + i] for j in (-1, 0, 1) for i in (-1, 0, 1))
                    new[y][x] = n >= 5
            grid = new
        for y in range(ey - 3, ey + 3):                                         # sala de entrada
            for x in range(ex - 4, ex + 5):
                grid[y][x] = False
        for y in range(1, H - 1):
            grid[y][0] = grid[y][W - 1] = True
        # flood fill desde la entrada: sólo se conserva la región conectada
        seen = {(ex, ey)}
        stack = [(ex, ey)]
        while stack:
            x, y = stack.pop()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 < nx < W - 1 and 0 < ny < H - 1 and not grid[ny][nx] and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    stack.append((nx, ny))
        if len(seen) >= 900:
            break
    tiles = {}
    for y in range(H):
        for x in range(W):
            tiles[(x, y)] = T.CAVE_FLOOR if (x, y) in seen else T.CAVE_WALL
    floor = sorted(seen)
    far = lambda p: abs(p[0] - ex) + abs(p[1] - ey)
    # charcos de agua y lava lejos de la entrada
    pools = 0
    for _ in range(80):
        if pools >= 7:
            break
        cx, cy = rng.choice(floor)
        if far((cx, cy)) < 14:
            continue
        kind = T.LAVA if rng.random() < 0.45 else T.SHALLOW
        r = rng.randint(1, 2)
        for j in range(-r, r + 1):
            for i in range(-r, r + 1):
                p = (cx + i, cy + j)
                if p in seen and i * i + j * j <= r * r + 1 and far(p) >= 12:
                    tiles[p] = kind
        pools += 1
    door = (ex, ey + 3)                                                         # puerta de salida (muro)
    tiles[door] = T.CAVE_DOOR
    # asegurar un camino sin lava junto a la entrada
    for y in range(ey - 3, ey + 3):
        for x in range(ex - 4, ex + 5):
            if tiles[(x, y)] in (T.LAVA, T.SHALLOW):
                tiles[(x, y)] = T.CAVE_FLOOR
    # minerales: pegados a las paredes, más oro cuanto más lejos
    ores = []
    for p in floor:
        if tiles[p] != T.CAVE_FLOOR or far(p) < 7:
            continue
        x, y = p
        walls = sum(tiles.get((x + i, y + j), T.CAVE_WALL) == T.CAVE_WALL for i, j in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if walls >= 1 and rng.random() < 0.12:
            roll = rng.random() * 0.75 + min(far(p) / 70.0, 0.3)
            ores.append((p, "ore_coal" if roll < 0.52 else "ore_iron" if roll < 0.88 else "ore_gold"))
    chests = []
    cand = [p for p in floor if tiles[p] == T.CAVE_FLOOR and far(p) > 22]
    rng.shuffle(cand)
    for p in cand:
        if len(chests) >= 4:
            break
        if all(abs(p[0] - c[0]) + abs(p[1] - c[1]) > 14 for c in chests):
            chests.append(p)
    return dict(tiles=tiles, spawn=(ex, ey), door=door, ores=ores, chests=chests, floor=floor)
