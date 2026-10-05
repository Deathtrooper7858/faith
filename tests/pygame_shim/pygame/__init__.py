"""Shim mínimo de pygame (PIL + numpy) SOLO para pruebas headless del juego.
No es una implementación completa; cubre la API que usa Faith of Surviving."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SRCALPHA = 0x10000
SCALED = 0x200
RESIZABLE = 0x10
FULLSCREEN = 0x80
BLEND_RGB_ADD, BLEND_RGB_SUB, BLEND_RGB_MULT = 1, 2, 3
BLEND_RGBA_ADD, BLEND_RGBA_SUB, BLEND_RGBA_MULT = 6, 7, 8
BLEND_ADD, BLEND_MULT = 1, 3

QUIT, KEYDOWN, KEYUP, MOUSEMOTION, MOUSEBUTTONUP, MOUSEBUTTONDOWN, MOUSEWHEEL = 256, 768, 769, 1024, 1026, 1025, 1027
VIDEORESIZE, WINDOWFOCUSLOST = 32769, 32786


class error(Exception):
    pass


# ── Teclas ───────────────────────────────────────────────────────────────────
_special = dict(ESCAPE=27, RETURN=13, SPACE=32, TAB=9, BACKSPACE=8, LSHIFT=1073742049, RSHIFT=1073742053,
                LCTRL=1073742048, UP=1073741906, DOWN=1073741905, LEFT=1073741904, RIGHT=1073741903,
                F1=1073741882, F2=1073741883, F3=1073741884, F4=1073741885, F5=1073741886, F11=1073741898,
                DELETE=127, PAGEUP=1073741899, PAGEDOWN=1073741902, MINUS=45, EQUALS=61)
for _n, _v in _special.items():
    globals()["K_" + _n] = _v
for _c in "abcdefghijklmnopqrstuvwxyz0123456789":
    globals()["K_" + _c] = ord(_c)


# ── Rect ─────────────────────────────────────────────────────────────────────
class Rect:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, *a):
        if len(a) == 1:
            a = a[0]
            if isinstance(a, Rect):
                a = (a.x, a.y, a.w, a.h)
        if len(a) == 2:
            (x, y), (w, h) = a
        else:
            x, y, w, h = a
        self.x, self.y, self.w, self.h = int(x), int(y), int(w), int(h)

    def __iter__(self):
        return iter((self.x, self.y, self.w, self.h))

    def __repr__(self):
        return f"Rect({self.x}, {self.y}, {self.w}, {self.h})"

    def __eq__(self, o):
        try:
            return tuple(self) == tuple(Rect(o))
        except Exception:
            return False

    def __getitem__(self, i):
        return (self.x, self.y, self.w, self.h)[i]

    def copy(self): return Rect(self.x, self.y, self.w, self.h)

    width = property(lambda s: s.w, lambda s, v: setattr(s, "w", int(v)))
    height = property(lambda s: s.h, lambda s, v: setattr(s, "h", int(v)))
    left = property(lambda s: s.x, lambda s, v: setattr(s, "x", int(v)))
    top = property(lambda s: s.y, lambda s, v: setattr(s, "y", int(v)))
    right = property(lambda s: s.x + s.w, lambda s, v: setattr(s, "x", int(v) - s.w))
    bottom = property(lambda s: s.y + s.h, lambda s, v: setattr(s, "y", int(v) - s.h))
    centerx = property(lambda s: s.x + s.w // 2, lambda s, v: setattr(s, "x", int(v) - s.w // 2))
    centery = property(lambda s: s.y + s.h // 2, lambda s, v: setattr(s, "y", int(v) - s.h // 2))
    center = property(lambda s: (s.centerx, s.centery), lambda s, v: (setattr(s, "centerx", v[0]), setattr(s, "centery", v[1])))
    topleft = property(lambda s: (s.x, s.y), lambda s, v: (setattr(s, "x", int(v[0])), setattr(s, "y", int(v[1]))))
    topright = property(lambda s: (s.right, s.y), lambda s, v: (setattr(s, "right", v[0]), setattr(s, "y", int(v[1]))))
    bottomleft = property(lambda s: (s.x, s.bottom), lambda s, v: (setattr(s, "x", int(v[0])), setattr(s, "bottom", v[1])))
    bottomright = property(lambda s: (s.right, s.bottom), lambda s, v: (setattr(s, "right", v[0]), setattr(s, "bottom", v[1])))
    midbottom = property(lambda s: (s.centerx, s.bottom), lambda s, v: (setattr(s, "centerx", v[0]), setattr(s, "bottom", v[1])))
    midtop = property(lambda s: (s.centerx, s.y), lambda s, v: (setattr(s, "centerx", v[0]), setattr(s, "y", int(v[1]))))
    midleft = property(lambda s: (s.x, s.centery), lambda s, v: (setattr(s, "x", int(v[0])), setattr(s, "centery", v[1])))
    midright = property(lambda s: (s.right, s.centery), lambda s, v: (setattr(s, "right", v[0]), setattr(s, "centery", v[1])))
    size = property(lambda s: (s.w, s.h), lambda s, v: (setattr(s, "w", int(v[0])), setattr(s, "h", int(v[1]))))

    def colliderect(self, o):
        o = Rect(o)
        return self.x < o.right and o.x < self.right and self.y < o.bottom and o.y < self.bottom

    def collidepoint(self, *p):
        if len(p) == 1:
            p = p[0]
        return self.x <= p[0] < self.right and self.y <= p[1] < self.bottom

    def inflate(self, dx, dy): return Rect(self.x - dx // 2, self.y - dy // 2, self.w + dx, self.h + dy)
    def move(self, dx, dy): return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def move_ip(self, dx, dy):
        self.x += int(dx); self.y += int(dy)

    def inflate_ip(self, dx, dy):
        r = self.inflate(dx, dy); self.x, self.y, self.w, self.h = r

    def union(self, o):
        o = Rect(o); x = min(self.x, o.x); y = min(self.y, o.y)
        return Rect(x, y, max(self.right, o.right) - x, max(self.bottom, o.bottom) - y)

    def clip(self, o):
        o = Rect(o); x = max(self.x, o.x); y = max(self.y, o.y)
        r = min(self.right, o.right); b = min(self.bottom, o.bottom)
        return Rect(x, y, max(0, r - x), max(0, b - y))

    def contains(self, o):
        o = Rect(o); return self.x <= o.x and self.y <= o.y and o.right <= self.right and o.bottom <= self.bottom

    def collidelist(self, lst):
        for i, r in enumerate(lst):
            if self.colliderect(r):
                return i
        return -1


def _col(c):
    if len(c) == 3:
        return (int(c[0]), int(c[1]), int(c[2]), 255)
    return (int(c[0]), int(c[1]), int(c[2]), int(c[3]))


# ── Surface ──────────────────────────────────────────────────────────────────
class Surface:
    def __init__(self, size, flags=0, depth=0, arr=None):
        self.flags = flags
        self._alpha = 255
        if arr is not None:
            self.a = arr
        else:
            w, h = int(size[0]), int(size[1])
            self.a = np.zeros((h, w, 4), np.uint8)
            if not (flags & SRCALPHA):
                self.a[..., 3] = 255

    @property
    def has_alpha(self): return bool(self.flags & SRCALPHA)
    def get_size(self): return (self.a.shape[1], self.a.shape[0])
    def get_width(self): return self.a.shape[1]
    def get_height(self): return self.a.shape[0]
    def get_flags(self): return self.flags

    def get_rect(self, **kw):
        r = Rect(0, 0, *self.get_size())
        for k, v in kw.items():
            setattr(r, k, v)
        return r

    def copy(self):
        s = Surface((1, 1), self.flags, arr=self.a.copy()); s._alpha = self._alpha; return s

    def convert(self):
        s = Surface((1, 1), 0, arr=self.a.copy()); s.a[..., 3] = 255; return s

    def convert_alpha(self):
        return Surface((1, 1), SRCALPHA, arr=self.a.copy())

    def set_alpha(self, v, flags=0): self._alpha = 255 if v is None else int(v)
    def get_alpha(self): return self._alpha
    def set_colorkey(self, *a, **k): pass

    def subsurface(self, r):
        r = Rect(r)
        return Surface((1, 1), self.flags, arr=self.a[r.y:r.y + r.h, r.x:r.x + r.w])

    def get_at(self, p): return tuple(int(v) for v in self.a[int(p[1]), int(p[0])])

    def set_at(self, p, c):
        x, y = int(p[0]), int(p[1])
        if 0 <= x < self.a.shape[1] and 0 <= y < self.a.shape[0]:
            self.a[y, x] = _col(c)

    def get_bounding_rect(self, min_alpha=1):
        ys, xs = np.nonzero(self.a[..., 3] >= min_alpha)
        if len(xs) == 0:
            return Rect(0, 0, 0, 0)
        return Rect(xs.min(), ys.min(), xs.max() - xs.min() + 1, ys.max() - ys.min() + 1)

    def fill(self, color, rect=None, special_flags=0):
        c = _col(color)
        if rect is None:
            d = self.a
        else:
            r = Rect(rect).clip(Rect(0, 0, *self.get_size()))
            d = self.a[r.y:r.y + r.h, r.x:r.x + r.w]
        if special_flags == BLEND_RGB_MULT:
            d[..., :3] = (d[..., :3].astype(np.uint16) * np.array(c[:3], np.uint16) // 255).astype(np.uint8)
        elif special_flags == BLEND_RGB_ADD:
            d[..., :3] = np.minimum(255, d[..., :3].astype(np.uint16) + np.array(c[:3], np.uint16)).astype(np.uint8)
        elif special_flags == BLEND_RGBA_SUB:
            d[...] = np.maximum(0, d.astype(np.int16) - np.array(c, np.int16)).astype(np.uint8)
        elif special_flags == BLEND_RGBA_MULT:
            d[...] = (d.astype(np.uint16) * np.array(c, np.uint16) // 255).astype(np.uint8)
        elif special_flags == BLEND_RGBA_ADD:
            d[...] = np.minimum(255, d.astype(np.uint16) + np.array(c, np.uint16)).astype(np.uint8)
        else:
            d[...] = c if self.has_alpha else (c[0], c[1], c[2], 255)

    def blit(self, src, dest, area=None, special_flags=0):
        if isinstance(dest, Rect):
            dx, dy = dest.x, dest.y
        else:
            dx, dy = int(dest[0]), int(dest[1])
        if area is not None:
            ar = Rect(area); sx0, sy0, w, h = ar.x, ar.y, ar.w, ar.h
        else:
            sx0, sy0 = 0, 0; w, h = src.get_size()
        x0, y0 = max(dx, 0), max(dy, 0)
        x1, y1 = min(dx + w, self.a.shape[1]), min(dy + h, self.a.shape[0])
        if x1 <= x0 or y1 <= y0:
            return Rect(dx, dy, 0, 0)
        s = src.a[sy0 + (y0 - dy):sy0 + (y1 - dy), sx0 + (x0 - dx):sx0 + (x1 - dx)]
        d = self.a[y0:y1, x0:x1]
        f = special_flags
        if f == BLEND_RGBA_SUB:
            d[...] = np.maximum(0, d.astype(np.int16) - s.astype(np.int16)).astype(np.uint8)
        elif f == BLEND_RGB_MULT:
            d[..., :3] = (d[..., :3].astype(np.uint16) * s[..., :3] // 255).astype(np.uint8)
        elif f == BLEND_RGBA_MULT:
            d[...] = (d.astype(np.uint16) * s // 255).astype(np.uint8)
        elif f in (BLEND_RGB_ADD,):
            a = (s[..., 3:4].astype(np.float32) / 255.0) if src.has_alpha else 1.0
            d[..., :3] = np.minimum(255, d[..., :3].astype(np.float32) + s[..., :3] * a).astype(np.uint8)
        elif f == BLEND_RGBA_ADD:
            d[...] = np.minimum(255, d.astype(np.uint16) + s).astype(np.uint8)
        elif f == BLEND_RGB_SUB:
            d[..., :3] = np.maximum(0, d[..., :3].astype(np.int16) - s[..., :3]).astype(np.uint8)
        else:
            if src.has_alpha or src._alpha < 255:
                sa = s[..., 3:4].astype(np.float32) / 255.0 * (src._alpha / 255.0)
                rgb = s[..., :3].astype(np.float32) * sa + d[..., :3].astype(np.float32) * (1 - sa)
                d[..., :3] = rgb.astype(np.uint8)
                if self.has_alpha:
                    da = d[..., 3:4].astype(np.float32) / 255.0
                    d[..., 3:4] = ((sa + da * (1 - sa)) * 255).astype(np.uint8)
            else:
                d[..., :3] = s[..., :3]
        return Rect(x0, y0, x1 - x0, y1 - y0)


# ── Dibujo (PIL sobre región recortada) ──────────────────────────────────────
def _paint(surf, bbox, fn):
    x0, y0, x1, y1 = bbox
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(surf.a.shape[1], int(x1)), min(surf.a.shape[0], int(y1))
    if x1 <= x0 or y1 <= y0:
        return
    region = surf.a[y0:y1, x0:x1]
    im = Image.fromarray(np.ascontiguousarray(region), "RGBA")
    d = ImageDraw.Draw(im)
    fn(d, x0, y0)
    region[...] = np.asarray(im)


class _Draw:
    def rect(self, surf, color, rect, width=0, border_radius=0, **k):
        r = Rect(rect); c = _col(color)
        if not surf.has_alpha:
            c = (c[0], c[1], c[2], 255)

        def f(d, ox, oy):
            box = [r.x - ox, r.y - oy, r.x - ox + r.w - 1, r.y - oy + r.h - 1]
            if r.w <= 0 or r.h <= 0:
                return
            if border_radius > 0:
                d.rounded_rectangle(box, radius=border_radius, fill=c if width == 0 else None,
                                    outline=c if width else None, width=max(1, width))
            elif width == 0:
                d.rectangle(box, fill=c)
            else:
                d.rectangle(box, outline=c, width=width)
        _paint(surf, (r.x, r.y, r.right, r.bottom), f)
        return r

    def circle(self, surf, color, center, radius, width=0, **k):
        cx, cy = int(center[0]), int(center[1]); r = int(radius); c = _col(color)

        def f(d, ox, oy):
            d.ellipse([cx - r - ox, cy - r - oy, cx + r - ox, cy + r - oy], fill=c if width == 0 else None,
                      outline=c if width else None, width=max(1, width))
        _paint(surf, (cx - r - 1, cy - r - 1, cx + r + 2, cy + r + 2), f)

    def ellipse(self, surf, color, rect, width=0):
        r = Rect(rect); c = _col(color)

        def f(d, ox, oy):
            if r.w <= 0 or r.h <= 0:
                return
            d.ellipse([r.x - ox, r.y - oy, r.x - ox + r.w - 1, r.y - oy + r.h - 1],
                      fill=c if width == 0 else None, outline=c if width else None, width=max(1, width))
        _paint(surf, (r.x - 1, r.y - 1, r.right + 1, r.bottom + 1), f)

    def line(self, surf, color, a, b, width=1):
        c = _col(color)
        xs = (a[0], b[0]); ys = (a[1], b[1])

        def f(d, ox, oy):
            d.line([a[0] - ox, a[1] - oy, b[0] - ox, b[1] - oy], fill=c, width=max(1, int(width)))
        _paint(surf, (min(xs) - width, min(ys) - width, max(xs) + width + 1, max(ys) + width + 1), f)

    def lines(self, surf, color, closed, pts, width=1):
        for i in range(len(pts) - 1):
            self.line(surf, color, pts[i], pts[i + 1], width)
        if closed:
            self.line(surf, color, pts[-1], pts[0], width)

    def polygon(self, surf, color, pts, width=0):
        c = _col(color); xs = [p[0] for p in pts]; ys = [p[1] for p in pts]

        def f(d, ox, oy):
            d.polygon([(p[0] - ox, p[1] - oy) for p in pts], fill=c if width == 0 else None,
                      outline=c if width else None)
        _paint(surf, (min(xs) - 1, min(ys) - 1, max(xs) + 2, max(ys) + 2), f)

    def arc(self, surf, color, rect, a0, a1, width=1):
        r = Rect(rect); c = _col(color)

        def f(d, ox, oy):
            d.arc([r.x - ox, r.y - oy, r.right - ox - 1, r.bottom - oy - 1], -math.degrees(a1), -math.degrees(a0),
                  fill=c, width=max(1, width))
        _paint(surf, (r.x - 2, r.y - 2, r.right + 2, r.bottom + 2), f)


draw = _Draw()


# ── Imagen / transform ───────────────────────────────────────────────────────
def _to_img(s): return Image.fromarray(np.ascontiguousarray(s.a), "RGBA")


def _from_img(im, flags):
    return Surface((1, 1), flags, arr=np.array(im.convert("RGBA"), dtype=np.uint8))


class _Image:
    def load(self, path):
        try:
            im = Image.open(path).convert("RGBA")
        except Exception as e:
            raise error(str(e))
        return _from_img(im, SRCALPHA)

    def save(self, surf, path):
        _to_img(surf).convert("RGB").save(path)


image = _Image()


class _Transform:
    def scale(self, s, size, dest=None):
        return _from_img(_to_img(s).resize((max(1, int(size[0])), max(1, int(size[1]))), Image.NEAREST), s.flags)

    def smoothscale(self, s, size, dest=None):
        return _from_img(_to_img(s).resize((max(1, int(size[0])), max(1, int(size[1]))), Image.BILINEAR), s.flags)

    def flip(self, s, fx, fy):
        a = s.a
        if fx: a = a[:, ::-1]
        if fy: a = a[::-1]
        return Surface((1, 1), s.flags, arr=np.ascontiguousarray(a).copy())

    def rotate(self, s, angle):
        return _from_img(_to_img(s).rotate(angle, expand=True, resample=Image.BILINEAR), s.flags)

    def rotozoom(self, s, angle, scale):
        im = _to_img(s)
        if scale != 1:
            im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
        return _from_img(im.rotate(angle, expand=True, resample=Image.BILINEAR), s.flags)


transform = _Transform()


# ── Fuentes ──────────────────────────────────────────────────────────────────
class _Font:
    def __init__(self, name, size):
        size = max(6, int(size * 0.82))
        try:
            self.f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except Exception:
            self.f = ImageFont.load_default(size)
        self.size_px = size

    def size(self, text):
        b = self.f.getbbox(text or " ")
        return (int(b[2]), int(self.f.getbbox("Ag")[3]) + 2)

    def get_height(self): return self.size(" ")[1]
    def get_linesize(self): return self.get_height() + 2

    def render(self, text, aa, color, bg=None):
        w, h = self.size(text)
        im = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((0, 0), text, font=self.f, fill=_col(color))
        return _from_img(im, SRCALPHA)


class _FontModule:
    Font = _Font
    def init(self): pass
    def get_init(self): return True
    def SysFont(self, name, size, bold=False, italic=False): return _Font(None, size)


font = _FontModule()


# ── Tiempo, entrada, eventos ─────────────────────────────────────────────────
class _Time:
    _ms = 0
    fixed_dt = 1000.0 / 60.0

    class Clock:
        def tick(self, fps=0):
            _Time._ms += _Time.fixed_dt
            return int(round(_Time.fixed_dt))
        def get_fps(self): return 60.0

    def get_ticks(self): return int(_Time._ms)
    def delay(self, ms): pass
    def wait(self, ms): pass


time = _Time()
time.Clock = _Time.Clock


class _Keys:
    def __init__(self, held): self.held = held
    def __getitem__(self, k): return k in self.held


class _Key:
    held = set()
    def get_pressed(self): return _Keys(_Key.held)
    def set_repeat(self, *a): pass
    def get_mods(self): return 0


class _Mouse:
    pos = (0, 0)
    buttons = (0, 0, 0)
    def get_pos(self): return _Mouse.pos
    def get_pressed(self, num_buttons=3): return _Mouse.buttons
    def set_visible(self, v): pass


class Event:
    def __init__(self, type, **kw):
        self.type = type
        self.__dict__.update(kw)


class _EventModule:
    queue = []
    Event = Event
    def get(self, *a):
        q = _EventModule.queue[:]; _EventModule.queue.clear(); return q
    def clear(self, *a): _EventModule.queue.clear()
    def post(self, e): _EventModule.queue.append(e)
    def pump(self): pass


key, mouse, event = _Key(), _Mouse(), _EventModule()


# ── Pantalla ─────────────────────────────────────────────────────────────────
class _Display:
    surface = None
    frames = 0
    caption = ""
    def set_mode(self, size, flags=0, depth=0, display=0, vsync=0):
        _Display.surface = Surface(size, 0); return _Display.surface
    def set_caption(self, *a): _Display.caption = a[0] if a else ""
    def set_icon(self, s): pass
    def flip(self): _Display.frames += 1
    def update(self, *a): _Display.frames += 1
    def get_surface(self): return _Display.surface
    def toggle_fullscreen(self): return 1
    def Info(self): return type("I", (), {"current_w": 1920, "current_h": 1080})()


display = _Display()


class _Mixer:
    def pre_init(self, *a, **k): pass
    def init(self, *a, **k): raise error("no audio device (shim)")
    def get_init(self): return None
    class Sound:
        def __init__(self, *a, **k): pass
        def play(self): pass
        def set_volume(self, v): pass


mixer = _Mixer()


def init(): return (6, 0)
def quit(): pass


# ── Utilidades de test ───────────────────────────────────────────────────────
def sim_key_down(k):
    _Key.held.add(k); event.queue.append(Event(KEYDOWN, key=k, unicode=""))
def sim_key_up(k):
    _Key.held.discard(k); event.queue.append(Event(KEYUP, key=k))
def sim_mouse(pos, buttons=(0, 0, 0)):
    buttons = tuple(buttons) + (0,) * (3 - len(buttons))
    _Mouse.pos = pos; _Mouse.buttons = buttons
def sim_click(pos, button=1):
    _Mouse.pos = pos
    event.queue.append(Event(MOUSEBUTTONDOWN, pos=pos, button=button))
    event.queue.append(Event(MOUSEBUTTONUP, pos=pos, button=button))
def screenshot(path):
    if _Display.surface is not None:
        image.save(_Display.surface, path)
