"""Carga y caché de imágenes. Todo se escala una sola vez y se reutiliza."""
import os
import sys
import pygame

if getattr(sys, "frozen", False):
    ROOT = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(ROOT, "assets", "images")

_raw = {}
_scaled = {}
_flipped = {}
_shadows = {}
_tinted = {}


def path(*parts):
    return os.path.join(IMG_DIR, *parts)


def load(rel):
    """Carga una imagen relativa a assets/images (con alfa) y la cachea."""
    s = _raw.get(rel)
    if s is None:
        full = path(*rel.split("/"))
        try:
            s = pygame.image.load(full).convert_alpha()
        except (pygame.error, FileNotFoundError):
            s = pygame.Surface((32, 32), pygame.SRCALPHA)
            s.fill((255, 0, 255, 255))
        _raw[rel] = s
    return s


def scaled(rel, w=None, h=None, smooth=True):
    """Escala manteniendo proporción si sólo se da w o h."""
    key = (rel, w, h, smooth)
    s = _scaled.get(key)
    if s is None:
        src = load(rel)
        sw, sh = src.get_size()
        if w is None and h is None:
            w, h = sw, sh
        elif w is None:
            w = max(1, round(sw * h / sh))
        elif h is None:
            h = max(1, round(sh * w / sw))
        if (w, h) == (sw, sh):
            s = src
        elif smooth:
            s = pygame.transform.smoothscale(src, (w, h))
        else:
            s = pygame.transform.scale(src, (w, h))
        _scaled[key] = s
    return s


def fit(rel, box_w, box_h, smooth=True):
    """Escala para caber en una caja conservando proporción."""
    src = load(rel)
    sw, sh = src.get_size()
    k = min(box_w / sw, box_h / sh)
    return scaled(rel, max(1, round(sw * k)), max(1, round(sh * k)), smooth)


def flipx(surf, cache=True):
    """Espejo horizontal. Con cache=False no se guarda (para superficies temporales)."""
    if not cache:
        return pygame.transform.flip(surf, True, False)
    hit = _flipped.get(id(surf))
    if hit is None or hit[0] is not surf:
        hit = (surf, pygame.transform.flip(surf, True, False))   # se guarda `surf` para que su id no se reutilice
        _flipped[id(surf)] = hit
    return hit[1]


def tint(surf, rgb, mult=True):
    """Devuelve una copia teñida (multiplicación de color) cacheada."""
    key = (id(surf), rgb, mult)
    hit = _tinted.get(key)
    if hit is None or hit[0] is not surf:
        s = surf.copy()
        flag = pygame.BLEND_RGB_MULT if mult else pygame.BLEND_RGB_ADD
        s.fill(rgb, special_flags=flag)
        hit = (surf, s)
        _tinted[key] = hit
    return hit[1]


def shadow(w, h, alpha=70):
    """Elipse de sombra suave bajo objetos y entidades."""
    key = (w, h, alpha)
    s = _shadows.get(key)
    if s is None:
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        steps = 4
        for i in range(steps):
            k = i / steps
            a = int(alpha * (0.35 + 0.65 * (i + 1) / steps) / steps * 1.9)
            r = pygame.Rect(int(w * k * 0.22), int(h * k * 0.22),
                            max(2, int(w * (1 - k * 0.44))), max(2, int(h * (1 - k * 0.44))))
            pygame.draw.ellipse(s, (0, 0, 0, min(255, a)), r)
        _shadows[key] = s
    return s


def strip(rel, frames, scale=1, smooth=False):
    """Divide una tira horizontal en `frames` cuadros."""
    src = load(rel)
    fw = src.get_width() // frames
    fh = src.get_height()
    out = []
    for i in range(frames):
        f = src.subsurface(pygame.Rect(i * fw, 0, fw, fh)).copy()
        if scale != 1:
            size = (int(fw * scale), int(fh * scale))
            f = pygame.transform.smoothscale(f, size) if smooth else pygame.transform.scale(f, size)
        out.append(f)
    return out


def trim(surf):
    """Recorta el borde transparente. Devuelve (superficie, (ox, oy))."""
    r = surf.get_bounding_rect()
    if r.width == 0 or r.height == 0:
        return surf, (0, 0)
    return surf.subsurface(r).copy(), (r.x, r.y)


def clear_caches():
    _raw.clear(); _scaled.clear(); _flipped.clear(); _shadows.clear(); _tinted.clear()
