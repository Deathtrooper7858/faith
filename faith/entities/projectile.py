"""Flechas (del jugador y de los arqueros enemigos)."""
import math
import pygame
from ..util import dist
from .. import audio, assets


class Projectile:
    def __init__(self, x, y, angle, speed, damage, owner, max_range=640.0, pierce=False):
        self.x, self.y = x, y            # posición a la altura del cuerpo
        self.angle = angle
        self.vx, self.vy = math.cos(angle) * speed, math.sin(angle) * speed
        self.damage = damage
        self.owner = owner               # "player" | "enemy"
        self.range = max_range
        self.alive = True
        self.stuck = 0.0
        self.trail = []

    def update(self, dt, level, player):
        if self.stuck > 0:
            self.stuck -= dt
            if self.stuck <= 0:
                self.alive = False
            return
        step = math.hypot(self.vx, self.vy) * dt
        n = max(1, int(step // 10) + 1)
        for _ in range(n):
            self.x += self.vx * dt / n
            self.y += self.vy * dt / n
            self.range -= step / n
            if self._collide(level, player):
                return
        if self.range <= 0:
            self.alive = False

    def _collide(self, level, player):
        # terreno / objetos sólidos (mide a la altura de los pies)
        r = pygame.Rect(int(self.x) - 2, int(self.y + 14) - 2, 4, 4)
        if level.collides(r):
            self.stuck = 0.8
            self.vx = self.vy = 0.0
            level.fx.chips(self.x, self.y, "dust", 4)
            audio.play("hit", 0.3)
            return True
        if self.owner == "player":
            for m in level.mobs:
                if m.dying or m.remove:
                    continue
                bx, by = m.body_pos()
                if dist(self.x, self.y, bx, by) < m.hit_radius:
                    m.hurt(self.damage, self.angle, level, player)
                    self.alive = False
                    return True
        else:
            if not player.dead and dist(self.x, self.y, player.x, player.y - 24) < 20:
                player.hurt(self.damage, self.angle, level)
                self.alive = False
                return True
        return False

    def draw(self, surf, cx, cy):
        sx, sy = self.x - cx, self.y - cy
        c, s = math.cos(self.angle), math.sin(self.angle)
        tail = (sx - c * 20, sy - s * 20)
        head = (sx, sy)
        pygame.draw.line(surf, (120, 82, 46), tail, head, 2)
        pygame.draw.line(surf, (235, 235, 240), (tail[0] + s * 3 - c * 3, tail[1] - c * 3 - s * 3), tail, 1)
        pygame.draw.line(surf, (235, 235, 240), (tail[0] - s * 3 - c * 3, tail[1] + c * 3 - s * 3), tail, 1)
        pygame.draw.circle(surf, (200, 204, 214), (int(head[0]), int(head[1])), 2)
        # sombra en el suelo
        surf.blit(assets.shadow(12, 5, 90), (int(sx - 6), int(sy + 11)))

    @property
    def sort_y(self):
        return self.y + 14
