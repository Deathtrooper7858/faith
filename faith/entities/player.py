"""El jugador: movimiento, estadísticas de supervivencia, acciones y animaciones."""
import math
import random
import pygame
from .. import assets, audio, items, settings as S
from ..inventory import Inventory, ItemStack
from ..util import clamp, dist, normalize
from ..world import terrain as T
from ..world.structures import PLACE_FROM_ITEM
from .drops import scatter

TS = S.TILE
_rng = random.Random()

# filas de las hojas de sprites
ROW_IDLE = {"down": 0, "side": 1, "up": 2}
ROW_WALK = {"down": 3, "side": 4, "up": 5}
SWORD_ROW = {"down": 6, "side": 7, "up": 8}
ACT_BASE = {"pickaxe": 0, "axe": 3, "shovel": 6}
ACT_OFF = {"side": 0, "down": 1, "up": 2}


class Frames:
    """Hojas de sprites del jugador, escaladas x2 y cacheadas."""

    def __init__(self):
        sheet = assets.load("character/Player.png")
        acts = assets.load("character/actions.png")
        self.base = {}                       # (row, frame) -> Surface (64x64)
        for row in range(10):
            for col in range(6):
                if row >= 6 and col > 3:
                    continue
                f = sheet.subsurface(pygame.Rect(col * 32, row * 32, 32, 32)).copy()
                if f.get_bounding_rect().w == 0:
                    continue
                self.base[(row, col)] = pygame.transform.scale(f, (64, 64))
        self.act = {}                        # (row, frame) -> Surface (96x96)
        for row in range(12):
            for col in range(2):
                f = acts.subsurface(pygame.Rect(col * 48, row * 48, 48, 48)).copy()
                self.act[(row, col)] = pygame.transform.scale(f, (96, 96))
        self.flip_cache = {}

    def flipped(self, surf):
        return assets.flipx(surf)


_frames = None


def frames():
    global _frames
    if _frames is None:
        _frames = Frames()
    return _frames


def facing_name(fx, fy):
    if abs(fx) > abs(fy) + 1e-6:
        return "side"
    return "down" if fy >= 0 else "up"


