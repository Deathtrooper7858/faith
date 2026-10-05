import os, sys, math, random, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# estas pruebas usan los ayudantes sim_* del shim (siempre headless)
sys.path.insert(0, os.path.join(ROOT, "tests", "pygame_shim"))
sys.path.insert(0, ROOT)
os.environ["FAITH_SAVE_DIR"] = "/tmp/faith_save2"
import pygame
from faith.game import Game
from faith import settings as S, items, crafting, save
from faith.world import terrain as T
from faith.entities import mobs as M
from faith.inventory import ItemStack
save.delete()
g = Game()
def frames(n, dt=1/60):
    for _ in range(n):
        for e in pygame.event.get(): g.handle_event(e)
        g.update(dt); g.draw(); pygame.display.flip()
g.new_game(seed=777); frames(5)
p, lv = g.player, g.level
ok = lambda c, m: print(("PASS " if c else "FAIL ") + m)

# --- colocación de estructuras
p.inv.add("crafting-table", 1); p.inv.add("chest", 1); p.inv.add("door", 1); p.inv.add("torch", 4); p.inv.add("bed", 1); p.inv.add("oven", 1)
p.teleport(0, 0); frames(40)
def place(item, dx, dy):
    for i, s in enumerate(p.inv.slots):
        if s and s.id == item: p.inv.select(i); break
    wx, wy = p.x + dx * 64, p.y + dy * 64
    pygame.sim_mouse((int(wx - g.cam[0]), int(wy - g.cam[1])), (1, 0, 0)); frames(3)
    pygame.sim_mouse((640, 360), (0, 0)); frames(20)
place("crafting-table", 2, -1); place("chest", 2, 1); place("oven", 0, -2); place("bed", -2, 1); place("torch", -2, -1); place("door", 1, 2)
ok(len(lv.structs) == 6, f"6 estructuras colocadas ({[s.kind for s in lv.structs.values()]})")

# --- interacción: cofre y mesa
chest = next(s for s in lv.structs.values() if s.kind == "chest")
chest.items[0] = ItemStack("wood", 12)
p.teleport((chest.tx + 1.9) * 64, chest.ty * 64 + 60); frames(30)
ok(g.focus and g.focus[1] is chest, f"foco en el cofre: {g.focus_text}")
g.interact(); frames(2)
ok(g.inv_ui.open and g.inv_ui.chest is chest, "cofre abierto")
# shift+clic mueve de cofre a mochila
pygame.key.held.add(pygame.K_LSHIFT)
r = next(r for r, k, i in g.inv_ui.slots if k == "chest" and i == 0)
before = p.inv.count("wood")
pygame.sim_click(r.center); frames(2)
pygame.key.held.discard(pygame.K_LSHIFT)
ok(p.inv.count("wood") == before + 12, "shift+clic mueve del cofre a la mochila")
pygame.screenshot("/tmp/shot_chest.png")
g.inv_ui.close(g); frames(2)

# --- crafteo con mesa cercana
table = next(s for s in lv.structs.values() if s.kind == "crafting_table")
p.teleport(table.tx * 64 + 32, table.ty * 64 + 110); frames(5)
p.inv.add("iron-ingot", 5); p.inv.add("stick", 5)
r_ = next(r for r in items.RECIPES if r.result == "iron-pickaxe")
ok(crafting.can_craft(r_, lv, p), "puede fabricar pico de hierro junto a la mesa")
p.teleport(600, 600); frames(3)
ok(not crafting.can_craft(r_, lv, p), "no puede fabricar lejos de la mesa")

# --- puerta
door = next(s for s in lv.structs.values() if s.kind == "door")
ok(door.solid, "puerta cerrada es sólida")
p.teleport(door.tx * 64 + 32, door.ty * 64 + 110); frames(10); g.compute_focus(); g.interact(); frames(2)
ok(door.open and not door.solid, "puerta abierta es atravesable")

# --- combate
p.teleport(0, 0); p.hp = 100; frames(5)
sk = M.spawn(lv, "skeleton", 150, 0)
for i, s in enumerate(p.inv.slots): pass
p.inv.add("iron-sword", 1)
for i, s in enumerate(p.inv.slots):
    if s and s.id == "iron-sword": p.inv.select(i)
