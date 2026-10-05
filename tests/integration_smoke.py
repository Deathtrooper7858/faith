import os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# estas pruebas usan los ayudantes sim_* del shim (siempre headless)
sys.path.insert(0, os.path.join(ROOT, "tests", "pygame_shim"))
sys.path.insert(0, ROOT)
os.environ["FAITH_SAVE_DIR"] = "/tmp/faith_save"
import pygame
from faith.game import Game
from faith import settings as S

g = Game()
def frames(n, dt=1/60):
    for _ in range(n):
        for e in pygame.event.get(): g.handle_event(e)
        g.update(dt); g.draw(); pygame.display.flip()

t0 = time.time()
frames(3)
pygame.screenshot("/tmp/shot_title.png")
g.new_game(seed=1234)
frames(2)
print("new game ok", time.time() - t0)
pygame.screenshot("/tmp/shot_play0.png")
