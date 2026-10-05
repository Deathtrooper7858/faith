"""Prueba aleatoria: miles de fotogramas con teclas, clics y menús al azar (busca excepciones)."""
import os, sys, random, math, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests", "pygame_shim")); sys.path.insert(0, ROOT)
os.environ["FAITH_SAVE_DIR"] = "/tmp/faith_fuzz"
import pygame
from faith.game import Game
from faith import settings as S, items
from faith.world import terrain as T

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
frames_n = int(sys.argv[2]) if len(sys.argv) > 2 else 2500
rng = random.Random(seed)
g = Game()
g.new_game(seed=rng.randrange(10**6))
KEYS = [pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_LSHIFT]
ONESHOT = [pygame.K_e, pygame.K_f, pygame.K_q, pygame.K_i, pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_TAB,
           pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_F3, pygame.K_RETURN]
# dar de todo para ejercitar rutas
for it in ("wood", "stone", "plank", "stick", "iron-ingot", "gold-ingot", "coal", "meat", "fiber", "sand", "iron-ore"):
    g.player.inv.add(it, 40)
for it in ("iron-sword", "iron-pickaxe", "iron-axe", "stone-shovel", "bow", "arrow", "torch", "crafting-table", "oven",
           "chest", "bed", "door", "wood-wall", "fence", "bottle", "bwater", "cooked-meat", "shield", "iron-helmet"):
    g.player.inv.add(it, 5)
if os.environ.get("FUZZ_CAVE"):                      # empezar dentro de una cueva y sin teletransportes
    from faith.world.level import Cave
    g.enter_cave((5, 5)); 
    for _ in range(40): g.update(1 / 60)
errors = 0
for f in range(frames_n):
    try:
        if rng.random() < 0.06:
            k = rng.choice(KEYS)
            (pygame.sim_key_up if k in pygame.key.held else pygame.sim_key_down)(k)
        if rng.random() < 0.03:
            pygame.sim_key_down(rng.choice(ONESHOT)); 
        if rng.random() < 0.04:
            pygame.sim_mouse((rng.randrange(1280), rng.randrange(720)), (rng.random() < 0.5, 0, rng.random() < 0.15))
        if rng.random() < 0.02:
            pygame.sim_click((rng.randrange(1280), rng.randrange(720)), rng.choice((1, 3)))
        if rng.random() < 0.004:
            pygame.event.post(pygame.Event(pygame.MOUSEWHEEL, y=rng.choice((-1, 1)), x=0))
        if rng.random() < 0.002:
            g.elapsed += rng.uniform(0, 400)
        if rng.random() < 0.003 and g.player and not os.environ.get("FUZZ_CAVE"):
            g.player.teleport(g.player.x + rng.uniform(-3000, 3000), g.player.y + rng.uniform(-3000, 3000))
        for e in pygame.event.get():
            g.handle_event(e)
        # liberar teclas de un solo golpe
        for k in ONESHOT:
            pygame.key.held.discard(k)
        if g.state == "dead" and rng.random() < 0.1:
            g.death_t = 5; pygame.sim_key_down(pygame.K_RETURN)
        if g.state == "paused" and rng.random() < 0.2:
            pygame.sim_key_down(pygame.K_ESCAPE)
        if g.state == "title":
            g.new_game()
        g.update(1 / 60)
        if f % 8 == 0:
            g.draw(); pygame.display.flip()
    except Exception:
        errors += 1
        print("EXCEPCIÓN en fotograma", f, "estado", g.state)
        traceback.print_exc()
        if errors > 3: break
print("fuzz seed", seed, "frames", frames_n, "errores", errors, "mobs", len(g.level.mobs), "cueva", g.level.is_cave, "estado", g.state)
sys.exit(1 if errors else 0)
