"""Controles táctiles en pantalla para móviles (Android / Touchscreens).
Soporta multi-touch nativo con FINGERDOWN/UP/MOTION y ratón para pruebas."""
import math
import os
import sys
import pygame
from .. import settings as S, audio
from . import widgets as W

IS_ANDROID = (
    sys.platform == "android"
    or "ANDROID_ARGUMENT" in os.environ
    or "ANDROID_ENTRYPOINT" in os.environ
    or hasattr(sys, "getandroidapilevel")
)


class TouchControls:
    def __init__(self):
        # Activado por defecto en Android o si se activa manualmente
        self.enabled = IS_ANDROID
        self.visible = True
        
        # Joystick analógico virtual
        self.joy_center = (140, S.SCREEN_H - 140)
        self.joy_radius = 76
        self.knob_radius = 34
        self.knob_pos = list(self.joy_center)
        self.joy_finger = None
        self.move_vector = [0.0, 0.0]
        self.is_running = False

        # Dedos activos: finger_id -> {"btn": str or None, "pos": (x, y)}
        self.touches = {}

        # Botones de acción (centro_x, centro_y, radio, id, label)
        self.buttons = [
            {"id": "attack", "pos": (S.SCREEN_W - 120, S.SCREEN_H - 120), "r": 48, "label": "ATACAR", "color": (210, 80, 80)},
            {"id": "interact", "pos": (S.SCREEN_W - 225, S.SCREEN_H - 120), "r": 38, "label": "USAR [E]", "color": (90, 160, 230)},
            {"id": "dash", "pos": (S.SCREEN_W - 105, S.SCREEN_H - 240), "r": 36, "label": "ESQUIVA", "color": (220, 180, 70)},
            {"id": "eat", "pos": (S.SCREEN_W - 215, S.SCREEN_H - 225), "r": 32, "label": "COMER", "color": (100, 190, 120)},
            {"id": "inv", "pos": (S.SCREEN_W - 65, 45), "r": 30, "label": "MOCHILA", "color": (160, 130, 200)},
            {"id": "pause", "pos": (50, 45), "r": 26, "label": "PAUSA", "color": (130, 140, 160)},
        ]
        
        # Botones presionados actualmente
        self.pressed = set()
        self.attack_held = False

    def handle_event(self, e, game):
        # Auto-activar si se detecta cualquier toque en pantalla
        if not self.enabled and hasattr(pygame, "FINGERDOWN") and e.type == pygame.FINGERDOWN:
            self.enabled = True

        if not self.enabled:
            return False

        # Si el inventario está abierto o juego en pausa, no capturar controles de movimiento
        if game.state != "play" or game.inv_ui.open:
            if hasattr(pygame, "FINGERDOWN") and e.type == pygame.FINGERDOWN:
                # Permitir que el botón de pausa o toque general responda si aplica
                pass
            return False

        # Eventos Multi-Touch nativos
        if hasattr(pygame, "FINGERDOWN") and e.type == pygame.FINGERDOWN:
            pos = (int(e.x * S.SCREEN_W), int(e.y * S.SCREEN_H))
            return self._on_touch_down(e.finger_id, pos, game)
        elif hasattr(pygame, "FINGERMOTION") and e.type == pygame.FINGERMOTION:
            pos = (int(e.x * S.SCREEN_W), int(e.y * S.SCREEN_H))
            return self._on_touch_motion(e.finger_id, pos, game)
        elif hasattr(pygame, "FINGERUP") and e.type == pygame.FINGERUP:
            pos = (int(e.x * S.SCREEN_W), int(e.y * S.SCREEN_H))
            return self._on_touch_up(e.finger_id, pos, game)

        # Emulación con ratón (para pruebas en PC)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self._on_touch_down("mouse", e.pos, game):
                return True
        elif e.type == pygame.MOUSEMOTION and "mouse" in self.touches:
            if self._on_touch_motion("mouse", e.pos, game):
                return True
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1 and "mouse" in self.touches:
            if self._on_touch_up("mouse", e.pos, game):
                return True

        return False

    def _on_touch_down(self, fid, pos, game):
        # 1. Comprobar botones de acción
        for btn in self.buttons:
            bx, by = btn["pos"]
            if math.hypot(pos[0] - bx, pos[1] - by) <= btn["r"] + 8:
                self.touches[fid] = {"type": "btn", "id": btn["id"]}
                self.pressed.add(btn["id"])
                self._trigger_button(btn["id"], game)
                return True

        # 2. Comprobar área izquierda para Joystick
        jx, jy = self.joy_center
        # Permitir tocar dentro del círculo o en la zona inferior izquierda de la pantalla
        if pos[0] < S.SCREEN_W * 0.40 and pos[1] > S.SCREEN_H * 0.40:
            self.joy_finger = fid
            self.touches[fid] = {"type": "joy"}
            self._update_joystick(pos)
            return True

        return False

    def _on_touch_motion(self, fid, pos, game):
        if fid == self.joy_finger:
            self._update_joystick(pos)
            return True
        return False

    def _on_touch_up(self, fid, pos, game):
        if fid == self.joy_finger:
            self.joy_finger = None
            self.move_vector = [0.0, 0.0]
            self.knob_pos = list(self.joy_center)
            self.is_running = False
            self.touches.pop(fid, None)
            return True

        t = self.touches.pop(fid, None)
        if t and t.get("type") == "btn":
            bid = t.get("id")
            self.pressed.discard(bid)
            if bid == "attack":
                self.attack_held = False
            return True

        return False

    def _update_joystick(self, pos):
        jx, jy = self.joy_center
        dx = pos[0] - jx
        dy = pos[1] - jy
        dist = math.hypot(dx, dy)
        if dist > 0:
            nx = dx / dist
            ny = dy / dist
        else:
            nx, ny = 0.0, 0.0

        # Limitar desplazamiento del knob
        clamped_dist = min(dist, self.joy_radius)
        self.knob_pos = [jx + nx * clamped_dist, jy + ny * clamped_dist]

        # Vector normalizado con zona muerta
        deadzone = 12.0
        if dist > deadzone:
            factor = min(1.0, (dist - deadzone) / (self.joy_radius - deadzone))
            self.move_vector = [nx * factor, ny * factor]
            # Si se estira a más del 80 %, corre automáticamente
            self.is_running = factor > 0.82
        else:
            self.move_vector = [0.0, 0.0]
            self.is_running = False

    def _trigger_button(self, bid, game):
        p = game.player
        if not p:
            return
        if bid == "attack":
            self.attack_held = True
            # Usar objeto hacia donde mira el jugador
            wx = p.x + p.fx * 50
            wy = p.y - 14 + p.fy * 50
            p.use(game.level, wx, wy)
        elif bid == "interact":
            game.interact()
        elif bid == "dash":
            p.dash()
        elif bid == "eat":
            p.eat_held()
        elif bid == "inv":
            if game.inv_ui.open:
                game.inv_ui.close(game)
            else:
                game.inv_ui.show(game)
        elif bid == "pause":
            game.state = "paused"

    def update(self, dt, game):
        if not self.enabled or game.state != "play" or game.inv_ui.open:
            return

        # Si el botón de ataque sigue presionado, mantener uso continuo
        if "attack" in self.pressed or self.attack_held:
            p = game.player
            if p and not game.inv_ui.open and not game.fade_job:
                wx = p.x + p.fx * 50
                wy = p.y - 14 + p.fy * 50
                p.use(game.level, wx, wy)

    def draw(self, surf, game):
        if not self.enabled or not self.visible:
            return
        if game.state != "play" or game.inv_ui.open:
            return

        # ── 1. Dibujar Joystick ──────────────────────────────────────────
        jx, jy = self.joy_center
        # Base exterior
        base_surf = pygame.Surface((self.joy_radius * 2 + 10, self.joy_radius * 2 + 10), pygame.SRCALPHA)
        pygame.draw.circle(base_surf, (20, 24, 38, 120), (self.joy_radius + 5, self.joy_radius + 5), self.joy_radius)
        pygame.draw.circle(base_surf, (80, 90, 130, 180), (self.joy_radius + 5, self.joy_radius + 5), self.joy_radius, 3)
        # Línea directriz
        if self.joy_finger:
            kx, ky = self.knob_pos
            pygame.draw.line(base_surf, (255, 214, 92, 160), 
                             (self.joy_radius + 5, self.joy_radius + 5),
                             (int(kx - jx + self.joy_radius + 5), int(ky - jy + self.joy_radius + 5)), 2)
        surf.blit(base_surf, (jx - self.joy_radius - 5, jy - self.joy_radius - 5))

        # Knob central
        kx, ky = int(self.knob_pos[0]), int(self.knob_pos[1])
        knob_color = (255, 214, 92, 220) if self.joy_finger else (140, 150, 180, 160)
        knob_surf = pygame.Surface((self.knob_radius * 2 + 6, self.knob_radius * 2 + 6), pygame.SRCALPHA)
        pygame.draw.circle(knob_surf, knob_color, (self.knob_radius + 3, self.knob_radius + 3), self.knob_radius)
        pygame.draw.circle(knob_surf, (255, 255, 255, 200), (self.knob_radius + 3, self.knob_radius + 3), self.knob_radius, 2)
        surf.blit(knob_surf, (kx - self.knob_radius - 3, ky - self.knob_radius - 3))

        # Indicador de sprint si está activo
        if self.is_running:
            W.text(surf, "CORRIENDO", (jx, jy - self.joy_radius - 16), 18, (255, 214, 92), "center")

        # ── 2. Dibujar Botones de Acción ────────────────────────────────
        for btn in self.buttons:
            bid = btn["id"]
            bx, by = btn["pos"]
            br = btn["r"]
            is_down = bid in self.pressed

            # Si es botón de interacción y hay objeto cerca, resaltarlo
            col = btn["color"]
            if bid == "interact" and game.focus:
                col = (60, 230, 120)
                br = int(br * 1.1)

            btn_surf = pygame.Surface((br * 2 + 8, br * 2 + 8), pygame.SRCALPHA)
            fill_a = 210 if is_down else 135
            fill_col = (*col[:3], fill_a)
            edge_col = (255, 255, 255, 230) if is_down else (*col[:3], 210)

            pygame.draw.circle(btn_surf, fill_col, (br + 4, br + 4), br)
            pygame.draw.circle(btn_surf, edge_col, (br + 4, br + 4), br, 3 if is_down else 2)
            surf.blit(btn_surf, (bx - br - 4, by - br - 4))

            # Texto del botón
            txt_col = S.C_TEXT if not is_down else (255, 255, 255)
            font_size = 18 if len(btn["label"]) > 6 else 20
            W.text(surf, btn["label"], (bx, by), font_size, txt_col, "center")
