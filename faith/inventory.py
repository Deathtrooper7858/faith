"""Modelo de inventario: pilas, hotbar, cuadrícula, armadura y operaciones de ranura.
Lógica pura (no depende de pygame) para poder probarla fácilmente."""
from . import settings as S
from .items import ITEMS, ARMOR_SLOTS


class ItemStack:
    __slots__ = ("id", "count", "dur")

    def __init__(self, item_id, count=1, dur=None):
        d = ITEMS[item_id]
        self.id = item_id
        self.count = int(count)
        self.dur = dur if dur is not None else d.durability

    @property
    def d(self):
        return ITEMS[self.id]

    @property
    def max(self):
        return ITEMS[self.id].stack

    def clone(self, count=None):
        return ItemStack(self.id, self.count if count is None else count, self.dur)

    def to_json(self):
        return [self.id, self.count, self.dur]

    @staticmethod
    def from_json(v):
        if not v or v[0] not in ITEMS:
            return None
        return ItemStack(v[0], v[1], v[2])


class Inventory:
    TOTAL = S.HOTBAR_SLOTS + S.GRID_COLS * S.GRID_ROWS

    def __init__(self):
        self.slots = [None] * self.TOTAL          # 0..7 = hotbar, resto = cuadrícula
        self.armor = {k: None for k in ARMOR_SLOTS}
        self.selected = 0
        self.cursor = None                        # pila en el "ratón" (arrastre)

    # ── acceso ────────────────────────────────────────────────────────────
    @property
    def hotbar(self):
        return self.slots[:S.HOTBAR_SLOTS]

    def held(self):
        return self.slots[self.selected]

    def held_id(self):
        h = self.held()
        return h.id if h else None

    def select(self, i):
        self.selected = i % S.HOTBAR_SLOTS

    def scroll(self, direction):
        self.selected = (self.selected + direction) % S.HOTBAR_SLOTS

    def armor_list(self):
        return [self.armor[k] for k in ARMOR_SLOTS]

    # ── añadir / quitar ───────────────────────────────────────────────────
    def add(self, item_id, count=1, dur=None):
        """Añade objetos; devuelve cuántos NO cupieron."""
        d = ITEMS[item_id]
        left = count
        if d.stack > 1:
            for s in self.slots:
                if s and s.id == item_id and s.count < d.stack:
                    take = min(d.stack - s.count, left)
                    s.count += take
                    left -= take
                    if left == 0:
                        return 0
        for i, s in enumerate(self.slots):
            if s is None:
                take = min(d.stack, left)
                self.slots[i] = ItemStack(item_id, take, dur)
                left -= take
                if left == 0:
                    return 0
        return left

    def room_for(self, item_id, count=1):
        d = ITEMS[item_id]
        free = 0
        for s in self.slots:
            if s is None:
                free += d.stack
            elif s.id == item_id and d.stack > 1:
                free += d.stack - s.count
            if free >= count:
                return True
        return free >= count

    def count(self, item_id):
        return sum(s.count for s in self.slots if s and s.id == item_id)

    def has(self, needs):
        return all(self.count(k) >= v for k, v in needs.items())

    def remove(self, item_id, n=1):
        if self.count(item_id) < n:
            return False
        # primero de las últimas ranuras para conservar la hotbar
        for i in range(len(self.slots) - 1, -1, -1):
            s = self.slots[i]
            if s and s.id == item_id:
                take = min(s.count, n)
                s.count -= take
                n -= take
                if s.count <= 0:
                    self.slots[i] = None
                if n == 0:
                    return True
        return True

    def consume(self, needs):
        if not self.has(needs):
            return False
        for k, v in needs.items():
            self.remove(k, v)
        return True

    def consume_held(self, n=1):
        h = self.held()
        if h:
            h.count -= n
            if h.count <= 0:
                self.slots[self.selected] = None

    def wear_held(self, amount=1):
        """Gasta durabilidad de la herramienta en mano. True si se rompió."""
        h = self.held()
        if h and h.dur is not None:
            h.dur -= amount
            if h.dur <= 0:
                self.slots[self.selected] = None
                return True
        return False

    # ── armadura ──────────────────────────────────────────────────────────
    def defense(self):
        total = 0
        for st in self.armor.values():
            if st:
                total += st.d.get("defense", 0)
        return total

    def has_shield(self):
        return self.armor.get("shield") is not None

    # ── serialización ─────────────────────────────────────────────────────
    def to_json(self):
        return {
            "slots": [s.to_json() if s else None for s in self.slots],
            "armor": {k: (v.to_json() if v else None) for k, v in self.armor.items()},
            "selected": self.selected,
        }

    def load_json(self, data):
        self.slots = [None] * self.TOTAL
        for i, v in enumerate(data.get("slots", [])[:self.TOTAL]):
            self.slots[i] = ItemStack.from_json(v)
        for k in ARMOR_SLOTS:
            self.armor[k] = ItemStack.from_json(data.get("armor", {}).get(k))
        self.selected = int(data.get("selected", 0)) % S.HOTBAR_SLOTS


# ═════════════════════════════════════════════════════════════════════════════
# Operaciones de ranura (compartidas por inventario, cofres y armadura)
# ═════════════════════════════════════════════════════════════════════════════
def slot_click(slots, idx, cursor, button, accept=None):
    """Lógica de clic en una ranura. Devuelve la nueva pila del cursor.
    button 1 = izq (coger/soltar todo/intercambiar), 3 = der (mitad / uno)."""
    cur = slots[idx]
    if accept and cursor and not accept(cursor):
        return cursor
    if button == 1:
        if cursor is None:
            slots[idx] = None
            return cur
        if cur is None:
            slots[idx] = cursor
            return None
        if cur.id == cursor.id and cur.max > 1:
            room = cur.max - cur.count
            moved = min(room, cursor.count)
            cur.count += moved
            cursor.count -= moved
            return cursor if cursor.count > 0 else None
        slots[idx] = cursor
        return cur
    if button == 3:
        if cursor is None:
            if cur is None:
                return None
            half = (cur.count + 1) // 2
            taken = cur.clone(half)
            cur.count -= half
            if cur.count <= 0:
                slots[idx] = None
            return taken
        if cur is None:
            slots[idx] = cursor.clone(1)
            cursor.count -= 1
            return cursor if cursor.count > 0 else None
        if cur.id == cursor.id and cur.count < cur.max:
            cur.count += 1
            cursor.count -= 1
            return cursor if cursor.count > 0 else None
    return cursor


def quick_move(src, idx, dst_lists):
    """Shift+clic: mueve la pila de src[idx] a la primera lista que tenga hueco."""
    st = src[idx]
    if not st:
        return
    for dst in dst_lists:
        if dst is src:
            continue
        for j, d in enumerate(dst):
            if d and d.id == st.id and st.max > 1 and d.count < d.max:
                m = min(d.max - d.count, st.count)
                d.count += m
                st.count -= m
                if st.count <= 0:
                    src[idx] = None
                    return
        for j, d in enumerate(dst):
            if d is None:
                dst[j] = st
                src[idx] = None
                return
