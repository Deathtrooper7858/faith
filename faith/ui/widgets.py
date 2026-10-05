"""Piezas básicas de interfaz: texto cacheado, paneles, barras, botones, tooltips."""
import math
import pygame
from .. import settings as S

_fonts = {}
_text = {}
_panels = {}


def font(size):
    f = _fonts.get(size)
    if f is None:
        f = pygame.font.Font(None, size)
        _fonts[size] = f
    return f


def render(text, size=24, color=S.C_TEXT, shadow=True):
    key = (text, size, color, shadow)
    s = _text.get(key)
    if s is None:
        f = font(size)
        base = f.render(text, True, color)
        if shadow:
            sh = f.render(text, True, (0, 0, 0))
            s = pygame.Surface((base.get_width() + 2, base.get_height() + 2), pygame.SRCALPHA)
            s.blit(sh, (2, 2))
            s.blit(base, (0, 0))
        else:
            s = base
        if len(_text) > 900:
            _text.clear()
        _text[key] = s
    return s


def text(surf, msg, pos, size=24, color=S.C_TEXT, anchor="topleft", shadow=True):
    s = render(str(msg), size, color, shadow)
    r = s.get_rect()
    setattr(r, anchor, (int(pos[0]), int(pos[1])))
    surf.blit(s, r)
    return r


def wrap(msg, size, width):
    f = font(size)
    words, lines, cur = msg.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.size(t)[0] <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def panel_surface(w, h, alpha=225, radius=12, border=S.C_PANEL_EDGE, fill=(18, 20, 30)):
    key = (w, h, alpha, radius, border, fill)
    s = _panels.get(key)
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(s, (*fill, alpha), (0, 0, w, h), border_radius=radius)
        # degradado sutil superior
        hl = pygame.Surface((w - 4, max(2, h // 5)), pygame.SRCALPHA)
        hl.fill((255, 255, 255, 10))
        s.blit(hl, (2, 2))
        pygame.draw.rect(s, border, (0, 0, w, h), 2, border_radius=radius)
        _panels[key] = s
    return s


def panel(surf, rect, alpha=225, radius=12, border=S.C_PANEL_EDGE, fill=(18, 20, 30), shadow=True):
    x, y, w, h = rect
    if shadow:
        sh = panel_surface(w + 12, h + 12, 70, radius + 4, (0, 0, 0), (0, 0, 0))
        surf.blit(sh, (x - 6, y - 2))
    surf.blit(panel_surface(int(w), int(h), alpha, radius, border, fill), (x, y))


def bar(surf, x, y, w, h, frac, color, back=(26, 28, 38), border=(8, 8, 12), flash=False):
    frac = max(0.0, min(1.0, frac))
    pygame.draw.rect(surf, border, (x - 2, y - 2, w + 4, h + 4), border_radius=4)
    pygame.draw.rect(surf, back, (x, y, w, h), border_radius=3)
    fw = int(w * frac)
    if fw > 0:
        c = color
        if flash and int(pygame.time.get_ticks() / 160) % 2 == 0:
            c = (255, 255, 255)
        pygame.draw.rect(surf, c, (x, y, fw, h), border_radius=3)
        light = tuple(min(255, v + 50) for v in c)
        pygame.draw.rect(surf, light, (x + 1, y + 1, max(0, fw - 2), max(1, h // 3)), border_radius=2)


def heart(surf, cx, cy, size=9, color=S.C_HP):
    r = size // 2 + 1
    pygame.draw.circle(surf, color, (cx - r // 2 - 1, cy - 1), r)
    pygame.draw.circle(surf, color, (cx + r // 2 + 1, cy - 1), r)
    pygame.draw.polygon(surf, color, [(cx - size // 2 - 3, cy + 1), (cx + size // 2 + 3, cy + 1), (cx, cy + size // 2 + 5)])
    pygame.draw.circle(surf, (255, 190, 190), (cx - r // 2 - 2, cy - 3), 1)


def bolt(surf, cx, cy, color=S.C_STAMINA):
    pts = [(cx + 2, cy - 8), (cx - 4, cy + 1), (cx, cy + 1), (cx - 2, cy + 8), (cx + 5, cy - 2), (cx + 1, cy - 2)]
    pygame.draw.polygon(surf, color, pts)


def hover_rect(rect):
    return pygame.Rect(rect).collidepoint(pygame.mouse.get_pos())


class Button:
    def __init__(self, label, rect, callback=None, size=30, enabled=True):
        self.label, self.rect, self.cb, self.size, self.enabled = label, pygame.Rect(rect), callback, size, enabled
        self.hover = 0.0

    def update(self, dt, mouse):
        target = 1.0 if (self.enabled and self.rect.collidepoint(mouse)) else 0.0
        self.hover += (target - self.hover) * min(1.0, dt * 14)

    def draw(self, surf):
        r = self.rect
        k = self.hover
        fill = (int(28 + 30 * k), int(32 + 34 * k), int(50 + 44 * k))
        border = (int(86 + 150 * k), int(92 + 122 * k), int(124 - 30 * k)) if self.enabled else (60, 62, 76)
        pygame.draw.rect(surf, (0, 0, 0), (r.x + 2, r.y + 3, r.w, r.h), border_radius=10)
        pygame.draw.rect(surf, fill, r, border_radius=10)
        pygame.draw.rect(surf, border, r, 2, border_radius=10)
        col = S.C_TEXT if self.enabled else (110, 112, 126)
        if k > 0.5:
            col = S.C_GOLD
        text(surf, self.label, r.center, self.size, col, "center")

    def click(self, pos):
        if self.enabled and self.rect.collidepoint(pos) and self.cb:
            self.cb()
            return True
        return False


def tooltip(surf, lines, pos, title_color=S.C_TEXT):
    """lines: [(texto, color)] — la primera línea es el título."""
    if not lines:
        return
    sizes = [26 if i == 0 else 21 for i in range(len(lines))]
    w = max(font(sizes[i]).size(l[0])[0] for i, l in enumerate(lines)) + 24
    h = sum(font(s).get_height() for s in sizes) + 16 + 3 * (len(lines) - 1)
    x, y = pos[0] + 16, pos[1] + 16
    if x + w > S.SCREEN_W - 6:
        x = pos[0] - w - 12
    if y + h > S.SCREEN_H - 6:
        y = S.SCREEN_H - h - 6
    panel(surf, (x, y, w, h), 240, 8, (110, 116, 160), (12, 13, 20), shadow=False)
    cy = y + 8
    for i, (t, c) in enumerate(lines):
        text(surf, t, (x + 12, cy), sizes[i], c)
        cy += font(sizes[i]).get_height() + 3
