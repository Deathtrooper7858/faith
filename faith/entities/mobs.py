"""Criaturas: enemigos (no-muertos) y animales, con IA sencilla basada en estados."""
import math
import random
import pygame
from .. import assets, audio, settings as S
from ..util import dist, clamp, normalize
from .drops import scatter
from .projectile import Projectile
from ..world import terrain as T

_rng = random.Random()
TS = S.TILE


def _sp(**k):
    return k


SPECIES = {
    # ── no-muertos ───────────────────────────────────────────────────────────
    "skeleton": _sp(name="Esqueleto", hostile=True, hp=34, dmg=10, speed=84, aggro=560, rng=44, windup=0.50, cd=1.2,
                    ai="melee", foot=(22, 14), body=44, gfx=("strip", 3.0), knock=1.0, sun=True,
                    drops=[("bone", 0, 2, .75), ("arrow", 0, 2, .30), ("coal", 0, 1, .12)]),
    "bones": _sp(name="Huesudo", hostile=True, hp=18, dmg=6, speed=130, aggro=520, rng=34, windup=0.28, cd=0.8,
                 ai="melee", foot=(18, 12), body=34, gfx=("tiny", "DecrepitBones", 4.0), knock=1.3, sun=True,
                 drops=[("bone", 0, 1, .6)]),
    "archer": _sp(name="Arquero frágil", hostile=True, hp=24, dmg=11, speed=72, aggro=640, rng=340, windup=0.75,
                  cd=2.1, ai="ranged", foot=(18, 12), body=36, gfx=("tiny", "BrittleArcher", 4.0), knock=1.2,
                  sun=True, drops=[("arrow", 1, 4, .85), ("bone", 0, 1, .5), ("stick", 0, 1, .4)]),
    "revenant": _sp(name="Revenant", hostile=True, hp=86, dmg=20, speed=64, aggro=620, rng=52, windup=0.80, cd=1.7,
                    ai="melee", foot=(26, 14), body=52, gfx=("tiny", "GraveRevenant", 5.0), knock=0.4, sun=True,
                    drops=[("bone", 1, 3, .9), ("iron-ingot", 0, 2, .5), ("gold-ingot", 0, 1, .12), ("leather", 0, 1, .3)]),
    "bat": _sp(name="Murciélago", hostile=True, hp=12, dmg=5, speed=150, aggro=560, rng=30, windup=0.0, cd=1.0,
               ai="bat", foot=(16, 10), body=40, gfx=("tiny", "VampireBat", 4.0), flying=True, knock=1.5, sun=True,
               drops=[("leather", 0, 1, .3)]),
    # ── animales ─────────────────────────────────────────────────────────────
    "cow": _sp(name="Vaca", hostile=False, hp=30, speed=46, foot=(34, 16), body=40, gfx=("cell", 0, 9, 2.0), ai="passive",
               drops=[("meat", 1, 3, 1.0), ("leather", 1, 2, .8)], knock=0.6),
    "pig": _sp(name="Cerdo", hostile=False, hp=22, speed=52, foot=(28, 14), body=30, gfx=("cell", 6, 9, 2.0), ai="passive",
               drops=[("meat", 1, 2, 1.0)], knock=0.8),
    "chicken": _sp(name="Gallina", hostile=False, hp=8, speed=70, foot=(14, 10), body=24, gfx=("cell", 0, 14, 1.8),
                   ai="passive", drops=[("meat", 1, 1, 1.0), ("fiber", 0, 2, .5)], knock=1.5),
    "rabbit": _sp(name="Conejo", hostile=False, hp=8, speed=118, foot=(14, 10), body=20, gfx=("cell", 6, 6, 1.8),
                  ai="passive", hop=True, drops=[("meat", 1, 1, .9), ("leather", 0, 1, .4)], knock=1.5),
    "goat": _sp(name="Cabra", hostile=False, hp=24, speed=56, foot=(26, 14), body=36, gfx=("cell", 0, 15, 2.0),
                ai="passive", drops=[("meat", 1, 2, 1.0), ("wool", 1, 2, .8)], knock=0.8),
    "boar": _sp(name="Jabalí", hostile=False, hp=42, dmg=9, speed=104, aggro=380, rng=44, windup=0.35, cd=1.2,
                foot=(32, 16), body=36, gfx=("cell", 7, 9, 2.0), ai="neutral",
                drops=[("meat", 2, 3, 1.0), ("leather", 1, 1, .6), ("bone", 0, 1, .3)], knock=0.5),
    "wolf": _sp(name="Lobo", hostile=True, hp=36, dmg=8, speed=122, aggro=440, rng=42, windup=0.30, cd=1.0,
                foot=(30, 14), body=34, gfx=("cell", 6, 4, 2.0), ai="melee", wolf=True, knock=0.9,
                drops=[("meat", 1, 1, .7), ("bone", 0, 2, .5), ("leather", 0, 1, .4)]),
}


