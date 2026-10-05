"""Menú principal, pausa, controles y pantalla de muerte."""
import math
import pygame
from .. import audio, settings as S
from . import widgets as W

CONTROLS = [
    ("W A S D", "Moverse"), ("Shift", "Correr (gasta energía)"), ("Espacio", "Esquivar con impulso"),
    ("Clic izq.", "Usar objeto: golpear, atacar, disparar, comer, colocar"),
    ("Clic der.", "Guardia con escudo equipado"),
    ("E", "Interactuar: cofres, mesas, camas, puertas, agua, cuevas"),
    ("1 - 8 / Rueda", "Elegir objeto de la barra rápida"),
    ("I / Tab", "Inventario y fabricación"), ("F", "Comer o beber lo que llevas en la mano"),
    ("Q", "Soltar el objeto en mano"), ("M", "Silenciar / activar sonido"),
    ("F3", "Datos de depuración"), ("F11", "Pantalla completa"), ("Esc", "Pausa"),
]
TIPS = ["Corta árboles con las manos para empezar; el hacha es mucho más rápida.",
        "Los no-muertos arden bajo el sol: refúgiate o pelea al amanecer.",
        "Las cuevas guardan hierro y oro, pero también más peligros. Lleva antorchas.",
        "Cocina la carne en un horno: la cruda te hace daño.",
        "Una cama te permite dormir la noche y fijar tu punto de reaparición.",
        "Un escudo reduce el 70 % del daño frontal si mantienes el clic derecho."]


class Title:
    def __init__(self, has_save, on_new, on_continue, on_quit, on_controls):
        cx = S.SCREEN_W // 2
        y = 330
        self.buttons = []
        if has_save:
            self.buttons.append(W.Button("Continuar", (cx - 150, y, 300, 52), on_continue))
            y += 64
        self.buttons.append(W.Button("Nueva partida", (cx - 150, y, 300, 52), on_new))
        y += 64
        self.buttons.append(W.Button("Controles", (cx - 150, y, 300, 52), on_controls))
        y += 64
        self.buttons.append(W.Button("Salir", (cx - 150, y, 300, 52), on_quit))
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        m = pygame.mouse.get_pos()
        for b in self.buttons:
            b.update(dt, m)

    def event(self, e):
        pos = None
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            pos = e.pos
        elif hasattr(pygame, "FINGERDOWN") and e.type == pygame.FINGERDOWN:
            pos = (int(e.x * S.SCREEN_W), int(e.y * S.SCREEN_H))
        if pos:
            for b in self.buttons:
                if b.click(pos):
                    audio.play("click")
                    return True
        if e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN:
            self.buttons[0].cb()
            return True
        return False

    def draw(self, surf):
        dim = pygame.Surface((S.SCREEN_W, S.SCREEN_H), pygame.SRCALPHA)
        dim.fill((6, 8, 18, 120))
        surf.blit(dim, (0, 0))
        cx = S.SCREEN_W // 2
        bob = math.sin(self.t * 1.6) * 4
        W.text(surf, "FAITH", (cx, 120 + bob), 128, (255, 226, 130), "midtop")
        W.text(surf, "OF SURVIVING", (cx, 232 + bob), 56, (236, 236, 244), "midtop")
        for b in self.buttons:
            b.draw(surf)
        tip = TIPS[int(self.t / 6) % len(TIPS)]
        W.text(surf, tip, (cx, S.SCREEN_H - 50), 24, S.C_DIM, "midbottom")
        W.text(surf, "v2.0", (S.SCREEN_W - 12, S.SCREEN_H - 10), 20, (90, 94, 120), "bottomright")


