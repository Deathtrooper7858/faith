import os, sys, time, math, random
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# estas pruebas usan los ayudantes sim_* del shim (siempre headless)
sys.path.insert(0, os.path.join(ROOT, "tests", "pygame_shim"))
sys.path.insert(0, ROOT)
os.environ["FAITH_SAVE_DIR"] = "/tmp/faith_save"
import pygame
from faith.game import Game
from faith import settings as S, items
from faith.world import terrain as T

g = Game()
def frames(n, dt=1/60):
    for _ in range(n):
        for e in pygame.event.get(): g.handle_event(e)
        g.update(dt); g.draw(); pygame.display.flip()
g.new_game(seed=1234); frames(5)
p = g.player; lv = g.level

# 1) cortar un árbol a mano
tree = min((o for o in lv.objects_near(p.x, p.y, 900) if o.kind == "tree" and not any(q is not o and math.hypot(q.x-o.x, q.y+0-(o.y+70)) < 110 or (q is not o and math.hypot(q.x-o.x,q.y-o.y)<110) for q in lv.objects_near(o.x, o.y, 160))), key=lambda o: math.hypot(o.x-p.x, o.y-p.y))
p.teleport(tree.x, tree.y + 70); p.inv.select(0); frames(60)
wood0 = p.inv.count("wood"); print('tree', tree.uid, tree.x, tree.y, 'held', p.inv.held(), 'sel', p.inv.selected)
for i in range(220):
    pygame.sim_mouse((int(tree.x - g.cam[0]), int(tree.y - 40 - g.cam[1])), (1, 0, 0))
    frames(4)
    if i % 40 == 0: print(i, tree.hp, 'swing', round(p.swing_t,2), 'cd', round(p.cd,2), 'state', g.state, 'ui', g.inv_ui.open, 'fade', g.fade_job, 'cc', getattr(g,'_click_consumed',None), p.inv.count('wood'), (p.x, p.y), pygame.mouse.get_pos(), pygame.mouse.get_pressed())
    if tree.uid in lv.removed: break
pygame.sim_mouse((640, 360), (0, 0)); frames(60)
print("madera tras talar:", p.inv.count("wood"), "árbol destruido:", tree.uid in lv.removed)
assert p.inv.count("wood") >= 2

# 2) fabricar herramientas
from faith import crafting
p.inv.add("wood", 20); p.inv.add("stone", 20); p.inv.add("fiber", 6); p.inv.add("coal", 6); p.inv.add("meat", 3)
rec = lambda res, st="hand": next(r for r in items.RECIPES if r.result == res and r.station == st)
for res, st in (("plank","hand"),("stick","hand"),("crafting-table","hand"),("wood-axe","hand"),("wood-pickaxe","hand"),("wood-sword","hand")):
    try: r = rec(res, st)
    except StopIteration: print("sin receta", res); continue
    print(res, crafting.craft(r, lv, p, 1, g))
p.inv.add("plank", 10)
print("inventario:", [(s.id, s.count) for s in p.inv.slots if s])

# 3) colocar mesa, usar horno
for i,s in enumerate(p.inv.slots):
    if s and s.id == "crafting-table": p.inv.select(i)
p.teleport(0, 0); p.fx, p.fy = 1, 0
pygame.sim_mouse((int(0 + 130 - g.cam[0]), int(0 - g.cam[1])), (1,0,0)); frames(3); pygame.sim_mouse((640,360),(0,0)); frames(2)
print("estructuras:", [(s.kind, s.tx, s.ty) for s in lv.structs.values()])

# 4) abrir inventario
g.inv_ui.show(g); frames(3); pygame.screenshot("/tmp/shot_inv.png")
g.inv_ui.close(g)

# 5) noche + enemigos
g.elapsed = (0.9 - S.START_TIME_FRAC) * S.DAY_LENGTH_MS / 1000.0
p.teleport(0, 0)
frames(1)
for i in range(1200):
    frames(1)
    if i % 300 == 0:
        print("t", i, "mobs", [(m.kind) for m in lv.mobs])
pygame.screenshot("/tmp/shot_night.png")
print("hostiles:", sum(m.hostile for m in lv.mobs), "animales:", sum(not m.hostile for m in lv.mobs))
print("OK scenario 1")