def surface_table(day):
    kinds = ["skeleton", "bones", "archer", "bat", "revenant"]
    w = [5, 4, 2 + min(day, 3), 1 + min(day, 3), 0 if day < 3 else 1 + min(day - 3, 2)]
    return kinds, w


def cave_table(day):
    kinds = ["skeleton", "bones", "archer", "bat", "revenant"]
    return kinds, [5, 3, 3, 4, 2 + min(day, 3)]


def animal_table(biome):
    if biome == "snow":
        return ["goat", "wolf", "rabbit"], [4, 2, 2]
    return ["cow", "pig", "chicken", "rabbit", "boar"], [3, 3, 3, 3, 1]


def spawn(level, kind, x, y):
    m = Mob(kind, x, y)
    level.mobs.append(m)
    return m


# ── sprites ──────────────────────────────────────────────────────────────────
_gfx = {}


def _anchor(frame):
    r = frame.get_bounding_rect()
    if r.w == 0:
        return frame.get_width() // 2, frame.get_height()
    return r.centerx, r.bottom


def _frames(kind):
    g = _gfx.get(kind)
    if g is not None:
        return g
    sp = SPECIES[kind]
    gx = sp["gfx"]
    if gx[0] == "strip":
        base = "enemies/SKELETON/PNG/skeleton_"
        sc = gx[1]
        anims = {"idle": assets.strip(base + "idle_strip6.png", 6, sc), "walk": assets.strip(base + "walk_strip8.png", 8, sc),
                 "attack": assets.strip(base + "attack_strip7.png", 7, sc), "hurt": assets.strip(base + "hurt_strip7.png", 7, sc),
                 "death": assets.strip(base + "death_strip10.png", 10, sc)}
        anchor = _anchor(anims["idle"][0])
        g = dict(anims=anims, anchor=anchor, kind="strip")
    elif gx[0] == "tiny":
        fr = assets.strip(f"enemies/{gx[1]}.png", 4, gx[2])
        g = dict(anims={"idle": fr, "walk": fr, "attack": fr, "hurt": fr, "death": fr}, anchor=_anchor(fr[0]), kind="tiny")
    else:
        _, cx, cy, sc = gx
        sheet = assets.load("animals/animals.png")
        cell = sheet.subsurface(pygame.Rect(cx * 32, cy * 32, 32, 32)).copy()
        r = cell.get_bounding_rect()
        cell = cell.subsurface(r).copy()
        spr = pygame.transform.scale(cell, (int(r.w * sc), int(r.h * sc)))
        g = dict(anims={"idle": [spr]}, anchor=(spr.get_width() // 2, spr.get_height()), kind="cell")
    _gfx[kind] = g
    return g


def clear_gfx_cache():
    _gfx.clear()


def _white(surf):
    return assets.tint(surf, (150, 150, 150), mult=False)


def _red(surf):
    return assets.tint(surf, (90, 0, 0), mult=False)


class Mob:
    def __init__(self, kind, x, y):
        self.kind = kind
        self.sp = SPECIES[kind]
        self.x, self.y = float(x), float(y)
        self.hp = self.max_hp = float(self.sp["hp"])
        self.hostile = bool(self.sp["hostile"])
        self.vx = self.vy = 0.0
        self.kx = self.ky = 0.0         # retroceso
        self.face = 1
        self.t = _rng.random() * 10
        self.state = "idle"
        self.state_t = _rng.uniform(0.5, 2.5)
        self.cd = _rng.uniform(0.2, 1.0)
        self.stun = 0.0
        self.flash = 0.0
        self.hit_t = 0.0
        self.windup_t = 0.0
        self.dying = False
        self.death_t = 0.0
        self.remove = False
        self.provoked = False
        self.flee_t = 0.0
        self.wdir = (0.0, 0.0)
        self.burn_t = 0.0
        self.orbit = _rng.uniform(0, math.tau)
        self.retreat = 0.0
        self.hover = 0.0
        self.anim_t = 0.0
        self.flying = bool(self.sp.get("flying"))
        fw, fh = self.sp["foot"]
        self.fw, self.fh = fw, fh
        self.hit_radius = max(18, fw * 0.8 + 6)

    # ── utilidades ────────────────────────────────────────────────────────
    @property
    def sort_y(self):
        return self.y

    def body_pos(self):
        return self.x, self.y - self.sp["body"] * 0.5 - (20 if self.flying else 0)

    def foot_rect(self):
        return pygame.Rect(int(self.x - self.fw / 2), int(self.y - self.fh), self.fw, self.fh)

    def _try_move(self, dx, dy, level):
        if self.flying:
            self.x += dx
            self.y += dy
            return dx != 0 or dy != 0
        moved = False
        if dx:
            r = self.foot_rect()
            r.x = int(self.x + dx - self.fw / 2)
            if not level.collides(r) and level.tile(int(r.centerx // TS), int(r.centery // TS)) not in (T.DEEP, T.LAVA):
                self.x += dx
                moved = True
        if dy:
            r = self.foot_rect()
            r.y = int(self.y + dy - self.fh)
            if not level.collides(r) and level.tile(int(r.centerx // TS), int(r.centery // TS)) not in (T.DEEP, T.LAVA):
                self.y += dy
                moved = True
        return moved

    def _steer(self, dirx, diry, speed, dt, level):
        """Mueve hacia (dirx, diry); si choca prueba desvíos laterales."""
        if dirx == 0 and diry == 0:
            return False
        ang = math.atan2(diry, dirx)
        for off in (0, 0.7, -0.7, 1.4, -1.4):
            a = ang + off
            mx, my = math.cos(a) * speed * dt, math.sin(a) * speed * dt
            if self._try_move(mx, my, level):
                if abs(mx) > 0.01:
                    self.face = 1 if mx > 0 else -1
                return True
        return False

    # ── combate ───────────────────────────────────────────────────────────
    def hurt(self, dmg, ang, level, player=None, knock=1.0):
        if self.dying:
            return False
        self.hp -= dmg
        self.flash = 0.14
        self.hit_t = 3.0
        self.stun = 0.22 * self.sp.get("knock", 1.0) + 0.08
        kn = 190 * self.sp.get("knock", 1.0) * knock
        self.kx, self.ky = math.cos(ang) * kn, math.sin(ang) * kn
        bx, by = self.body_pos()
        level.fx.chips(bx, by, "bone" if self.hostile and self.kind != "wolf" else "blood", 7)
        level.fx.text(bx, by - 26, str(int(round(dmg))), (255, 235, 150) if dmg < 20 else (255, 150, 90))
        audio.play("hit", 0.7)
        if not self.hostile:
            self.flee_t = 4.0
            if self.sp["ai"] == "neutral":
                self.provoked = True
                self.flee_t = 0
        if self.hp <= 0:
            self._die(level)
            return True
        return False

    def _die(self, level):
        self.dying = True
        self.death_t = 0.0
        self.hp = 0
        audio.play("enemy_die", 0.6)
        bx, by = self.body_pos()
        level.fx.chips(bx, by, "bone" if self.hostile else "blood", 14)
        for item, lo, hi, p in self.sp["drops"]:
            if _rng.random() <= p:
                n = _rng.randint(lo, hi)
                if n > 0:
                    scatter(level, self.x, self.y, item, n, 80)

    # ── actualización ─────────────────────────────────────────────────────
    def update(self, dt, level, player):
        self.t += dt
        self.anim_t += dt
        if self.flash > 0:
            self.flash -= dt
        if self.hit_t > 0:
            self.hit_t -= dt
        if self.dying:
            self.death_t += dt
            if self.death_t > 1.3:
                self.remove = True
            return
        d = dist(self.x, self.y, player.x, player.y)
        if d > (1700 if level.outdoors else 99999):
            self.remove = True
            return
        # retroceso
        if abs(self.kx) + abs(self.ky) > 8:
            self._try_move(self.kx * dt, self.ky * dt, level)
            self.kx *= max(0.0, 1 - 9 * dt)
            self.ky *= max(0.0, 1 - 9 * dt)
        # los no-muertos arden con el sol
        if self.sp.get("sun") and level.outdoors and level.darkness < 45:
            self.burn_t += dt
            if _rng.random() < dt * 5:
                level.fx.smoke(self.x, self.y - 30, 1)
            if self.burn_t >= 0.7:
                self.burn_t = 0
                self.hurt(4, 0, level, None, knock=0)
                if self.dying:
                    return
        if self.stun > 0:
            self.stun -= dt
            return
        self.cd -= dt
        ai = self.sp["ai"]
        if ai == "passive":
            self._ai_passive(dt, level, player, d)
        elif ai == "bat":
            self._ai_bat(dt, level, player, d)
        elif ai == "ranged":
            self._ai_ranged(dt, level, player, d)
        else:
            self._ai_melee(dt, level, player, d)

    def _wander(self, dt, level, speed_mult=0.45):
        self.state_t -= dt
        if self.state_t <= 0:
            if self.state == "walk" or _rng.random() < 0.3:
                self.state, self.state_t = "idle", _rng.uniform(1.0, 3.5)
            else:
                a = _rng.uniform(0, math.tau)
                self.wdir = (math.cos(a), math.sin(a))
                self.state, self.state_t = "walk", _rng.uniform(1.0, 3.0)
        if self.state == "walk":
            if not self._steer(self.wdir[0], self.wdir[1], self.sp["speed"] * speed_mult, dt, level):
                self.state_t = 0

    def _ai_passive(self, dt, level, player, d):
        if self.flee_t > 0:
            self.flee_t -= dt
            dx, dy = normalize(self.x - player.x, self.y - player.y)
            self.state = "walk"
            self._steer(dx, dy, self.sp["speed"] * 1.9, dt, level)
            return
        self._wander(dt, level)

    def _ai_melee(self, dt, level, player, d):
        sp = self.sp
        hostile_now = self.hostile or self.provoked
        if sp["ai"] == "neutral" and not self.provoked:
            self._wander(dt, level)
            return
        if self.state == "windup":
            self.windup_t -= dt
            if self.windup_t <= 0:
                self._strike(level, player)
            return
        if not hostile_now or player.dead or d > sp["aggro"] * (1.6 if self.provoked else 1.0):
            self._wander(dt, level)
            return
        if d > sp["aggro"] and not self.provoked:
            self._wander(dt, level)
            return
        dx, dy = normalize(player.x - self.x, player.y - self.y)
        if abs(dx) > 0.05:
            self.face = 1 if dx > 0 else -1
        if d <= sp["rng"]:
            self.state = "idle"
            if self.cd <= 0:
                self.state = "windup"
                self.windup_t = sp["windup"]
                self.cd = sp["cd"]
        else:
            self.state = "walk"
            self._steer(dx, dy, sp["speed"], dt, level)

    def _strike(self, level, player):
        sp = self.sp
        self.state = "idle"
        ang = math.atan2(player.y - self.y, player.x - self.x)
        bx, by = self.body_pos()
        level.fx.slash(bx + math.cos(ang) * 22, by + math.sin(ang) * 22, ang, (240, 240, 240))
        audio.play("swing", 0.5)
        if dist(self.x, self.y, player.x, player.y) <= sp["rng"] + 22 and not player.dead:
            player.hurt(sp["dmg"], ang, level, attacker=self)

    def _ai_ranged(self, dt, level, player, d):
        sp = self.sp
        if self.state == "windup":
            self.windup_t -= dt
            self.face = 1 if player.x > self.x else -1
            if self.windup_t <= 0:
                self.state = "idle"
                bx, by = self.body_pos()
                tx, ty = player.x, player.y - 24
                # ligero adelanto sobre la velocidad del jugador
                tt = dist(bx, by, tx, ty) / 430.0
                tx += player.vx * tt * 0.6
                ty += player.vy * tt * 0.6
                level.projectiles.append(Projectile(bx, by, math.atan2(ty - by, tx - bx), 430, sp["dmg"], "enemy", 760))
                audio.play("arrow", 0.6)
            return
        if player.dead or d > sp["aggro"]:
            self._wander(dt, level)
            return
        dx, dy = normalize(player.x - self.x, player.y - self.y)
        self.face = 1 if dx > 0 else -1
        if d < sp["rng"] * 0.55:
            self.state = "walk"
            self._steer(-dx, -dy, sp["speed"] * 1.1, dt, level)
        elif d > sp["rng"] * 0.95:
            self.state = "walk"
            self._steer(dx, dy, sp["speed"], dt, level)
        else:
            self.state = "walk"
            self._steer(-dy, dx, sp["speed"] * 0.5, dt, level)
        if self.cd <= 0 and d < sp["rng"] * 1.1:
            self.state = "windup"
            self.windup_t = sp["windup"]
            self.cd = sp["cd"]

    def _ai_bat(self, dt, level, player, d):
        sp = self.sp
        self.hover = math.sin(self.t * 7) * 5
        if player.dead or d > sp["aggro"]:
            self.orbit += dt
            self._steer(math.cos(self.orbit), math.sin(self.orbit * 1.3), sp["speed"] * 0.4, dt, level)
            return
        if self.retreat > 0:
            self.retreat -= dt
            dx, dy = normalize(self.x - player.x, self.y - player.y)
            self._steer(dx + math.sin(self.t * 5) * 0.6, dy, sp["speed"] * 1.2, dt, level)
            return
        self.orbit += dt * 2.4
        wob = math.sin(self.orbit) * 70
        px, py = player.x + math.cos(self.orbit * 0.8) * wob, player.y - 24 + math.sin(self.orbit * 1.1) * wob * 0.6
        dx, dy = normalize(px - self.x, py - (self.y - 20))
        self.face = 1 if dx > 0 else -1
        self._steer(dx, dy, sp["speed"], dt, level)
        if d < sp["rng"] + 14 and self.cd <= 0:
            self.cd = sp["cd"]
            self.retreat = 0.9
            player.hurt(sp["dmg"], math.atan2(player.y - self.y, player.x - self.x), level, attacker=self)

    # ── dibujo ────────────────────────────────────────────────────────────
    def draw(self, surf, cx, cy):
        g = _frames(self.kind)
        sx, sy = self.x - cx, self.y - cy
        sp = self.sp
        lift = (20 + self.hover) if self.flying else 0
        shadow_w = max(26, int(self.fw * 1.5))
        k = 1.0
        if self.dying:
            k = max(0.0, 1.0 - self.death_t / 1.3)
        surf.blit(assets.shadow(shadow_w, 10, int(80 * k)), (int(sx - shadow_w / 2), int(sy - 6)))
        anims = g["anims"]
        moving = self.state == "walk" or self.kx * self.kx + self.ky * self.ky > 400
        if g["kind"] == "strip":
            if self.dying:
                fr = anims["death"]
                img = fr[min(len(fr) - 1, int(self.death_t * 10))]
            elif self.state == "windup":
                fr = anims["attack"]
                p = 1.0 - max(0.0, self.windup_t) / max(0.01, sp["windup"])
                img = fr[min(len(fr) - 1, int(p * len(fr)))]
            elif self.flash > 0 and self.stun > 0:
                fr = anims["hurt"]
                img = fr[min(len(fr) - 1, int((0.22 - self.stun) * 25))]
            elif moving:
                fr = anims["walk"]
                img = fr[int(self.anim_t * 10) % len(fr)]
            else:
                fr = anims["idle"]
                img = fr[int(self.anim_t * 6) % len(fr)]
        elif g["kind"] == "tiny":
            fr = anims["walk"]
            img = fr[int(self.anim_t * (10 if moving or self.flying else 5)) % len(fr)]
        else:
            img = anims["idle"][0]
        ax, ay = g["anchor"]
        bob = 0
        sq = 1.0
        if g["kind"] != "strip":
            if self.sp.get("hop") and moving:
                bob = -abs(math.sin(self.anim_t * 14)) * 10
            elif moving:
                bob = -abs(math.sin(self.anim_t * 10)) * 3
                if g["kind"] == "cell":
                    sq = 1.0 + math.sin(self.anim_t * 10) * 0.03
            else:
                bob = math.sin(self.anim_t * 2.5) * 1.0
        transient = False
        if self.dying and g["kind"] != "strip":
            img = pygame.transform.rotate(img, -90 * min(1, self.death_t * 3) * (1 if self.face > 0 else -1))
            ax, ay = img.get_width() // 2, img.get_height() - 6
            transient = True
        flip = (self.face < 0) if g["kind"] != "tiny" else (self.face > 0)
        if g["kind"] == "cell":
            flip = self.face > 0       # los sprites de la hoja miran a la izquierda
        if flip:
            img = assets.flipx(img, cache=not transient)
            ax = img.get_width() - ax
        draw_img = img
        if not transient:
            if self.flash > 0:
                draw_img = _white(img)
            elif self.state == "windup" and int(self.t * 16) % 2 == 0:
                draw_img = _red(img)
        if self.dying and k < 1.0:
            draw_img = draw_img.copy()
            draw_img.set_alpha(int(255 * k))
        if sq != 1.0:
            draw_img = pygame.transform.scale(draw_img, (draw_img.get_width(), int(draw_img.get_height() * sq)))
        surf.blit(draw_img, (int(sx - ax), int(sy - ay + bob - lift)))
        if self.dying:
            return
        # indicador de ataque inminente y barra de vida
        if self.state == "windup":
            top = sy - sp["body"] - 22 - lift
            pygame.draw.rect(surf, (230, 60, 60), (int(sx - 2), int(top), 4, 9))
            pygame.draw.rect(surf, (230, 60, 60), (int(sx - 2), int(top + 11), 4, 3))
        if self.hit_t > 0 and self.hp < self.max_hp:
            w = 38
            bx, by = int(sx - w / 2), int(sy - sp["body"] - 14 - lift)
            pygame.draw.rect(surf, (18, 14, 18), (bx - 1, by - 1, w + 2, 7))
            pygame.draw.rect(surf, (120, 30, 34), (bx, by, w, 5))
            pygame.draw.rect(surf, (226, 72, 72), (bx, by, int(w * clamp(self.hp / self.max_hp, 0, 1)), 5))