class Pause:
    def __init__(self, on_resume, on_save, on_controls, on_mute, on_title, on_touch=None, get_touch=None):
        cx = S.SCREEN_W // 2
        self.on_touch = on_touch
        self.get_touch = get_touch
        y = 210
        self.buttons = [
            W.Button("Continuar", (cx - 150, y, 300, 46), on_resume),
            W.Button("Guardar partida", (cx - 150, y + 52, 300, 46), on_save),
            W.Button("Controles", (cx - 150, y + 104, 300, 46), on_controls),
            W.Button("Táctil: sí", (cx - 150, y + 156, 300, 46), on_touch or (lambda: None)),
            W.Button("Sonido: sí", (cx - 150, y + 208, 300, 46), on_mute),
            W.Button("Guardar y salir al menú", (cx - 150, y + 260, 300, 46), on_title),
        ]
        self.touch_btn = self.buttons[3]
        self.mute_btn = self.buttons[4]

    def update(self, dt):
        if self.get_touch:
            self.touch_btn.label = f"Táctil: {'sí' if self.get_touch() else 'no'}"
        self.mute_btn.label = "Sonido: no" if audio.is_muted() else "Sonido: sí"
        m = pygame.mouse.get_pos()
        for b in self.buttons:
            b.update(dt, m)

    def event(self, e):
        pos = None
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            pos = e.pos
        elif hasattr(pygame, "FINGERDOWN") and e.type == pygame.FINGERDOWN:
            pos = (int(e.x * S.SCREEN_W), int(e.y * S.SCREEN_H))
        if pos:
            for b in self.buttons:
                if b.click(pos):
                    audio.play("click")
                    return True
        return False

    def draw(self, surf):
        dim = pygame.Surface((S.SCREEN_W, S.SCREEN_H), pygame.SRCALPHA)
        dim.fill((4, 6, 14, 170))
        surf.blit(dim, (0, 0))
        W.panel(surf, (S.SCREEN_W // 2 - 190, 145, 380, 395), 235, 16)
        W.text(surf, "Pausa", (S.SCREEN_W // 2, 158), 48, S.C_GOLD, "midtop")
        for b in self.buttons:
            b.draw(surf)


def draw_controls(surf):
    dim = pygame.Surface((S.SCREEN_W, S.SCREEN_H), pygame.SRCALPHA)
    dim.fill((4, 6, 14, 200))
    surf.blit(dim, (0, 0))
    w, h = 800, 56 + len(CONTROLS) * 36 + 60
    x, y = (S.SCREEN_W - w) // 2, (S.SCREEN_H - h) // 2
    W.panel(surf, (x, y, w, h), 240, 16)
    W.text(surf, "Controles", (S.SCREEN_W // 2, y + 14), 46, S.C_GOLD, "midtop")
    for i, (k, d) in enumerate(CONTROLS):
        yy = y + 66 + i * 36
        W.panel(surf, (x + 30, yy, 190, 28), 220, 7, (96, 100, 140), (30, 33, 50), shadow=False)
        W.text(surf, k, (x + 125, yy + 14), 22, S.C_GOLD, "center")
        W.text(surf, d, (x + 238, yy + 5), 23, S.C_TEXT)
    W.text(surf, "Pulsa cualquier tecla o haz clic para volver", (S.SCREEN_W // 2, y + h - 14), 22, S.C_DIM, "midbottom")


def draw_death(surf, player, day, t, grave_msg):
    a = min(1.0, t / 1.2)
    dim = pygame.Surface((S.SCREEN_W, S.SCREEN_H), pygame.SRCALPHA)
    dim.fill((40, 0, 0, int(190 * a)))
    surf.blit(dim, (0, 0))
    if a < 0.5:
        return
    k = min(1.0, (a - 0.5) * 2)
    s = W.render("HAS MUERTO", 108, (230, 60, 60)).copy()
    s.set_alpha(int(255 * k))
    surf.blit(s, (S.SCREEN_W // 2 - s.get_width() // 2, 180))
    if k > 0.9:
        W.text(surf, f"Sobreviviste hasta el día {day}", (S.SCREEN_W // 2, 310), 34, S.C_TEXT, "midtop")
        st = player.stats
        W.text(surf, f"Enemigos derrotados: {st['kills']}   ·   Recursos reunidos: {st['mined']}   ·   Objetos fabricados: {st['crafted']}",
               (S.SCREEN_W // 2, 358), 24, S.C_DIM, "midtop")
        if grave_msg:
            W.text(surf, grave_msg, (S.SCREEN_W // 2, 394), 24, S.C_GOLD, "midtop")
        if int(t * 2) % 2 == 0:
            W.text(surf, "Pulsa ENTER para reaparecer", (S.SCREEN_W // 2, 470), 34, S.C_GOLD, "midtop")
