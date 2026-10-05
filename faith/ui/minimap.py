"""Minimapa que se actualiza de forma incremental (unas pocas filas por fotograma)."""
import pygame
from .. import settings as S
from ..world import terrain as T
from . import widgets as W

RADIUS = 36            # tiles a cada lado
ROWS_PER_FRAME = 10
SIZE = RADIUS * 2 + 1
SCALE = 3


class Minimap:
    def __init__(self):
        self.surf = pygame.Surface((SIZE, SIZE))
        self.out = pygame.Surface((SIZE * SCALE, SIZE * SCALE))
        self.view = pygame.Surface((SIZE * SCALE, SIZE * SCALE))
        self.row = 0
        self.center = (0, 0)
        self.next_center = (0, 0)
        self.level = None
        self.idle = 0.0

    def reset(self, level, center=None):
        self.level = level
        self.surf.fill((10, 10, 14))
        self.row = 0
        if center is not None:
            self.center = center
            colors = T.MINIMAP_COLORS
            for j in range(SIZE):
                for i in range(SIZE):
                    self.surf.set_at((i, j), colors[level.tile(center[0] - RADIUS + i, center[1] - RADIUS + j)])
            self.out = pygame.transform.scale(self.surf, (SIZE * SCALE, SIZE * SCALE))

    def update(self, level, tx, ty, dt=1 / 60):
        if level is not self.level:
            self.reset(level, (tx, ty))
        if abs(tx - self.center[0]) > RADIUS - 12 or abs(ty - self.center[1]) > RADIUS - 12:
            self.reset(level, (tx, ty))
        if self.row == 0:
            # tras terminar una pasada, esperar a que el jugador se mueva (o pasen 2 s) antes de repintar
            self.idle += dt
            if (tx, ty) == self.center and self.idle < 2.0:
                return
            self.idle = 0.0
            self.center = (tx, ty)           # snapshot de la cuadrícula en la que se pinta
        cx, cy = self.center
        end = min(SIZE, self.row + ROWS_PER_FRAME)
        colors = T.MINIMAP_COLORS
        tile = level.tile
        for j in range(self.row, end):
            for i in range(SIZE):
                self.surf.set_at((i, j), colors[tile(cx - RADIUS + i, cy - RADIUS + j)])
        self.row = end
        if self.row >= SIZE:
            self.row = 0
            self.out = pygame.transform.scale(self.surf, (SIZE * SCALE, SIZE * SCALE))

    def draw(self, surf, level, player, pos, time_s):
        x, y = pos
        size = SIZE * SCALE
        W.panel(surf, (x - 6, y - 6, size + 12, size + 12), 235, 10)
        ptx, pty = player.x / S.TILE, player.y / S.TILE
        # desplazamiento suave: el mapa se pinta sobre `center`, el jugador se mueve sobre él
        ox = (ptx - self.center[0] - 0.5 + RADIUS) * SCALE
        oy = (pty - self.center[1] - 0.5 + RADIUS) * SCALE
        self.view.fill((10, 10, 14))
        self.view.blit(self.out, (int(size / 2 - ox - SCALE / 2), int(size / 2 - oy - SCALE / 2)))
        # estructuras y minerales conocidos
        surf.blit(self.view, (x, y))
        # jugador
        cx, cy = x + size // 2, y + size // 2
        pulse = 1 + int(time_s * 3) % 2
        pygame.draw.circle(surf, (0, 0, 0), (cx, cy), 5)
        pygame.draw.circle(surf, (255, 240, 120), (cx, cy), 3 + (pulse - 1))
        # flecha de orientación
        pygame.draw.line(surf, (255, 255, 255), (cx, cy), (cx + player.fx * 9, cy + player.fy * 9), 2)
        pygame.draw.rect(surf, (90, 96, 130), (x, y, size, size), 1)
        for m in level.mobs:
            mx, my = (m.x - player.x) / S.TILE * SCALE, (m.y - player.y) / S.TILE * SCALE
            if abs(mx) < size / 2 - 3 and abs(my) < size / 2 - 3 and m.hostile and not m.dying:
                pygame.draw.rect(surf, (230, 60, 60), (int(cx + mx) - 1, int(cy + my) - 1, 3, 3))
