"""Objetos caídos en el suelo que el jugador recoge acercándose (con imán)."""
import math
import random
from .. import assets, items, audio
from ..util import dist

_rng = random.Random()
PICKUP_RANGE = 26
MAGNET_RANGE = 125
LIFETIME = 300.0


class ItemDrop:
    __slots__ = ("id", "count", "dur", "x", "y", "z", "vz", "vx", "vy", "age", "alive", "delay")

    def __init__(self, item_id, count, x, y, dur=None, spread=60.0):
        self.id, self.count, self.dur = item_id, count, dur
        self.x, self.y = x, y
        self.z = 0.0
        self.vz = _rng.uniform(150, 260)
        a = _rng.uniform(0, math.tau)
        sp = _rng.uniform(0.3, 1.0) * spread
        self.vx, self.vy = math.cos(a) * sp, math.sin(a) * sp * 0.6
        self.age = 0.0
        self.delay = 0.45             # tiempo antes de poder recogerse
        self.alive = True

    @property
    def sort_y(self):
        return self.y

    def update(self, dt, level, player):
        self.age += dt
        if self.age > LIFETIME:
            self.alive = False
            return
        self.delay -= dt
        if self.z > 0 or self.vz > 0:                      # salto inicial
            self.z += self.vz * dt
            self.vz -= 760 * dt
            self.x += self.vx * dt
            self.y += self.vy * dt
            if self.z <= 0:
                self.z, self.vz = 0.0, 0.0
                self.vx = self.vy = 0.0
        if self.delay > 0 or player.dead:
            return
        px, py = player.x, player.y - 14
        d = dist(self.x, self.y, px, py)
        if d < MAGNET_RANGE and player.inv.room_for(self.id, self.count):
            k = (1.0 - d / MAGNET_RANGE)
            sp = 160 + 520 * k
            self.x += (px - self.x) / max(d, 1) * sp * dt
            self.y += (py - self.y) / max(d, 1) * sp * dt
            d = dist(self.x, self.y, px, py)
        if d < PICKUP_RANGE:
            left = player.inv.add(self.id, self.count, self.dur)
            got = self.count - left
            if got > 0:
                player.on_pickup(self.id, got)
                audio.play("pickup", 0.6)
            self.count = left
            if left == 0:
                self.alive = False

    def draw(self, surf, cx, cy):
        ic = items.icon(self.id, 30)
        bob = math.sin(self.age * 4 + self.x) * 2.5 if self.z <= 0 else 0
        sx, sy = self.x - cx, self.y - cy
        sh = assets.shadow(22, 8, 70)
        surf.blit(sh, (int(sx - 11), int(sy - 3)))
        surf.blit(ic, (int(sx - ic.get_width() / 2), int(sy - ic.get_height() - 4 - self.z - 4 - bob)))
        if self.count > 1:
            pass


def scatter(level, x, y, item_id, count, spread=70.0, dur=None):
    """Suelta `count` unidades como pilas de 1–N alrededor del punto."""
    if count <= 0:
        return
    stack = 1 if count <= 4 else 2 if count <= 8 else 4
    left = count
    while left > 0:
        n = min(stack, left)
        level.drops.append(ItemDrop(item_id, n, x, y, dur, spread))
        left -= n