hp0 = p.hp
for i in range(180):
    pygame.sim_mouse((int(sk.x - g.cam[0]), int(sk.y - 24 - g.cam[1])), (1, 0, 0)); frames(1)
    if sk.dying: break
pygame.sim_mouse((640, 360), (0, 0))
ok(sk.dying or sk.hp < sk.max_hp, f"el esqueleto recibió daño (hp {sk.hp:.0f}/{sk.max_hp:.0f}), jugador hp {p.hp:.0f}")
pygame.screenshot("/tmp/shot_combat.png")

# --- arco
p.inv.add("bow", 1); p.inv.add("arrow", 10)
for i, s in enumerate(p.inv.slots):
    if s and s.id == "bow": p.inv.select(i)
ar = M.spawn(lv, "bones", 300, 0); ar.cd = 99
a0 = p.inv.count("arrow")
for i in range(60):
    pygame.sim_mouse((int(ar.x - g.cam[0]), int(ar.y - 24 - g.cam[1])), (1, 0, 0)); frames(1)
pygame.sim_mouse((640, 360), (0, 0)); frames(30)
ok(p.inv.count("arrow") < a0 and ar.hp < ar.max_hp, f"el arco disparó y dañó (flechas {a0}->{p.inv.count('arrow')}, hp {ar.hp:.0f})")

# --- cueva
doors = []
for cx in range(-6, 7):
    for cy in range(-6, 7):
        ch = lv.get_chunk(cx, cy)
        doors += [o for o in ch.objects if o.kind == "cavedoor"]
print("entradas de cueva cercanas:", len(doors))
if doors:
    d = min(doors, key=lambda o: math.hypot(o.x, o.y))
    p.teleport(d.x, d.y + 70); p.fx, p.fy = 0, -1; frames(40)
    g.compute_focus(); print("foco:", g.focus_text)
    g.interact(); frames(40)
    ok(g.level.is_cave, "dentro de la cueva")
    frames(60); pygame.screenshot("/tmp/shot_cave.png")
    ok(len(g.level.mobs) > 3, f"cueva poblada ({len(g.level.mobs)} criaturas)")
    # minar mineral
    ore = next(o for ch in g.level.chunks.values() for o in ch.objects if o.kind.startswith("ore_"))
    g.level.removed.add(ore.uid); g.level.remove_object(ore)
    cave = g.level
    # salir
    ex = next(o for ch in g.level.chunks.values() for o in ch.objects if o.uid == "cave-exit")
    p.teleport(ex.x, ex.y + 40); frames(10); g.compute_focus(); g.interact(); frames(40)
    ok(not g.level.is_cave, "de vuelta en la superficie")

# --- guardado / carga
p.inv.add("gold-ingot", 7); p.hp = 77; p.teleport(123, 45); lv = g.level
n_struct = len(lv.structs); removed = len(lv.removed)
g.save_game(silent=True)
ok(save.exists(), "archivo de guardado creado")
g2 = Game(); g2.continue_game(); frames(1)
ok(g2.seed == 777 and g2.player.inv.count("gold-ingot") == 7 and abs(g2.player.hp - 77) < 1, "carga restaura semilla, inventario y vida")
ok(len(g2.overworld.structs) == n_struct and len(g2.overworld.removed) == removed, "carga restaura estructuras y objetos recogidos")
ok(len(g2.caves) == len(g.caves), "carga restaura cuevas")

# --- muerte y reaparición con tumba
g = g2; p, lv = g.player, g.level
p.teleport(300, 300); frames(30)
p.inv.add("iron-sword", 1)
n_items = sum(1 for s in p.inv.slots if s)
p.hurt(500, 0, lv)
frames(5)
ok(g.state == "dead", "estado de muerte")
frames(150)
pygame.screenshot("/tmp/shot_dead.png")
chest = [s for s in lv.structs.values() if s.kind == "chest" and any(s.items)]
ok(len(chest) >= 1, "tumba con objetos creada")
ok(all(s is None for s in p.inv.slots), "inventario vaciado al morir")
g.respawn(); frames(5)
ok(g.state == "play" and not p.dead and p.hp == 100, "reaparición correcta")
print("ALL DONE")
