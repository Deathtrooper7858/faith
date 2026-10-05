"""Pruebas unitarias para los controles táctiles de Android."""
import unittest
from faith.ui.touch_controls import TouchControls
from faith import settings as S


class FakePlayer:
    def __init__(self):
        self.x, self.y = 100, 100
        self.fx, self.fy = 1, 0
        self.dashed = False
        self.ate = False
        self.used = False

    def dash(self):
        self.dashed = True

    def eat_held(self):
        self.ate = True

    def use(self, level, wx, wy):
        self.used = True


class FakeInvUI:
    def __init__(self):
        self.open = False

    def show(self, game):
        self.open = True

    def close(self, game):
        self.open = False


class FakeGame:
    def __init__(self):
        self.state = "play"
        self.level = None
        self.fade_job = None
        self.player = FakePlayer()
        self.inv_ui = FakeInvUI()
        self.focus = None
        self.interacted = False

    def interact(self):
        self.interacted = True


class TestTouchControls(unittest.TestCase):
    def setUp(self):
        self.touch = TouchControls()
        self.touch.enabled = True
        self.game = FakeGame()

    def test_joystick_movement(self):
        jx, jy = self.touch.joy_center
        # Tocar a la derecha del joystick
        self.touch._on_touch_down(1, (jx + 50, jy), self.game)
        self.assertAlmostEqual(self.touch.move_vector[0], 1.0, delta=0.5)
        self.assertAlmostEqual(self.touch.move_vector[1], 0.0, delta=0.2)

        # Mover hacia arriba
        self.touch._on_touch_motion(1, (jx, jy - 70), self.game)
        self.assertAlmostEqual(self.touch.move_vector[1], -1.0, delta=0.2)

        # Soltar
        self.touch._on_touch_up(1, (jx, jy - 70), self.game)
        self.assertEqual(self.touch.move_vector, [0.0, 0.0])
        self.assertEqual(self.touch.knob_pos, list(self.touch.joy_center))

    def test_action_buttons(self):
        # Botón dash
        dash_btn = next(b for b in self.touch.buttons if b["id"] == "dash")
        self.touch._on_touch_down(2, dash_btn["pos"], self.game)
        self.assertTrue(self.game.player.dashed)

        # Botón inventario
        inv_btn = next(b for b in self.touch.buttons if b["id"] == "inv")
        self.touch._on_touch_down(3, inv_btn["pos"], self.game)
        self.assertTrue(self.game.inv_ui.open)

        # Botón comer
        eat_btn = next(b for b in self.touch.buttons if b["id"] == "eat")
        self.touch._on_touch_down(4, eat_btn["pos"], self.game)
        self.assertTrue(self.game.player.ate)

        # Botón interactuar
        interact_btn = next(b for b in self.touch.buttons if b["id"] == "interact")
        self.touch._on_touch_down(5, interact_btn["pos"], self.game)
        self.assertTrue(self.game.interacted)


if __name__ == "__main__":
    unittest.main()