class Player:
    def __init__(self, host, x=0.0, y=0.0):
        self.host = host
        self.x, self.y = float(x), float(y)       # posición de los PIES
        self.vx = self.vy = 0.0
        self.kx = self.ky = 0.0
        self.fx, self.fy = 0.0, 1.0               # vector de orientación
        self.hp, self.food, self.thirst, self.stamina = S.MAX_HEALTH, S.MAX_FOOD, S.MAX_THIRST, S.MAX_STAMINA
        self.inv = Inventory()
        self.dead = False
        self.death_t = 0.0
        self.running = False
        self.exhausted = False
        self.blocking = False
        self.moving = False
        self.cd = 0.0
        self.swing_t = 0.0
        self.swing_dur = 0.0
        self.swing_kind = None                    # "pickaxe" | "axe" | "shovel" | "sword" | "bow" | "punch"
        self.pending = None                       # (tiempo restante, acción) a mitad del golpe
        self.invuln = 0.0
        self.flash = 0.0
        self.dash_t = 0.0
        self.dash_cool = 0.0
        self.dashdir = (0.0, 1.0)
        self.afterimages = []
        self.anim_t = 0.0
        self.step_t = 0.0
        self.drink_cd = 0.0
        self.eat_cd = 0.0
        self.last_hurt = 99.0
        self.regen_acc = 0.0
        self.spawn_point = None                   # cama
        self.stats = dict(kills=0, mined=0, crafted=0, deaths=0)
        self.stamina_lock = 0.0

    # ── propiedades ───────────────────────────────────────────────────────
    @property
    def sort_y(self):
        return self.y

    @property
    def face(self):
        return facing_name(self.fx, self.fy)

    def foot_rect(self):
        return pygame.Rect(int(self.x - S.PLAYER_FOOT_W / 2), int(self.y - S.PLAYER_FOOT_H),
                           S.PLAYER_FOOT_W, S.PLAYER_FOOT_H)

    def body_pos(self):
        return self.x, self.y - 24

    def held_def(self):
        h = self.inv.held()
        return h.d if h else None

    def tool_kind(self):
        d = self.held_def()
        return d.get("tool") if d and d.kind == "tool" else None

    def on_pickup(self, item_id, count):
        self.host.toast_item(item_id, count)

    # ── movimiento ────────────────────────────────────────────────────────
    def update(self, dt, level, move, run, block=False):
        if self.dead:
            self.death_t += dt
            return
        dt = min(dt, 0.05)
        self.cd = max(0.0, self.cd - dt)
        self.invuln = max(0.0, self.invuln - dt)
        self.flash = max(0.0, self.flash - dt)
        self.drink_cd = max(0.0, self.drink_cd - dt)
        self.eat_cd = max(0.0, self.eat_cd - dt)
        self.dash_cool = max(0.0, self.dash_cool - dt)
        self.last_hurt += dt
        self.anim_t += dt
        self.stamina_lock = max(0.0, self.stamina_lock - dt)

        mx, my = move
        self.moving = (mx != 0 or my != 0)
        if self.moving:
            mx, my = normalize(mx, my)
            self.fx, self.fy = mx, my
        acting = self.swing_t > 0
        if self.exhausted and self.stamina > 22:
            self.exhausted = False
        self.running = bool(run and self.moving and not self.exhausted and self.stamina > 0 and not acting)
        self.blocking = bool(block and self.inv.has_shield() and not self.dash_t > 0)

        speed = S.RUN_SPEED if self.running else S.WALK_SPEED
        if level.in_shallow(self.x, self.y - 6):
            speed *= S.WATER_SLOW
        if self.blocking:
            speed *= 0.45
        if acting:
            speed *= 0.6

        if self.dash_t > 0:
            self.dash_t -= dt
            tx, ty = self.dashdir[0] * 560, self.dashdir[1] * 560
            self.vx, self.vy = tx, ty
            if _rng.random() < 0.8:
                self.afterimages.append([self.x, self.y, 0.22, self.face, self.fx < 0])
        else:
            accel = 2600 if self.moving else 3400
            tvx, tvy = mx * speed, my * speed
            self.vx += clamp(tvx - self.vx, -accel * dt, accel * dt)
            self.vy += clamp(tvy - self.vy, -accel * dt, accel * dt)
        self.afterimages = [a for a in self.afterimages if (a.__setitem__(2, a[2] - dt) or a[2] > 0)]

        total_x = (self.vx + self.kx) * dt
        total_y = (self.vy + self.ky) * dt
        self.kx *= max(0.0, 1 - 10 * dt)
        self.ky *= max(0.0, 1 - 10 * dt)
        steps = max(1, int(max(abs(total_x), abs(total_y)) // 8) + 1)
        for _ in range(steps):
            self._slide(total_x / steps, 0, level)
            self._slide(0, total_y / steps, level)

        # estadísticas
        decay = (S.RUN_DECAY_MULT if self.running else 1.0)
        self.food = max(0.0, self.food - S.FOOD_DECAY * decay * dt)
        self.thirst = max(0.0, self.thirst - S.THIRST_DECAY * decay * dt)
        if self.running:
            self.stamina = max(0.0, self.stamina - S.STAMINA_DRAIN * dt)
            self.stamina_lock = 0.7
            if self.stamina <= 0:
                self.exhausted = True
        elif self.stamina_lock <= 0:
            rate = S.STAMINA_REGEN * (1.0 if self.food > 15 and self.thirst > 15 else 0.35)
            self.stamina = min(S.MAX_STAMINA, self.stamina + rate * dt)
        if self.food <= 0 or self.thirst <= 0:
            self.hp -= S.STARVE_DAMAGE * dt
            self.last_hurt = 0
            if self.hp <= 0:
                self.die(level)
        elif self.food > 55 and self.thirst > 55 and self.last_hurt > 6 and self.hp < S.MAX_HEALTH:
            self.hp = min(S.MAX_HEALTH, self.hp + S.REGEN_RATE * dt)
        if level.in_lava(self.x, self.y - 6):
            self.hp -= S.LAVA_DPS * dt
            self.last_hurt = 0
            self.flash = 0.05
            if _rng.random() < dt * 20:
                level.fx.ember(self.x, self.y - 10, 2)
            if self.hp <= 0:
                self.die(level)
        # pasos
        if self.moving and (abs(self.vx) + abs(self.vy)) > 40:
            self.step_t -= dt
            if self.step_t <= 0:
                self.step_t = 0.19 if self.running else 0.3
                audio.play("splash" if level.in_shallow(self.x, self.y - 6) else "step", 0.35)
                if self.running and not level.is_cave:
                    level.fx.chips(self.x, self.y - 2, "dust", 2)
        # animación de golpe
        if self.swing_t > 0:
            self.swing_t = max(0.0, self.swing_t - dt)
        if self.pending:
            self.pending[0] -= dt
            if self.pending[0] <= 0:
                fn = self.pending[1]
                self.pending = None
                fn(level)

    def _slide(self, dx, dy, level):
        if dx == 0 and dy == 0:
            return
        r = self.foot_rect()
        r.x = int(round(self.x + dx - S.PLAYER_FOOT_W / 2))
        r.y = int(round(self.y + dy - S.PLAYER_FOOT_H))
        if not level.collides(r):
            self.x += dx
            self.y += dy
        else:
            if dx:
                self.vx *= 0.3
                self.kx = 0
            if dy:
                self.vy *= 0.3
                self.ky = 0

    def teleport(self, x, y):
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = self.kx = self.ky = 0.0

    # ── daño y muerte ─────────────────────────────────────────────────────
    def hurt(self, dmg, ang, level, attacker=None):
        if self.dead or self.invuln > 0 or self.dash_t > 0:
            return 0
        sx, sy = -math.cos(ang), -math.sin(ang)           # hacia donde está el atacante
        shielded = False
        if self.blocking and self.fx * sx + self.fy * sy > 0.25 and self.stamina > 5:
            shielded = True
            dmg *= (1.0 - S.SHIELD_BLOCK)
            self.stamina = max(0.0, self.stamina - 12)
            self.stamina_lock = 1.0
            audio.play("mine", 0.7)
            level.fx.chips(self.x + sx * 18, self.y - 28, "spark", 8)
        red = min(S.DEFENSE_CAP, self.inv.defense() * S.DEFENSE_PER_POINT)
        dmg = max(1.0, dmg * (1.0 - red))
        self.hp -= dmg
        self.invuln = S.INVULN_MS / 1000.0
        self.flash = 0.18
        self.last_hurt = 0.0
        kn = 150 if shielded else 260
        self.kx, self.ky = math.cos(ang) * kn, math.sin(ang) * kn
        audio.play("hurt", 0.8)
        level.fx.chips(self.x, self.y - 26, "blood", 8)
        level.fx.text(self.x, self.y - 60, f"-{int(round(dmg))}", (255, 90, 90), 26)
        self.host.shake(3 + min(dmg, 20) * 0.35)
        self.host.flash_screen((200, 20, 20), 70 if not shielded else 25)
        if self.hp <= 0:
            self.die(level)
        return dmg

    def die(self, level):
        if self.dead:
            return
        self.hp = 0
        self.dead = True
        self.death_t = 0.0
        self.stats["deaths"] += 1
        audio.play("die")
        self.host.on_player_death(level)

    def respawn(self):
        self.dead = False
        self.hp, self.food, self.thirst, self.stamina = S.MAX_HEALTH, S.MAX_FOOD * 0.7, S.MAX_THIRST * 0.7, S.MAX_STAMINA
        self.invuln = 2.0
        self.vx = self.vy = self.kx = self.ky = 0.0
        self.swing_t = self.cd = 0.0
        self.pending = None
        self.exhausted = False

    # ── acciones ──────────────────────────────────────────────────────────
    def aim_at(self, wx, wy):
        d = normalize(wx - self.x, wy - (self.y - 24))
        if d != (0.0, 0.0):
            self.fx, self.fy = d

    def use(self, level, wx, wy):
        """Clic izquierdo mantenido: usa el objeto en mano hacia (wx, wy)."""
        if self.dead or self.cd > 0 or self.dash_t > 0:
            return
        self.aim_at(wx, wy)
        ang = math.atan2(wy - (self.y - 24), wx - self.x)
        h = self.inv.held()
        d = h.d if h else None
        if d is None:
            self._swing("punch", 0.42, lambda lv: self._hit(lv, ang, None, 0, 0.5, 3, 0))
            return
        if d.kind == "tool":
            tool = d.get("tool")
            cd = d.get("cd") / 1000.0
            if tool == "bow":
                self._shoot(level, ang, cd)
            elif tool == "sword":
                self._swing("sword", cd, lambda lv: self._slash(lv, ang, d))
            else:
                self._swing(tool, cd, lambda lv: self._hit(lv, ang, tool, d.get("tier"), d.get("power"), d.get("dmg"), 1))
        elif d.kind == "food":
            self.eat_held()
        elif d.kind == "placeable":
            self._place(level, wx, wy, d)
        else:
            self._swing("punch", 0.42, lambda lv: self._hit(lv, ang, None, 0, 0.5, 3, 0))

    def _swing(self, kind, dur, fn):
        self.swing_kind = kind
        self.swing_dur = dur
        self.swing_t = dur
        self.cd = dur
        self.pending = [dur * 0.45, fn]
        audio.play("swing", 0.4)

    def _shoot(self, level, ang, cd):
        from .projectile import Projectile
        if self.inv.count("arrow") <= 0:
            if self.cd <= 0:
                self.host.notify("Sin flechas", S.C_BAD)
                self.cd = 0.4
            return
        self.inv.remove("arrow", 1)
        self.cd = cd
        self.swing_kind = "bow"
        self.swing_dur = 0.25
        self.swing_t = 0.25
        d = self.held_def()
        dmg = d.get("dmg") * _rng.uniform(0.9, 1.15)
        bx, by = self.body_pos()
        level.projectiles.append(Projectile(bx + math.cos(ang) * 14, by + math.sin(ang) * 14, ang, 640, dmg, "player", 700))
        audio.play("arrow", 0.7)
        self.kx -= math.cos(ang) * 40
        self.ky -= math.sin(ang) * 40
        if self.inv.wear_held(1):
            self.host.notify("¡Tu arco se rompió!", S.C_BAD)
            audio.play("hit")

    def _targets_in_cone(self, level, ang, reach, half_angle=1.15):
        """Objetos, mobs y estructuras delante del jugador."""
        px, py = self.x, self.y - 22
        out_obj, out_mob = None, []
        best = 1e9
        for o in level.objects_near(px, py, reach + 90):
            if o.kind == "cavedoor" or o.kind == "lootchest":
                continue
            cx, cy = o.center()
            dd = dist(px, py, cx, cy) - o.radius()
            if dd > reach:
                continue
            a = math.atan2(cy - py, cx - px)
            diff = abs((a - ang + math.pi) % math.tau - math.pi)
            if diff < half_angle + (0.5 if dd < 20 else 0.0) and dd < best:
                best, out_obj = dd, o
        for m in level.mobs:
            if m.dying:
                continue
            bx, by = m.body_pos()
            dd = dist(px, py, bx, by) - m.hit_radius
            if dd > reach:
                continue
            a = math.atan2(by - py, bx - px)
            diff = abs((a - ang + math.pi) % math.tau - math.pi)
            if diff < half_angle or dd < 14:
                out_mob.append((dd, m))
        out_mob.sort(key=lambda t: t[0])
        return out_obj, [m for _, m in out_mob]

    def _hit(self, level, ang, tool, tier, power, dmg, wear):
        """Golpe con herramienta o puño: prioriza mobs; si no hay, el objeto del mundo."""
        obj, mobs = self._targets_in_cone(level, ang, S.REACH, 0.95)
        px, py = self.x, self.y - 22
        hx, hy = px + math.cos(ang) * 40, py + math.sin(ang) * 40
        if mobs:
            m = mobs[0]
            killed = m.hurt(dmg * _rng.uniform(0.9, 1.1), ang, level, self)
            if killed:
                self.stats["kills"] += 1
            self._after_hit(wear)
            self.host.shake(2)
            return
        if obj is not None:
            status, units, destroyed = obj.hit(tool, tier, power)
            if status == "tool":
                need = obj.spec["tool"]
                self.host.notify(f"Necesitas {'un ' + items.TOOL_NAMES.get(need, 'herramienta').lower() if need else 'otra herramienta'}", S.C_BAD)
                audio.play("click", 0.5)
                level.fx.chips(obj.x, obj.y - 20, "dust", 3)
                return
            if status == "tier":
                names = {1: "madera", 2: "piedra", 3: "hierro"}
                self.host.notify(f"Necesitas {items.TOOL_NAMES.get(obj.spec['tool'], 'herramienta').lower()} de {names.get(obj.spec['tier'], '?')} o mejor", S.C_BAD)
                audio.play("click", 0.5)
                return
            level.activate(obj)
            cxo, cyo = obj.center()
            audio.play(obj.spec["sfx"], 0.8)
            kind = "leaf" if obj.spec.get("leaves") else ("wood" if obj.kind == "stump" else "stone")
            level.fx.chips(cxo, cyo, kind, 6)
            if obj.spec.get("leaves"):
                level.fx.chips(cxo, cyo - 16, "wood", 3)
            self.host.shake(1.5)
            y = obj.spec["yield_"]
            if y and units > 0:
                scatter(level, obj.x, obj.y - 10, y, units, 70)
                self.stats["mined"] += units
            if destroyed:
                for item, n in obj.loot(_rng):
                    scatter(level, obj.x, obj.y - 10, item, n, 90)
                level.remove_object(obj)
                level.fx.chips(cxo, cyo, kind, 10)
                if obj.spec.get("leaves"):
                    audio.play("place", 0.6)
            self._after_hit(wear)
            return
        # excavar arena con la pala
        if tool == "shovel":
            tx, ty = int((px + math.cos(ang) * 44) // TS), int((py + 20 + math.sin(ang) * 44) // TS)
            if level.tile(tx, ty) == T.SAND and (tx, ty) not in level.structs:
                scatter(level, (tx + 0.5) * TS, (ty + 0.5) * TS, "sand", 1 + (1 if _rng.random() < 0.4 else 0), 40)
                level.fx.chips((tx + 0.5) * TS, (ty + 0.5) * TS, "dust", 6)
                audio.play("place", 0.5)
                self._after_hit(wear)
                return
        # deshacer estructuras (pico, hacha o pala)
        if tool in ("axe", "pickaxe", "shovel"):
            st = self._struct_in_front(level, ang)
            if st:
                if st.items and any(st.items):
                    self.host.notify("Vacía el cofre antes de recogerlo", S.C_BAD)
                    return
                level.remove_structure(st)
                cxs, cys = st.center()
                scatter(level, cxs, cys, st.spec["drop"], 1, 40)
                level.fx.chips(cxs, cys, "wood" if "wood" in st.kind or st.kind in ("door", "chest", "bed", "fence", "crafting_table") else "stone", 10)
                audio.play("place", 0.7)
                self._after_hit(wear)
                return
        level.fx.chips(hx, hy, "dust", 2)

    def _struct_in_front(self, level, ang):
        px, py = self.x, self.y - 14
        best, bd = None, 1e9
        for st in level.structs_near(px, py, S.REACH + 36):
            cx, cy = st.center()
            a = math.atan2(cy - py, cx - px)
            diff = abs((a - ang + math.pi) % math.tau - math.pi)
            dd = dist(px, py, cx, cy)
            if diff < 1.0 and dd < bd:
                best, bd = st, dd
        return best

    def _after_hit(self, wear):
        if wear and self.inv.wear_held(wear):
            self.host.notify("¡Se rompió tu herramienta!", S.C_BAD)
            audio.play("hit")

    def _slash(self, level, ang, d):
        px, py = self.x, self.y - 22
        dmg = d.get("dmg")
        hit_any = False
        level.fx.slash(px + math.cos(ang) * 34, py + math.sin(ang) * 34, ang, (255, 255, 255))
        for m in level.mobs:
            if m.dying:
                continue
            bx, by = m.body_pos()
            dd = dist(px, py, bx, by) - m.hit_radius
            if dd > S.REACH + 22:
                continue
            a = math.atan2(by - py, bx - px)
            diff = abs((a - ang + math.pi) % math.tau - math.pi)
            if diff < 1.25 or dd < 14:
                crit = _rng.random() < 0.12
                if m.hurt(dmg * (1.6 if crit else _rng.uniform(0.9, 1.1)), ang, level, self, knock=1.2):
                    self.stats["kills"] += 1
                if crit:
                    level.fx.ring(bx, by, (255, 220, 120))
                hit_any = True
        if hit_any:
            self.host.shake(3.5)
            self._after_hit(1)
        # la espada también corta flores y plantas
        for o in level.objects_near(px + math.cos(ang) * 30, py + math.sin(ang) * 30, 34):
            if o.kind == "rose":
                o.hit(None, 0, 2)
                scatter(level, o.x, o.y - 6, "rose", 1, 40)
                for item, n in o.loot(_rng):
                    scatter(level, o.x, o.y - 6, item, n, 40)
                level.remove_object(o)

    def _place(self, level, wx, wy, d):
        kind = d.get("place")
        px, py = self.x, self.y - 14
        tx, ty = int(wx // TS), int(wy // TS)
        if dist(px, py, (tx + 0.5) * TS, (ty + 0.5) * TS) > TS * 3.3:
            # demasiado lejos: colocar en el tile frente al jugador
            tx = int((px + self.fx * TS * 1.3) // TS)
            ty = int((py + self.fy * TS * 1.3 + 12) // TS)
        blockers = [self.foot_rect()] + [m.foot_rect() for m in level.mobs]
        st = level.add_structure(kind, tx, ty, blockers)
        self.cd = 0.25
        if st is None:
            self.host.notify("No se puede colocar aquí", S.C_BAD)
            audio.play("click", 0.5)
            return
        self.inv.consume_held(1)
        audio.play("place", 0.8)
        cxs, cys = st.center()
        level.fx.chips(cxs, cys + 14, "dust", 5)

    def eat_held(self):
        h = self.inv.held()
        if not h or h.d.kind != "food" or self.eat_cd > 0:
            return False
        d = h.d
        food, drink, hp = d.get("food", 0), d.get("drink", 0), d.get("hp", 0)
        useful = (food and self.food < S.MAX_FOOD - 1) or (drink and self.thirst < S.MAX_THIRST - 1) or (hp > 0 and self.hp < S.MAX_HEALTH - 1)
        if not useful:
            self.host.notify("No lo necesitas ahora", S.C_DIM)
            self.eat_cd = 0.4
            return False
        self.food = min(S.MAX_FOOD, self.food + food)
        self.thirst = min(S.MAX_THIRST, self.thirst + drink)
        if hp > 0:
            self.hp = min(S.MAX_HEALTH, self.hp + hp)
        elif hp < 0:
            self.hp += hp
            self.host.notify("Carne cruda… mejor cocínala", S.C_BAD)
            self.last_hurt = 0
            if self.hp <= 0:
                self.die(self.host.level)
        self.eat_cd = 0.7
        ret = d.get("returns")
        self.inv.consume_held(1)
        if ret:
            if self.inv.add(ret, 1):
                scatter(self.host.level, self.x, self.y, ret, 1, 40)
        audio.play("drink" if drink else "eat", 0.8)
        self.host.level.fx.chips(self.x, self.y - 30, "water" if drink else "dust", 5)
        return True

    def drink_from(self, level):
        """Beber / llenar botella frente al agua."""
        if self.drink_cd > 0:
            return False
        h = self.inv.held()
        if h and h.id == "bottle":
            self.inv.consume_held(1)
            left = self.inv.add("bwater", 1)
            if left:
                scatter(level, self.x, self.y, "bwater", 1, 30)
            audio.play("splash", 0.8)
            self.drink_cd = 0.6
            self.host.notify("Botella llena", S.C_WATER)
            return True
        if self.thirst >= S.MAX_THIRST - 1:
            self.host.notify("No tienes sed", S.C_DIM)
            self.drink_cd = 0.4
            return False
        self.thirst = min(S.MAX_THIRST, self.thirst + 24)
        self.drink_cd = 0.9
        audio.play("drink", 0.8)
        level.fx.chips(self.x + self.fx * 26, self.y - 8, "water", 8)
        return True

    def dash(self):
        if self.dead or self.dash_t > 0 or self.dash_cool > 0 or self.stamina < 20:
            return
        d = (self.fx, self.fy) if (self.fx or self.fy) else (0, 1)
        self.dashdir = d
        self.dash_t = 0.17
        self.dash_cool = 0.7
        self.invuln = max(self.invuln, 0.22)
        self.stamina -= 20
        self.stamina_lock = 0.9
        audio.play("swing", 0.5)

    # ── dibujo ────────────────────────────────────────────────────────────
    def _pick_frame(self):
        F = frames()
        face = self.face
        flip = self.fx < -0.01 if face == "side" else False
        if self.dead:
            f = min(3, int(self.death_t * 5))
            return F.base[(9, f)], (32, 50), self.fx < 0
        if self.swing_t > 0 and self.swing_kind:
            p = 1.0 - self.swing_t / max(self.swing_dur, 0.001)
            k = self.swing_kind
            if k == "sword":
                fr = min(3, int(p * 4))
                return F.base[(SWORD_ROW[face], fr)], (32, 50), flip
            if k in ACT_BASE:
                row = ACT_BASE[k] + ACT_OFF[face]
                return F.act[(row, 0 if p < 0.45 else 1)], (48, 66), flip
            if k == "punch":
                row = ACT_BASE["shovel"] + ACT_OFF[face]
                return F.act[(row, 0 if p < 0.45 else 1)], (48, 66), flip
        moving = self.moving and (abs(self.vx) + abs(self.vy) > 30)
        rows = ROW_WALK if moving else ROW_IDLE
        spd = 14 if self.running else 9
        fr = int(self.anim_t * (spd if moving else 4)) % 6
        return F.base[(rows[face], fr)], (32, 50), flip

    def sprite_draw(self, surf, cx, cy):
        img, (ax, ay), flip = self._pick_frame()
        sx, sy = self.x - cx, self.y - cy
        if flip:
            img = assets.flipx(img)
            ax = img.get_width() - ax
        # estela del dash
        for (gx, gy, life, _f, fl) in self.afterimages:
            g = img.copy()
            g.set_alpha(int(110 * (life / 0.22)))
            surf.blit(g, (int(gx - cx - ax), int(gy - cy - ay)))
        bob = 0
        if self.moving and self.swing_t <= 0 and not self.dead:
            bob = -abs(math.sin(self.anim_t * (14 if self.running else 9))) * 1.5
        draw = img
        if self.flash > 0 and not self.dead:
            draw = assets.tint(img, (140, 40, 40), mult=False)
        elif self.invuln > 0 and int(self.anim_t * 22) % 2 == 0 and self.dash_t <= 0:
            draw = img.copy()
            draw.set_alpha(120)
        surf.blit(draw, (int(sx - ax), int(sy - ay + bob)))
        if self.blocking:
            ic = items.icon("shield", 30)
            ox = self.fx * 18
            surf.blit(ic, (int(sx + ox - 15), int(sy - 44 + self.fy * 6)))

    def draw(self, surf, cx, cy):
        self.sprite_draw(surf, cx, cy)

    # ── guardado ──────────────────────────────────────────────────────────
    def to_json(self):
        return {"x": self.x, "y": self.y, "hp": self.hp, "food": self.food, "thirst": self.thirst,
                "stamina": self.stamina, "inv": self.inv.to_json(), "stats": self.stats,
                "bed": self.spawn_point}

    def load_json(self, d):
        self.x, self.y = float(d.get("x", 0)), float(d.get("y", 0))
        self.hp = float(d.get("hp", S.MAX_HEALTH))
        self.food = float(d.get("food", S.MAX_FOOD))
        self.thirst = float(d.get("thirst", S.MAX_THIRST))
        self.stamina = float(d.get("stamina", S.MAX_STAMINA))
        self.inv.load_json(d.get("inv", {}))
        self.stats.update(d.get("stats", {}))
        self.spawn_point = tuple(d["bed"]) if d.get("bed") else None
