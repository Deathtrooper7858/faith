"""Pantalla de inventario: mochila, equipo, fabricación y cofres (arrastrar y soltar)."""
import pygame
from .. import items, crafting, audio, settings as S
from ..inventory import slot_click, quick_move
from ..items import ITEMS, RECIPES, CATEGORIES, ARMOR_SLOTS, ARMOR_LABELS, TIERS
from ..entities.drops import scatter
from ..entities import player as P
from . import widgets as W
from .hud import draw_slot, draw_item_in

SLOT, GAP = 52, 4
STEP = SLOT + GAP
ROW_H = 58


class InventoryUI:
    def __init__(self):
        self.open = False
        self.chest = None
        self.cat = 0
        self.scroll = 0
        self.slots = []            # [(Rect, kind, idx)]
        self.rows = []             # [(Rect, recipe)]
        self.tab_rects = []
        self.panel = pygame.Rect(0, 0, 0, 0)
        self.close_btn = pygame.Rect(0, 0, 0, 0)
        self.sort_btn = pygame.Rect(0, 0, 0, 0)
        self.hover_slot = None
        self.hover_recipe = None
        self.craft_flash = 0.0
        self._dim_surface = pygame.Surface((S.SCREEN_W, S.SCREEN_H), pygame.SRCALPHA)
        self._dim_surface.fill((4, 6, 14, 150))
        self._char_frames = None
        self._dim_icons = {}

    # ── apertura ──────────────────────────────────────────────────────────
    def show(self, game, chest=None, tab=None):
        self.open = True
        self.chest = chest
        if tab is not None:
            self.cat = tab
        self.scroll = 0
        self._layout(game)
        audio.play("click", 0.6)

    def close(self, game):
        inv = game.player.inv
        if inv.cursor:                                   # devolver la pila del cursor
            left = inv.add(inv.cursor.id, inv.cursor.count, inv.cursor.dur)
            if left:
                scatter(game.level, game.player.x, game.player.y - 10, inv.cursor.id, left, 60, inv.cursor.dur)
            inv.cursor = None
        self.open = False
        self.chest = None
        audio.play("click", 0.5)

    # ── geometría ─────────────────────────────────────────────────────────
    def _layout(self, game):
        self.slots = []
        self.tab_rects = []
        if self.chest is None:
            self.panel = pygame.Rect(96, 64, 1088, 592)
            gx, gy = 392, 150
            for r in range(S.GRID_ROWS):
                for c in range(S.GRID_COLS):
                    self.slots.append((pygame.Rect(gx + c * STEP, gy + r * STEP, SLOT, SLOT), "inv", S.HOTBAR_SLOTS + r * S.GRID_COLS + c))
            hy = gy + S.GRID_ROWS * STEP + 34
            for c in range(S.HOTBAR_SLOTS):
                self.slots.append((pygame.Rect(gx + c * STEP, hy, SLOT, SLOT), "inv", c))
            ax, ay = 132, 150
            for i, name in enumerate(ARMOR_SLOTS[:4]):
                self.slots.append((pygame.Rect(ax, ay + i * (SLOT + 10), SLOT, SLOT), "armor", i))
            self.slots.append((pygame.Rect(ax + 178, ay, SLOT, SLOT), "armor", 4))
            tx = 884
            tw = 292 // 5
            for i in range(len(CATEGORIES)):
                self.tab_rects.append(pygame.Rect(tx + i * (tw + 2), 128, tw, 30))
            self.list_rect = pygame.Rect(tx, 170, 292, 464)
        else:
            self.panel = pygame.Rect(386, 34, 508, 606)
            gx = 414
            cy = 104
            for r in range(S.GRID_ROWS):
                for c in range(S.GRID_COLS):
                    self.slots.append((pygame.Rect(gx + c * STEP, cy + r * STEP, SLOT, SLOT), "chest", r * S.GRID_COLS + c))
            iy = cy + S.GRID_ROWS * STEP + 56
            for r in range(S.GRID_ROWS):
                for c in range(S.GRID_COLS):
                    self.slots.append((pygame.Rect(gx + c * STEP, iy + r * STEP, SLOT, SLOT), "inv", S.HOTBAR_SLOTS + r * S.GRID_COLS + c))
            hy = iy + S.GRID_ROWS * STEP + 20
            for c in range(S.HOTBAR_SLOTS):
                self.slots.append((pygame.Rect(gx + c * STEP, hy, SLOT, SLOT), "inv", c))
        self.close_btn = pygame.Rect(self.panel.right - 44, self.panel.top + 14, 32, 32)
        self.sort_btn = pygame.Rect(self.panel.right - 146, self.panel.top + 14, 94, 32)

    # ── acceso a contenedores ─────────────────────────────────────────────
    def _list(self, game, kind):
        if kind == "inv":
            return game.player.inv.slots
        if kind == "chest":
            return self.chest.items
        return None

    def _armor_accept(self, st, idx):
        return st is None or (st.d.kind == "armor" and st.d.get("slot") == ARMOR_SLOTS[idx])

    # ── eventos ───────────────────────────────────────────────────────────
    def handle_event(self, e, game):
        inv = game.player.inv
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_ESCAPE, pygame.K_i, pygame.K_TAB, pygame.K_e):
                self.close(game)
                return True
            if e.key == pygame.K_r:
                if self.chest is not None:
                    from ..inventory import compact_and_sort
                    compact_and_sort(self.chest.items)
                else:
                    game.player.inv.sort_bag()
                audio.play("click", 0.45)
                return True
            if pygame.K_1 <= e.key <= pygame.K_8 and self.hover_slot and self.hover_slot[1] != "armor":
                idx = e.key - pygame.K_1
                kind, i = self.hover_slot[1], self.hover_slot[2]
                lst = self._list(game, kind)
                if lst is not None and inv.cursor is None:
                    lst[i], inv.slots[idx] = inv.slots[idx], lst[i]
                    audio.play("click", 0.4)
                return True
        elif e.type == pygame.MOUSEWHEEL:
            if self.chest is None and self.list_rect.collidepoint(pygame.mouse.get_pos()):
                self.scroll = max(0, self.scroll - e.y)
            return True
        elif hasattr(pygame, "FINGERDOWN") and e.type == pygame.FINGERDOWN:
            pos = (int(e.x * S.SCREEN_W), int(e.y * S.SCREEN_H))
            self._click(pos, 1, game)
            return True
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3):
            self._click(e.pos, e.button, game)
            return True
        return False

    def _click(self, pos, button, game):
        if hasattr(self, "close_btn") and self.close_btn.collidepoint(pos):
            self.close(game)
            return
        if hasattr(self, "sort_btn") and self.sort_btn.collidepoint(pos):
            if self.chest is not None:
                from ..inventory import compact_and_sort
                compact_and_sort(self.chest.items)
            else:
                game.player.inv.sort_bag()
            audio.play("click", 0.45)
            return
        inv = game.player.inv
        keys = pygame.key.get_pressed()
        shift = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
        for rect, kind, idx in self.slots:
            if rect.collidepoint(pos):
                if kind == "armor":
                    self._armor_click(inv, idx, button)
                else:
                    lst = self._list(game, kind)
                    if shift and button == 1 and lst[idx]:
                        self._shift_move(game, kind, idx)
                    else:
                        inv.cursor = slot_click(lst, idx, inv.cursor, button)
                        audio.play("click", 0.35)
                return
        if self.chest is None:
            for i, r in enumerate(self.tab_rects):
                if r.collidepoint(pos):
                    self.cat, self.scroll = i, 0
                    audio.play("click", 0.5)
                    return
            for rect, rec in self.rows:
                if rect.collidepoint(pos) and button in (1, 3):
                    n = 1 if button == 1 and not shift else (max(1, min(crafting.max_crafts(rec, game.player), 10)) if shift else 1)
                    if not crafting.can_craft(rec, game.level, game.player):
                        audio.play("click", 0.3)
                        if crafting.station_ok(rec, game.level, game.player):
                            game.notify("Faltan materiales", S.C_BAD)
                        else:
                            game.notify("Necesitas " + items.STATION_NAMES[rec.station].lower() + " cerca", S.C_BAD)
                        return
                    crafting.craft(rec, game.level, game.player, n, game)
                    self.craft_flash = 0.25
                    return
        if not self.panel.collidepoint(pos) and button == 1:
            if inv.cursor:
                c = inv.cursor
                scatter(game.level, game.player.x, game.player.y - 10, c.id, c.count, 90, c.dur)
                inv.cursor = None
            else:
                self.close(game)

    def _armor_click(self, inv, idx, button):
        if button != 1:
            return
        slot = ARMOR_SLOTS[idx]
        cur = inv.armor[slot]
        if inv.cursor:
            if inv.cursor.d.kind == "armor" and inv.cursor.d.get("slot") == slot:
                inv.armor[slot], inv.cursor = inv.cursor, cur
                audio.play("place", 0.6)
        elif cur:
            inv.cursor, inv.armor[slot] = cur, None
            audio.play("click", 0.4)

    def _shift_move(self, game, kind, idx):
        inv = game.player.inv
        lst = self._list(game, kind)
        st = lst[idx]
        if kind == "inv" and st.d.kind == "armor":              # equipar rápido
            slot = st.d.get("slot")
            old = inv.armor[slot]
            inv.armor[slot] = st
            lst[idx] = old
            audio.play("place", 0.6)
            return
        if self.chest is not None:
            dst = self.chest.items if kind == "inv" else inv.slots
            quick_move(lst, idx, [dst])
        else:
            hot, grid = inv.slots[:S.HOTBAR_SLOTS], inv.slots[S.HOTBAR_SLOTS:]
            # mover entre hotbar y mochila
            if idx < S.HOTBAR_SLOTS:
                tmp = grid
                quick_move(inv.slots, idx, [tmp])
            else:
                quick_move(inv.slots, idx, [hot])
        audio.play("click", 0.35)

    # ── dibujo ────────────────────────────────────────────────────────────
    def _dim_icon(self, item_id, size):
        key = (item_id, size)
        ic = self._dim_icons.get(key)
        if ic is None:
            base = items.icon(item_id, size)
            ic = base.copy()
            ic.set_alpha(150)
            if len(self._dim_icons) > 120:
                self._dim_icons.clear()
            self._dim_icons[key] = ic
        return ic

    def draw(self, surf, game, dt):
        p = game.player
        inv = p.inv
        self.craft_flash = max(0.0, self.craft_flash - dt)
        surf.blit(self._dim_surface, (0, 0))
        W.panel(surf, self.panel, 238, 16)
        mouse = pygame.mouse.get_pos()
        if hasattr(self, "close_btn"):
            hov_x = self.close_btn.collidepoint(mouse)
            W.panel(surf, self.close_btn, 220, 6, (180, 70, 70) if hov_x else (110, 50, 50), (40, 20, 20), shadow=False)
            W.text(surf, "X", self.close_btn.center, 22, (255, 230, 230), "center")
        if hasattr(self, "sort_btn"):
            hov_s = self.sort_btn.collidepoint(mouse)
            W.panel(surf, self.sort_btn, 220, 6, (90, 100, 140) if hov_s else (48, 54, 76), (24, 28, 40), shadow=False)
            W.text(surf, "Ordenar [R]", self.sort_btn.center, 18, S.C_TEXT if not hov_s else S.C_GOLD, "center")
        self.hover_slot = None
        self.hover_recipe = None
        pr = self.panel
        if self.chest is None:
            W.text(surf, "Equipo", (132, 100), 32, S.C_GOLD)
            W.text(surf, "Mochila", (392, 100), 32, S.C_GOLD)
            W.text(surf, "Barra rápida", (392, 150 + S.GRID_ROWS * STEP + 8), 22, S.C_DIM)
            W.text(surf, "Fabricación", (884, 100), 32, S.C_GOLD)
            self._draw_character(surf, p)
        else:
            W.text(surf, self.chest.name, (414, 62), 32, S.C_GOLD)
            W.text(surf, "Mochila", (414, 104 + S.GRID_ROWS * STEP + 20), 28, S.C_GOLD)
        # ranuras
        for rect, kind, idx in self.slots:
            hov = rect.collidepoint(mouse)
            if kind == "armor":
                st = inv.armor[ARMOR_SLOTS[idx]]
                fill, edge = (58, 44, 26), (140, 108, 56)
                if idx == 4:
                    fill, edge = (24, 44, 64), (66, 106, 150)
                draw_slot(surf, rect, st, hover=hov, fill=fill, edge=edge)
                if st is None:
                    W.text(surf, ARMOR_LABELS[ARMOR_SLOTS[idx]], rect.center, 15, (150, 136, 100), "center")
            else:
                lst = self._list(game, kind)
                st = lst[idx]
                sel = kind == "inv" and idx == inv.selected and idx < S.HOTBAR_SLOTS
                draw_slot(surf, rect, st, selected=sel, hover=hov)
            if hov:
                self.hover_slot = (rect, kind, idx)
        # fabricación
        if self.chest is None:
            self._draw_crafting(surf, game, mouse)
            W.text(surf, f"Defensa total: {inv.defense()}", (132, 150 + 4 * (SLOT + 10) + 6), 24, (160, 220, 160))
            W.text(surf, "Clic: coger/soltar · Clic der.: dividir · Mayús+clic: mover/equipar · 1-8: atajo · R: ordenar",
                   (pr.x + 24, pr.bottom - 30), 19, S.C_DIM)
        else:
            W.text(surf, "Mayús+clic: mover rápido · 1-8: atajo a la barra · R: ordenar", (pr.x + 22, pr.bottom - 30), 19, S.C_DIM)
        # cursor con pila
        if inv.cursor:
            ic = items.icon(inv.cursor.id, 40)
            surf.blit(ic, (mouse[0] - ic.get_width() // 2, mouse[1] - ic.get_height() // 2))
            if inv.cursor.count > 1:
                W.text(surf, str(inv.cursor.count), (mouse[0] + 20, mouse[1] + 18), 22, S.C_TEXT, "bottomright")
        elif self.hover_slot:
            _r, kind, idx = self.hover_slot
            st = inv.armor[ARMOR_SLOTS[idx]] if kind == "armor" else self._list(game, kind)[idx]
            if st:
                self._item_tooltip(surf, st, mouse)
        elif self.hover_recipe:
            self._recipe_tooltip(surf, self.hover_recipe, mouse, game)

    def _item_tooltip(self, surf, st, mouse):
        d = st.d
        tier = d.get("tier_name")
        col = TIERS[tier][5] if tier in TIERS else S.C_TEXT
        if d.get("rare"):
            col = (255, 160, 70)
        lines = [(d.name, col)] + items.describe(st.id, st.dur)
        W.tooltip(surf, lines, mouse)

    def _recipe_tooltip(self, surf, rec, mouse, game):
        d = ITEMS[rec.result]
        tier = d.get("tier_name")
        col = TIERS[tier][5] if tier in TIERS else S.C_TEXT
        lines = [(f"{d.name}" + (f" x{rec.count}" if rec.count > 1 else ""), col)] + items.describe(rec.result)
        if rec.station != "hand":
            ok = crafting.station_ok(rec, game.level, game.player)
            lines.append((("Estación disponible: " if ok else "Necesitas: ") + items.STATION_NAMES[rec.station], S.C_GOOD if ok else S.C_BAD))
        W.tooltip(surf, lines, mouse)

    def _draw_character(self, surf, p):
        if self._char_frames is None:
            F = P.frames()
            self._char_frames = [
                pygame.transform.scale(F.base[(P.ROW_IDLE["down"], i)], (192, 192))
                for i in range(6)
            ]
        fr = int(pygame.time.get_ticks() / 260) % 6
        big = self._char_frames[fr]
        cx, cy = 132 + 150, 176
        surf.blit(big, (cx - 96, cy + 50))

    def _draw_crafting(self, surf, game, mouse):
        p = game.player
        # estaciones cercanas
        has_t = game.level.station_near(p.x, p.y - 10, "crafting_table")
        has_o = game.level.station_near(p.x, p.y - 10, "oven")
        sx = 1056
        W.text(surf, "Mesa", (sx, 104), 20, S.C_GOOD if has_t else (130, 90, 90))
        W.text(surf, "Horno", (sx + 62, 104), 20, S.C_GOOD if has_o else (130, 90, 90))
        for i, (key, label) in enumerate(CATEGORIES):
            r = self.tab_rects[i]
            sel = i == self.cat
            hov = r.collidepoint(mouse)
            pygame.draw.rect(surf, (52, 58, 86) if sel else (30, 33, 48) if not hov else (42, 46, 66), r, border_radius=6)
            pygame.draw.rect(surf, S.C_GOLD if sel else (70, 76, 104), r, 2, border_radius=6)
            short = {"basic": "Básico", "tools": "Herram.", "combat": "Combate", "build": "Constr.", "cook": "Horno"}[key]
            W.text(surf, short, r.center, 17, S.C_GOLD if sel else S.C_TEXT, "center")
        key = CATEGORIES[self.cat][0]
        recs = [r for r in RECIPES if r.cat == key]
        recs.sort(key=lambda r: (not crafting.can_craft(r, game.level, p), not crafting.station_ok(r, game.level, p)))
        per = self.list_rect.h // ROW_H
        self.scroll = max(0, min(self.scroll, max(0, len(recs) - per)))
        self.rows = []
        y = self.list_rect.y
        for rec in recs[self.scroll:self.scroll + per]:
            rect = pygame.Rect(self.list_rect.x, y, self.list_rect.w, ROW_H - 4)
            can = crafting.can_craft(rec, game.level, p)
            st_ok = crafting.station_ok(rec, game.level, p)
            hov = rect.collidepoint(mouse)
            if hov:
                self.hover_recipe = rec
            fill = (40, 62, 44) if can else (30, 33, 46)
            if hov:
                fill = (56, 84, 60) if can else (42, 46, 64)
            pygame.draw.rect(surf, fill, rect, border_radius=8)
            pygame.draw.rect(surf, (96, 170, 100) if can else (66, 70, 96), rect, 2, border_radius=8)
            ic = items.icon(rec.result, 38) if can else self._dim_icon(rec.result, 38)
            surf.blit(ic, (rect.x + 8, rect.y + (rect.h - ic.get_height()) // 2))
            nm = ITEMS[rec.result].name + (f"  x{rec.count}" if rec.count > 1 else "")
            W.text(surf, nm, (rect.x + 56, rect.y + 6), 21, S.C_TEXT if st_ok else (140, 130, 120))
            ix = rect.x + 56
            for k, v in rec.ing.items():
                have = p.inv.count(k)
                ok = have >= v
                mic = items.icon(k, 20)
                surf.blit(mic, (ix, rect.y + 28))
                s = W.render(f"{min(have, 99)}/{v}", 17, S.C_GOOD if ok else S.C_BAD)
                surf.blit(s, (ix + 21, rect.y + 31))
                ix += 21 + s.get_width() + 8
            if not st_ok:
                tag = "Mesa" if rec.station == "table" else "Horno"
                W.text(surf, tag, (rect.right - 8, rect.y + 7), 17, (220, 150, 90), "topright")
            self.rows.append((rect, rec))
            y += ROW_H
        if len(recs) > per:
            W.text(surf, f"{self.scroll + 1}-{min(len(recs), self.scroll + per)} / {len(recs)}  (rueda del ratón)",
                   (self.list_rect.x, self.list_rect.bottom + 4), 17, S.C_DIM)
