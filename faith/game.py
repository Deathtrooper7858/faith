"""Bucle principal y máquina de estados del juego."""
import math
import random
import sys
import pygame

from . import assets, audio, items, save, settings as S
from .entities import mobs as M
from .entities.drops import scatter
from .entities.player import Player
from .fx import lighting
from .inventory import ItemStack
from .ui import menus, widgets as W
from .ui.hud import HUD, hotbar_rect
from .ui.inventory_ui import InventoryUI
from .ui.touch_controls import TouchControls, IS_ANDROID
from .world import terrain as T
from .world.level import Overworld, Cave
from .world.objects import roll_loot

TS = S.TILE


class Game:
    def __init__(self, screen=None, headless=False):
        pygame.init()
        self.headless = headless
        flags = pygame.SCALED | pygame.RESIZABLE
        self.screen = screen or pygame.display.set_mode((S.SCREEN_W, S.SCREEN_H), flags)
        pygame.display.set_caption(S.TITLE)
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()
        audio.init()
        items.build_special_icons()
        self.lighting = lighting.Lighting()
        self.weather = lighting.Weather()
        self.hud = HUD()
        self.inv_ui = InventoryUI()
        self.touch = TouchControls()
        self.state = "title"
        self.running = True
        self.debug = False
        self.show_controls = False
        self.seed = 0
        self.level = None
        self.overworld = None
        self.caves = {}
        self.player = None
        self.elapsed = 0.0
        self.focus = None
        self.focus_text = ""
        self.cam = [0.0, 0.0]
        self.shake_amt = 0.0
        self.flash_col = None
        self.flash_a = 0.0
        self.fade = 0.0
        self.fade_job = None
        self._fade_surface = pygame.Surface((S.SCREEN_W, S.SCREEN_H))
        self._flash_surface = pygame.Surface((S.SCREEN_W, S.SCREEN_H), pygame.SRCALPHA)
        self.autosave_t = S.AUTOSAVE_SECONDS
        self.death_t = 0.0
        self.grave_msg = ""
        self.was_night = False
        self.last_day = 1
        self.fps = 60.0
        self.sleeping = 0.0
        # menús
        self.bg_level = Overworld(20240607)
        self.bg_t = 0.0
        self.title = None
        self._build_menus()
        self.pause_menu = menus.Pause(self.resume, self.save_game, lambda: setattr(self, "show_controls", True),
                                      audio.toggle_mute, self.to_title, self.toggle_touch, lambda: self.touch.enabled)

    def toggle_touch(self):
        self.touch.enabled = not self.touch.enabled
        self.touch.visible = self.touch.enabled

    # ══ menús / estados ══════════════════════════════════════════════════
    def _build_menus(self):
        self.title = menus.Title(save.exists(), self.new_game, self.continue_game, self.quit,
                                 lambda: setattr(self, "show_controls", True))

    def quit(self):
        if self.state in ("play", "paused", "dead") and self.player:
            self.save_game(silent=True)
        self.running = False

    def resume(self):
        self.state = "play"

    def to_title(self):
        self.save_game(silent=True)
        self.state = "title"
        self._build_menus()

    # ══ partida ══════════════════════════════════════════════════════════
    def new_game(self, seed=None):
        self.seed = seed if seed is not None else random.randrange(1, 10 ** 9)
        self.overworld = Overworld(self.seed)
        self.caves = {}
        self.level = self.overworld
        self.player = Player(self)
        self.player.teleport(0, 0)
        self.player.inv.slots[1] = ItemStack("apple", 3)      # la mano (ranura 1) queda libre para recolectar
        self.elapsed = 0.0
        self.weather = lighting.Weather(self.seed)
        self._after_load()
        self.hud.show_banner("Día 1", "Reúne madera con las manos. Pulsa I para ver recetas.", 5.0)
        self.grave_msg = ""

    def _after_load(self):
        self.state = "play"
        self.focus = None
        self.player.inv.cursor = None
        self.level.ensure(self.player.x, self.player.y, 2, budget=25)
        self.cam = [self.player.x - S.SCREEN_W / 2, self.player.y - 24 - S.SCREEN_H / 2]
        self.hud.minimap.reset(self.level, (int(self.player.x // TS), int(self.player.y // TS)))
        self.last_day = self.day
        self.autosave_t = S.AUTOSAVE_SECONDS
        self.was_night = self.level_darkness() > 110

    def continue_game(self):
        d = save.read()
        if not d:
            self.new_game()
            return
        try:
            self._load(d)
        except Exception as ex:                       # partida corrupta: no tirar el juego
            print("No se pudo cargar la partida:", ex, file=sys.stderr)
            self.new_game()

    def _load(self, d):
        from .world.structures import Structure
        self.seed = d["seed"]
        self.overworld = Overworld(self.seed)
        self.overworld.removed = set(d.get("removed", []))
        for sd in d.get("structs", []):
            st = Structure.from_json(sd)
            if st:
                self.overworld.structs[(st.tx, st.ty)] = st
        self.caves = {}
        for key, cd in d.get("caves", {}).items():
            tx, ty = map(int, key.split(","))
            cave = self._make_cave((tx, ty))
            cave.removed = set(cd.get("removed", []))
            for sd in cd.get("structs", []):
                st = Structure.from_json(sd)
                if st:
                    cave.structs[(st.tx, st.ty)] = st
            cave.populated = bool(cd.get("populated", False))
        self.elapsed = d.get("elapsed", 0.0)
        self.player = Player(self)
        self.player.load_json(d["player"])
        self.level = self.overworld
        loc = d.get("level")
        if loc:
            key = tuple(loc)
            self.level = self.caves.get(key) or self._make_cave(key)
        self.weather = lighting.Weather(self.seed)
        self._after_load()
        self.hud.show_banner(f"Día {self.day}", "Partida cargada", 2.5)

    def _make_cave(self, door_tile):
        seed = (self.seed * 31 + door_tile[0] * 7919 + door_tile[1] * 104729) & 0x7FFFFFFF
        cave = Cave(seed, door_tile)
        self.caves[door_tile] = cave
        return cave

    def save_game(self, silent=False):
        if not self.player or self.player.dead:
            return
        try:
            caves = {}
            for k, c in self.caves.items():
                caves[f"{k[0]},{k[1]}"] = {"removed": sorted(c.removed), "populated": c.populated,
                                           "structs": [s.to_json() for s in c.structs.values()]}
            loc = list(self.level.door_tile) if self.level.is_cave else None
            save.write({"seed": self.seed, "elapsed": self.elapsed, "player": self.player.to_json(),
                        "removed": sorted(self.overworld.removed),
                        "structs": [s.to_json() for s in self.overworld.structs.values()],
                        "caves": caves, "level": loc})
            if not silent:
                self.notify("Partida guardada", S.C_GOOD)
        except OSError as ex:
            print("Error al guardar:", ex, file=sys.stderr)
            if not silent:
                self.notify("No se pudo guardar", S.C_BAD)

    # ══ tiempo ═══════════════════════════════════════════════════════════
    @property
    def time_frac(self):
        return (S.START_TIME_FRAC + self.elapsed * 1000.0 / S.DAY_LENGTH_MS) % 1.0

    @property
    def day(self):
        return int(S.START_TIME_FRAC + self.elapsed * 1000.0 / S.DAY_LENGTH_MS) + 1

    @property
    def ui_open(self):
        return self.inv_ui.open

    def level_darkness(self):
        if self.level and self.level.is_cave:
            return S.CAVE_DARK
        return lighting.ambient(self.time_frac)[1] + self.weather.intensity * 26

    # ══ callbacks para otras clases ══════════════════════════════════════
    def notify(self, text, color=S.C_TEXT):
        self.hud.toasts.add(text, color)

    def toast_item(self, item_id, n):
        self.hud.toasts.add(items.ITEMS[item_id].name, S.C_TEXT, item_id, key=item_id, n=n)

    def shake(self, amount):
        self.shake_amt = min(14.0, max(self.shake_amt, amount))

    def flash_screen(self, color, alpha):
        self.flash_col, self.flash_a = color, alpha

    def on_player_death(self, level):
        self.state = "dead"
        self.death_t = 0.0
        self.inv_ui.open = False
        p = self.player
        # tumba: un cofre con las pertenencias
        stacks = [s for s in p.inv.slots if s] + [s for s in p.inv.armor.values() if s]
        self.grave_msg = ""
        if stacks:
            tx0, ty0 = int(p.x // TS), int((p.y - 8) // TS)
            spot = None
            for r in range(0, 6):
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        if max(abs(dx), abs(dy)) == r and level.can_place("chest", tx0 + dx, ty0 + dy):
                            spot = (tx0 + dx, ty0 + dy)
                            break
                    if spot:
                        break
                if spot:
                    break
            if spot:
                chest = level.add_structure("chest", *spot)
                it = iter(stacks)
                for i in range(len(chest.items)):
                    st = next(it, None)
                    if st is None:
                        break
                    chest.items[i] = st
                for st in it:
                    scatter(level, (spot[0] + 0.5) * TS, (spot[1] + 0.5) * TS, st.id, st.count, 80, st.dur)
                self.grave_msg = "Tus objetos quedaron en un cofre donde caíste"
            else:
                for st in stacks:
                    scatter(level, p.x, p.y, st.id, st.count, 80, st.dur)
                self.grave_msg = "Tus objetos quedaron en el suelo donde caíste"
            p.inv.slots = [None] * len(p.inv.slots)
            p.inv.armor = {k: None for k in p.inv.armor}
            p.inv.cursor = None

    def respawn(self):
        p = self.player
        p.respawn()
        self.level = self.overworld
        sp = p.spawn_point
        if sp and (int(sp[0]), int(sp[1])) in self.overworld.structs:
            p.teleport((sp[0] + 0.5) * TS, (sp[1] + 1.5) * TS)
        else:
            p.teleport(0, 0)
        self.level.ensure(p.x, p.y, 2, budget=25)
        self.cam = [p.x - S.SCREEN_W / 2, p.y - 24 - S.SCREEN_H / 2]
        self.hud.minimap.reset(self.level, (int(p.x // TS), int(p.y // TS)))
        self.state = "play"
        self.hud.show_banner("De vuelta", "Recupera tus cosas… si puedes", 3.0)
        self.save_game(silent=True)

    # ══ transiciones ═════════════════════════════════════════════════════
    def transition(self, job):
        if self.fade_job is None:
            self.fade_job = [job, 0.0, 0]          # [función, tiempo, fase]

    def _update_fade(self, dt):
        if self.fade_job is None:
            return
        job = self.fade_job
        job[1] += dt
        if job[2] == 0:
            self.fade = min(1.0, job[1] / 0.25)
            if job[1] >= 0.25:
                job[0]()
                job[2], job[1] = 1, 0.0
        else:
            self.fade = max(0.0, 1.0 - job[1] / 0.3)
            if job[1] >= 0.3:
                self.fade, self.fade_job = 0.0, None

    def enter_cave(self, door_tile):
        def job():
            cave = self.caves.get(door_tile) or self._make_cave(door_tile)
            self.level = cave
            cave.populate(self.day)
            x, y = cave.spawn_pos
            self.player.teleport(x, y + 10)
            cave.ensure(x, y, 2, budget=25)
            self.cam = [x - S.SCREEN_W / 2, y - S.SCREEN_H / 2]
            self.hud.minimap.reset(cave, (int(x // TS), int(y // TS)))
            self.hud.show_banner("La cueva", "Cuidado con la oscuridad", 2.2)
            audio.play("door")
        self.transition(job)

    def leave_cave(self):
        def job():
            door = self.level.door_tile
            self.level = self.overworld
            self.player.teleport((door[0] + 0.5) * TS, (door[1] + 1) * TS + 30)
            self.level.ensure(self.player.x, self.player.y, 2, budget=25)
            self.cam = [self.player.x - S.SCREEN_W / 2, self.player.y - 24 - S.SCREEN_H / 2]
            self.hud.minimap.reset(self.level, (int(self.player.x // TS), int(self.player.y // TS)))
            audio.play("door")
        self.transition(job)

    # ══ interacción ══════════════════════════════════════════════════════
    def compute_focus(self):
        p = self.player
        best, bd = None, 1e9
        px, py = p.x, p.y - 14
        for st in self.level.structs_near(px, py, 96):
            if st.interactive:
                cx, cy = st.center()
                d = math.hypot(cx - px, cy - py) - 8
                if d < bd:
                    best, bd = ("struct", st), d
        for o in self.level.objects_near(px, py, 120):
            if o.interactive:
                d = math.hypot(o.x - px, o.y - 20 - py)
                lim = 100 if o.kind == "cavedoor" else 84
                if d < lim and d < bd:
                    best, bd = ("object", o), d
        if best is None or bd > 56:
            wx, wy = p.x + p.fx * 44, p.y - 6 + p.fy * 44
            if self.level.tile(int(wx // TS), int(wy // TS)) in T.WATER and bd > 40:
                best = ("water", None)
        self.focus = best
        self.focus_text = self._focus_label(best)

    def _focus_label(self, f):
        if not f:
            return ""
        kind, o = f
        if kind == "water":
            h = self.player.inv.held()
            return "[E] Llenar botella" if h and h.id == "bottle" else "[E] Beber agua"
        if kind == "struct":
            return {"crafting_table": "[E] Usar mesa de crafteo", "oven": "[E] Usar horno", "chest": "[E] Abrir cofre",
                    "bed": "[E] Dormir" if self.level_darkness() > 100 else "[E] Fijar reaparición aquí",
                    "door": "[E] Cerrar puerta" if o.open else "[E] Abrir puerta"}.get(o.kind, "[E] Usar")
        if o.kind == "cavedoor":
            return "[E] Salir de la cueva" if self.level.is_cave else "[E] Entrar a la cueva"
        return "[E] Abrir cofre antiguo"

    def interact(self):
        if not self.focus:
            return
        kind, o = self.focus
        p = self.player
        if kind == "water":
            p.drink_from(self.level)
        elif kind == "object":
            if o.kind == "cavedoor":
                if self.level.is_cave:
                    self.leave_cave()
                else:
                    self.enter_cave((int(o.x // TS), int((o.y - 2) // TS)))
            else:
                self._open_loot(o)
        else:
            if o.kind == "crafting_table":
                self.inv_ui.show(self, tab=1)
            elif o.kind == "oven":
                self.inv_ui.show(self, tab=4)
            elif o.kind == "chest":
                self.inv_ui.show(self, chest=o)
            elif o.kind == "bed":
                self._use_bed(o)
            elif o.kind == "door":
                if o.open and o.rect().colliderect(p.foot_rect()):
                    self.notify("Hay algo en el camino", S.C_BAD)
                else:
                    o.open = not o.open
                    audio.play("door", 0.7)

    def _open_loot(self, o):
        rng = random.Random(hash((self.seed, o.uid)) & 0xFFFFFFFF)
        for item, n in roll_loot(rng):
            scatter(self.level, o.x, o.y - 14, item, n, 100)
        self.level.fx.chips(o.x, o.y - 20, "spark", 14)
        self.level.fx.ring(o.x, o.y - 20, (255, 230, 140))
        audio.play("levelup", 0.7)
        self.level.remove_object(o)
        self.notify("¡Cofre antiguo abierto!", S.C_GOLD)

    def _use_bed(self, bed):
        p = self.player
        p.spawn_point = (bed.tx, bed.ty)
        if self.level_darkness() > 100 and not self.level.is_cave:
            def job():
                target = (self.elapsed * 1000.0 / S.DAY_LENGTH_MS)
                frac = (S.START_TIME_FRAC + target) % 1.0
                add = ((S.START_TIME_FRAC + 0.02 - frac) % 1.0) * S.DAY_LENGTH_MS / 1000.0
                self.elapsed += add
                p.hp = min(S.MAX_HEALTH, p.hp + 40)
                p.stamina = S.MAX_STAMINA
                p.food = max(10.0, p.food - 12)
                p.thirst = max(10.0, p.thirst - 14)
                for m in list(self.level.mobs):
                    if m.hostile:
                        m.remove = True
                audio.play("sleep")
                self.hud.show_banner(f"Día {self.day}", "Has dormido hasta el amanecer", 3.0)
            self.transition(job)
        else:
            self.notify("Reaparición fijada en esta cama", S.C_GOOD)
            audio.play("place", 0.6)

    # ══ eventos ══════════════════════════════════════════════════════════
    def handle_event(self, e):
        if e.type == pygame.QUIT:
            self.quit()
            return
        if hasattr(pygame, "WINDOWFOCUSLOST") and e.type == pygame.WINDOWFOCUSLOST:
            if self.state == "play" and not self.inv_ui.open:
                self.state = "paused"
            return
        if hasattr(pygame, "ACTIVEEVENT") and e.type == pygame.ACTIVEEVENT and getattr(e, "gain", 1) == 0 and getattr(e, "state", 0) & 2:
            if self.state == "play" and not self.inv_ui.open:
                self.state = "paused"
            return
        if self.show_controls:
            if e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN) or (hasattr(pygame, "FINGERDOWN") and e.type == pygame.FINGERDOWN):
                self.show_controls = False
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
            pygame.display.toggle_fullscreen()
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_m:
            audio.toggle_mute()
        if self.state == "title":
            self.title.event(e)
        elif self.state == "paused":
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.state = "play"
            else:
                self.pause_menu.event(e)
        elif self.state == "dead":
            is_tap = (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1) or (hasattr(pygame, "FINGERDOWN") and e.type == pygame.FINGERDOWN)
            if ((e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_SPACE)) or is_tap) and self.death_t > 2.2:
                self.respawn()
        elif self.state == "play":
            self._play_event(e)

    def _play_event(self, e):
        p = self.player
        if self.fade_job:
            return
        if self.inv_ui.open:
            self.inv_ui.handle_event(e, self)
            return
        if self.touch.handle_event(e, self):
            return
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k == pygame.K_ESCAPE:
                self.state = "paused"
            elif k in (pygame.K_i, pygame.K_TAB):
                self.inv_ui.show(self)
            elif k == pygame.K_e:
                self.interact()
            elif k == pygame.K_f:
                p.eat_held()
            elif k == pygame.K_SPACE:
                p.dash()
            elif k == pygame.K_q:
                self._drop_held()
            elif k == pygame.K_F3:
                self.debug = not self.debug
            elif pygame.K_1 <= k <= pygame.K_8:
                p.inv.select(k - pygame.K_1)
        elif e.type == pygame.MOUSEWHEEL:
            p.inv.scroll(-1 if e.y > 0 else 1)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i in range(S.HOTBAR_SLOTS):
                if hotbar_rect(i).collidepoint(e.pos):
                    p.inv.select(i)
                    self._click_consumed = True
                    audio.play("click", 0.3)
        elif hasattr(pygame, "FINGERDOWN") and e.type == pygame.FINGERDOWN:
            fpos = (int(e.x * S.SCREEN_W), int(e.y * S.SCREEN_H))
            for i in range(S.HOTBAR_SLOTS):
                if hotbar_rect(i).collidepoint(fpos):
                    p.inv.select(i)
                    self._click_consumed = True
                    audio.play("click", 0.3)

    def _drop_held(self):
        p = self.player
        h = p.inv.held()
        if h:
            scatter(self.level, p.x + p.fx * 24, p.y - 10, h.id, h.count, 50, h.dur)
            p.inv.slots[p.inv.selected] = None

    # ══ actualización ════════════════════════════════════════════════════
    def update(self, dt):
        dt = min(dt, 0.05)
        self.fps = self.fps * 0.95 + (1.0 / max(dt, 1e-3)) * 0.05
        if self.state == "title":
            self.bg_t += dt
            self.bg_level.t += dt
            self.bg_level.ensure(self.bg_t * 40, 0, 2, budget=4)
            self.title.update(dt)
            return
        if self.state == "paused":
            self.pause_menu.update(dt)
            return
        self._update_fade(dt)
        p = self.player
        if self.state == "dead":
            self.death_t += dt
            p.update(dt, self.level, (0, 0), False)
            self.level.update(dt, p, self.level_darkness(), self.day)
            self._update_camera(dt)
            self._fx_decay(dt)
            return
        self.elapsed += dt
        self.touch.update(dt, self)
        keys = pygame.key.get_pressed()
        mv = [0.0, 0.0]
        if not self.inv_ui.open and not self.fade_job:
            if keys[pygame.K_a] or keys[pygame.K_LEFT]: mv[0] -= 1
            if keys[pygame.K_d] or keys[pygame.K_RIGHT]: mv[0] += 1
            if keys[pygame.K_w] or keys[pygame.K_UP]: mv[1] -= 1
            if keys[pygame.K_s] or keys[pygame.K_DOWN]: mv[1] += 1
            if self.touch.enabled and (self.touch.move_vector[0] != 0 or self.touch.move_vector[1] != 0):
                mv[0] += self.touch.move_vector[0]
                mv[1] += self.touch.move_vector[1]
        run = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) or (self.touch.enabled and self.touch.is_running)
        buttons = pygame.mouse.get_pressed()
        mx, my = pygame.mouse.get_pos()
        wx, wy = mx + self.cam[0], my + self.cam[1]
        block = bool(buttons[2]) and not self.inv_ui.open
        p.update(dt, self.level, tuple(mv), run, block)
        if buttons[0] and not self.inv_ui.open and not self.fade_job and not getattr(self, "_click_consumed", False):
            if not any(hotbar_rect(i).collidepoint((mx, my)) for i in range(S.HOTBAR_SLOTS)):
                p.use(self.level, wx, wy)
        if not buttons[0]:
            self._click_consumed = False
        snow = (not self.level.is_cave) and self.overworld.biome(p.x, p.y) == "snow"
        self.weather.update(dt, self.level.outdoors, snow)
        dark = self.level_darkness()
        self.level.update(dt, p, dark, self.day)
        self.hud.update(dt, p)
        self.hud.minimap.update(self.level, int(p.x // TS), int(p.y // TS), dt)
        self.compute_focus()
        self._update_camera(dt)
        self._fx_decay(dt)
        self._events(dark)
        self.autosave_t -= dt
        if self.autosave_t <= 0:
            self.autosave_t = S.AUTOSAVE_SECONDS
            self.save_game(silent=True)

    def _fx_decay(self, dt):
        self.shake_amt = max(0.0, self.shake_amt - dt * 22)
        self.flash_a = max(0.0, self.flash_a - dt * 260)

    def _events(self, dark):
        if self.level.is_cave:
            return
        night = dark > 110
        if night and not self.was_night:
            self.hud.show_banner("Anochece", "Los no-muertos salen de sus tumbas", 3.0)
        elif not night and self.was_night:
            self.hud.show_banner(f"Día {self.day}", "Amanece. El sol los quema.", 3.0)
        self.was_night = night

    def _update_camera(self, dt):
        p = self.player
        if self.touch.enabled:
            look_x = p.fx * 20.0
            look_y = p.fy * 20.0
        else:
            mx, my = pygame.mouse.get_pos()
            look_x = (mx - S.SCREEN_W / 2) * 0.10
            look_y = (my - S.SCREEN_H / 2) * 0.10
        tx = p.x - S.SCREEN_W / 2 + look_x
        ty = p.y - 24 - S.SCREEN_H / 2 + look_y
        k = 1 - math.exp(-dt * 9.0)
        self.cam[0] += (tx - self.cam[0]) * k
        self.cam[1] += (ty - self.cam[1]) * k

    # ══ dibujo ═══════════════════════════════════════════════════════════
    def draw(self):
        scr = self.screen
        if self.state == "title":
            self._draw_title(scr)
        else:
            self._draw_world(scr)
            if self.state == "dead":
                menus.draw_death(scr, self.player, self.day, self.death_t, self.grave_msg, touch_enabled=self.touch.enabled)
            elif self.state == "paused":
                self.pause_menu.draw(scr)
        if self.show_controls:
            menus.draw_controls(scr)
        if self.fade > 0:
            self._fade_surface.fill((0, 0, 0))
            self._fade_surface.set_alpha(int(255 * self.fade))
            scr.blit(self._fade_surface, (0, 0))
        if self.debug and self.state != "title":
            self._draw_debug(scr)

    def _draw_title(self, scr):
        lv = self.bg_level
        cx, cy = self.bg_t * 40 - S.SCREEN_W / 2, -S.SCREEN_H / 2 + math.sin(self.bg_t * 0.2) * 60
        lv.draw(scr, cx, cy)
        col, dk = lighting.ambient(0.33)
        self.lighting.render(scr, cx, cy, col, dk, [])
        self.title.draw(scr)

    def _draw_world(self, scr):
        p = self.player
        sh = self.shake_amt
        ox = random.uniform(-sh, sh) if sh > 0.2 else 0
        oy = random.uniform(-sh, sh) if sh > 0.2 else 0
        cx, cy = int(self.cam[0] + ox), int(self.cam[1] + oy)
        lv = self.level
        lv.draw(scr, cx, cy, [p])
        # iluminación
        if lv.is_cave:
            amb, dark = S.CAVE_AMBIENT, S.CAVE_DARK
        else:
            amb, dark = lighting.ambient(self.time_frac)
            dark += self.weather.intensity * 26
            k = 1.0 - self.weather.intensity * 0.12
            amb = (int(amb[0] * k), int(amb[1] * k), int(amb[2] * k))
        lights = lv.collect_lights(cx, cy)
        t = lv.t
        held = p.inv.held_id()
        r0 = 210 if lv.is_cave else (165 if dark > 90 else 0)
        if r0:
            lights.append((p.x, p.y - 26, r0, 215, (255, 196, 130)))
        if held == "torch":
            f = 1 + 0.06 * math.sin(t * 9) + 0.04 * math.sin(t * 23)
            lights.append((p.x + p.fx * 10, p.y - 28, 270 * f, 215, (255, 190, 110)))
        self.lighting.render(scr, cx, cy, amb, dark, lights)
        lv.fx.draw_texts(scr, cx, cy)
        self.weather.draw(scr)
        if self.flash_a > 0 and self.flash_col:
            self._flash_surface.fill((*self.flash_col, int(self.flash_a)))
            scr.blit(self._flash_surface, (0, 0))
        if self.state != "dead":
            self.hud.draw(scr, self)
            if self.inv_ui.open:
                self.inv_ui.draw(scr, self, 1 / 60.0)
            self._draw_target_marker(scr, cx, cy)
            if not self.touch.enabled:
                self.hud.draw_cursor(scr, self._cursor_active())
            self.touch.draw(scr, self)
        else:
            pass

    def _cursor_active(self):
        if self.inv_ui.open or self.state != "play":
            return False
        mx, my = pygame.mouse.get_pos()
        wx, wy = mx + self.cam[0], my + self.cam[1]
        p = self.player
        for o in self.level.objects_near(wx, wy, 40):
            if o.spec["hp"] > 0 and not o.interactive and math.hypot(o.x - p.x, o.y - p.y) < 130:
                return True
        for m in self.level.mobs:
            bx, by = m.body_pos()
            if math.hypot(bx - wx, by - wy) < m.hit_radius + 10:
                return True
        return False

    def _draw_target_marker(self, scr, cx, cy):
        if self.inv_ui.open or not self.focus:
            return
        kind, o = self.focus
        if kind == "water":
            return
        if kind == "struct":
            x, y = o.center()
            y -= 46
        else:
            x, y = o.x, o.y - 70
        bob = math.sin(self.level.t * 6) * 3
        sx, sy = int(x - cx), int(y - cy + bob)
        pygame.draw.polygon(scr, (0, 0, 0), [(sx - 9, sy - 1), (sx + 9, sy - 1), (sx, sy + 11)])
        pygame.draw.polygon(scr, S.C_GOLD, [(sx - 7, sy), (sx + 7, sy), (sx, sy + 8)])

    def _draw_debug(self, scr):
        p = self.player
        lv = self.level
        lines = [f"FPS {self.fps:5.1f}", f"pos {p.x / TS:7.1f}, {p.y / TS:7.1f}  tile {lv.tile(int(p.x // TS), int(p.y // TS))}",
                 f"chunks {len(lv.chunks)}  mobs {len(lv.mobs)}  drops {len(lv.drops)}  particulas {len(lv.fx.p)}",
                 f"hora {lighting.clock_text(self.time_frac)}  dia {self.day}  semilla {self.seed}"]
        for i, l in enumerate(lines):
            W.text(scr, l, (230, 92 + i * 22), 22, (180, 255, 180))

    # ══ bucle ════════════════════════════════════════════════════════════
    def run(self):
        while self.running:
            dt = self.clock.tick(S.FPS) / 1000.0
            for e in pygame.event.get():
                self.handle_event(e)
            self.update(dt)
            self.draw()
            pygame.display.flip()
        pygame.quit()

    async def run_async(self):
        import asyncio
        while self.running:
            dt = self.clock.tick(S.FPS) / 1000.0
            for e in pygame.event.get():
                self.handle_event(e)
            self.update(dt)
            self.draw()
            pygame.display.flip()
            await asyncio.sleep(0)
        pygame.quit()
