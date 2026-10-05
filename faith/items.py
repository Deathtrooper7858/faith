"""Registro central de objetos del juego y de las recetas de fabricación.
Para añadir un objeto basta con registrar una entrada en ITEMS."""
import pygame

O = "objects/"


class ItemDef:
    __slots__ = ("id", "name", "icon", "stack", "kind", "p")

    def __init__(self, id, name, icon, kind="material", stack=64, **props):
        self.id = id
        self.name = name
        self.icon = icon
        self.kind = kind
        self.stack = stack
        self.p = props

    def get(self, key, default=None):
        return self.p.get(key, default)

    @property
    def is_tool(self):
        return self.kind == "tool"

    @property
    def durability(self):
        return self.p.get("dur")


ITEMS = {}


def _reg(*a, **k):
    d = ItemDef(*a, **k)
    ITEMS[d.id] = d
    return d


# ── Materiales ───────────────────────────────────────────────────────────────
_reg("wood", "Madera", O + "wood.png")
_reg("stick", "Palo", O + "stick.png")
_reg("plank", "Tablón", O + "plank.png")
_reg("stone", "Piedra", O + "small_stone.png")
_reg("stone-brick", "Ladrillo", O + "stone-brick.png")
_reg("coal", "Carbón", O + "coal.png", fuel=1)
_reg("fiber", "Fibra", O + "fiber.png")
_reg("rose", "Rosa", O + "rose.png")
_reg("leather", "Cuero", O + "leather.png")
_reg("wool", "Lana", O + "wool.png")
_reg("bone", "Hueso", O + "bone.png")
_reg("iron-ore", "Mineral de hierro", O + "iron-ore.png")
_reg("gold-ore", "Mineral de oro", O + "gold-ore.png")
_reg("iron-ingot", "Lingote de hierro", O + "iron-ingot.png")
_reg("gold-ingot", "Lingote de oro", O + "gold-ingot.png")
_reg("sand", "Arena", "@sand")
_reg("glass", "Vidrio", O + "glass.png")
_reg("bottle", "Botella vacía", O + "bottle.png")

# ── Comida y bebida ──────────────────────────────────────────────────────────
_reg("apple", "Manzana", O + "apple.png", "food", food=12, hp=2)
_reg("green-apple", "Manzana verde", O + "green-apple.png", "food", food=18, hp=4)
_reg("meat", "Carne cruda", O + "meat.png", "food", food=8, hp=-3)
_reg("cooked-meat", "Carne asada", "@cooked-meat", "food", food=46, hp=10)
_reg("bwater", "Botella de agua", O + "bwater.png", "food", food=0, drink=55, returns="bottle")

# ── Herramientas por nivel ───────────────────────────────────────────────────
TIERS = {
    #         nivel potencia durab. daño  enfriamiento(ms)  color de texto
    "wood":  (1, 1.00, 45, 7, 540, (190, 150, 100)),
    "stone": (2, 1.60, 100, 11, 500, (170, 170, 175)),
    "iron":  (3, 2.40, 260, 16, 450, (200, 215, 235)),
    "gold":  (2, 3.20, 55, 13, 410, (255, 215, 80)),
}
TIER_NAMES = {"wood": "de madera", "stone": "de piedra", "iron": "de hierro", "gold": "de oro"}
TOOL_ICONS = {
    "axe": {"wood": "wood-axe", "stone": "stone-axe", "iron": "axe", "gold": "gold-axe"},
    "pickaxe": {"wood": "wood-pixkaxe", "stone": "stone-pickaxe", "iron": "iron-pickaxe", "gold": "gold-pickaxe"},
    "sword": {"wood": "wood-sword", "stone": "stone-sword", "iron": "iron-sword", "gold": "gold-sword"},
    "shovel": {"wood": "wood-shovel", "stone": "stone-shovel", "iron": "iron-shovel", "gold": "gold-shovel"},
}
TOOL_NAMES = {"axe": "Hacha", "pickaxe": "Pico", "sword": "Espada", "shovel": "Pala"}
# multiplicadores de daño y de tiempo de golpe según tipo de herramienta
TOOL_DMG = {"axe": 0.85, "pickaxe": 0.65, "sword": 1.0, "shovel": 0.45}
TOOL_CD = {"axe": 1.12, "pickaxe": 1.1, "sword": 0.95, "shovel": 1.0}

for _tool, _icons in TOOL_ICONS.items():
    for _tier, _icon in _icons.items():
        lvl, power, dur, dmg, cd, _c = TIERS[_tier]
        _reg(f"{_tier}-{_tool}", f"{TOOL_NAMES[_tool]} {TIER_NAMES[_tier]}", O + _icon + ".png",
             "tool", stack=1, tool=_tool, tier=lvl, tier_name=_tier, power=power, dur=dur,
             dmg=dmg * TOOL_DMG[_tool], cd=cd * TOOL_CD[_tool])

_reg("katana", "Katana ancestral", O + "katana.png", "tool", stack=1, tool="sword", tier=3,
     tier_name="iron", power=1.0, dur=320, dmg=27, cd=330, rare=True)
_reg("bow", "Arco", O + "bow.png", "tool", stack=1, tool="bow", tier=1, tier_name="wood",
     power=0.0, dur=160, dmg=15, cd=620, ranged=True)
_reg("arrow", "Flecha", O + "arrow.png", "ammo", stack=99)

# ── Armadura ─────────────────────────────────────────────────────────────────
ARMOR_DEF = {
    "wood": (1, 3, 2, 1), "iron": (4, 8, 5, 2), "gold": (6, 12, 8, 4),
}
ARMOR_SLOTS = ("helmet", "chest", "pants", "boots", "shield")
ARMOR_LABELS = {"helmet": "Casco", "chest": "Pecho", "pants": "Pantalón", "boots": "Botas", "shield": "Escudo"}
_ARMOR_NAMES = {"helmet": "Casco", "chest": "Peto", "pants": "Pantalones", "boots": "Botas"}
for _tier, _vals in ARMOR_DEF.items():
    for _i, _slot in enumerate(ARMOR_SLOTS[:4]):
        _icon = f"{_tier}-{'boots' if _slot == 'boots' else _slot}"
        if _tier == "wood" and _slot == "boots":
            _icon = "woof-boots"
        _reg(f"{_tier}-{_slot}", f"{_ARMOR_NAMES[_slot]} {TIER_NAMES[_tier]}", O + _icon + ".png",
             "armor", stack=1, slot=_slot, defense=_vals[_i], tier_name=_tier)
_reg("shield", "Escudo", O + "shield.png", "armor", stack=1, slot="shield", defense=6, tier_name="iron")

# ── Colocables ───────────────────────────────────────────────────────────────
_reg("crafting-table", "Mesa de crafteo", O + "crafting-table.png", "placeable", place="crafting_table")
_reg("oven", "Horno", O + "oven.png", "placeable", place="oven")
_reg("chest", "Cofre", O + "chest.png", "placeable", place="chest")
_reg("bed", "Cama", O + "bed.png", "placeable", place="bed")
_reg("torch", "Antorcha", O + "torch.png", "placeable", place="torch")
_reg("wood-wall", "Muro de madera", O + "wood-wall.png", "placeable", place="wood_wall")
_reg("stone-wall", "Muro de piedra", O + "brick-wall.png", "placeable", place="stone_wall")
_reg("door", "Puerta", O + "door.png", "placeable", place="door")
_reg("fence", "Valla", O + "fence.png", "placeable", place="fence")

SPECIAL_ICONS = {}  # "@nombre" → Surface generada procedimentalmente


def build_special_icons():
    """Iconos que no existen como archivo (arena, carne asada)."""
    from . import assets
    # Arena: montoncito con granos
    s = pygame.Surface((48, 48), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (170, 140, 86), (4, 24, 40, 18))
    pygame.draw.ellipse(s, (226, 203, 148), (6, 20, 36, 18))
    pygame.draw.ellipse(s, (240, 222, 170), (14, 16, 20, 12))
    for (x, y) in ((12, 28), (24, 24), (30, 31), (19, 21), (35, 27), (16, 33)):
        s.set_at((x, y), (176, 148, 92))
    SPECIAL_ICONS["@sand"] = s
    # Carne asada: la carne cruda teñida de marrón dorado
    meat = assets.load(O + "meat.png")
    SPECIAL_ICONS["@cooked-meat"] = assets.tint(meat, (255, 205, 150))


def icon_source(item_id):
    d = ITEMS[item_id]
    if d.icon.startswith("@"):
        if not SPECIAL_ICONS:
            build_special_icons()
        return SPECIAL_ICONS[d.icon]
    from . import assets
    return assets.load(d.icon)


_icon_cache = {}


def icon(item_id, size=44):
    """Icono cuadrado cacheado de un objeto."""
    key = (item_id, size)
    s = _icon_cache.get(key)
    if s is None:
        src = icon_source(item_id)
        sw, sh = src.get_size()
        k = min(size / sw, size / sh)
        w, h = max(1, round(sw * k)), max(1, round(sh * k))
        s = pygame.transform.smoothscale(src, (w, h)) if min(sw, sh) > 40 else pygame.transform.scale(src, (w, h))
        _icon_cache[key] = s
    return s


def describe(item_id, dur=None):
    """Líneas de texto para el tooltip: [(texto, color)]."""
    d = ITEMS[item_id]
    lines = []
    if d.kind == "tool" and d.get("tool") != "bow":
        lines.append((f"Nivel {d.get('tier')} · potencia x{d.get('power'):.1f}", (180, 200, 220)))
        lines.append((f"Daño {d.get('dmg'):.0f}", (230, 150, 140)))
    if d.get("tool") == "bow":
        lines.append((f"Daño {d.get('dmg'):.0f} · usa flechas", (230, 150, 140)))
    if dur is not None and d.durability:
        lines.append((f"Durabilidad {int(dur)}/{d.durability}", (160, 200, 160)))
    if d.kind == "armor":
        lines.append((f"Defensa +{d.get('defense')}", (160, 220, 160)))
    if d.kind == "food":
        bits = []
        if d.get("food"):
            bits.append(f"comida +{d.get('food')}")
        if d.get("drink"):
            bits.append(f"sed +{d.get('drink')}")
        if d.get("hp"):
            bits.append(f"vida {d.get('hp'):+d}")
        lines.append((" · ".join(bits), (240, 200, 140)))
    if d.kind == "placeable":
        lines.append(("Clic para colocar", (160, 180, 220)))
    if d.get("fuel"):
        lines.append(("Combustible del horno", (220, 170, 120)))
    return lines


# ═════════════════════════════════════════════════════════════════════════════
# Recetas
# ═════════════════════════════════════════════════════════════════════════════
class Recipe:
    __slots__ = ("result", "count", "ing", "station", "cat")

    def __init__(self, result, count, ing, station="hand", cat="basic"):
        self.result, self.count, self.ing, self.station, self.cat = result, count, ing, station, cat


RECIPES = []


def _rec(result, count, ing, station="hand", cat="basic"):
    RECIPES.append(Recipe(result, count, ing, station, cat))


CATEGORIES = [("basic", "Básico"), ("tools", "Herramientas"), ("combat", "Combate"),
              ("build", "Construcción"), ("cook", "Horno")]
STATION_NAMES = {"hand": "Manos", "table": "Mesa de crafteo", "oven": "Horno"}

# Básico (a mano)
_rec("plank", 2, {"wood": 1})
_rec("stick", 3, {"wood": 1})
_rec("crafting-table", 1, {"plank": 4}, "hand", "build")
_rec("torch", 2, {"stick": 1, "fiber": 2}, "hand", "build")
_rec("torch", 4, {"stick": 1, "coal": 1}, "hand", "build")
_rec("stone-brick", 2, {"stone": 2}, "hand", "basic")
_rec("bottle", 1, {"glass": 1}, "hand", "basic")

# Herramientas
for _tier, _mat, _s in (("wood", "plank", "hand"), ("stone", "stone", "table"),
                        ("iron", "iron-ingot", "table"), ("gold", "gold-ingot", "table")):
    _stn = "table" if _tier != "wood" else "hand"
    _rec(f"{_tier}-axe", 1, {_mat: 3, "stick": 2}, _stn, "tools")
    _rec(f"{_tier}-pickaxe", 1, {_mat: 3, "stick": 2}, _stn, "tools")
    _rec(f"{_tier}-shovel", 1, {_mat: 1, "stick": 2}, _stn, "tools")
    _rec(f"{_tier}-sword", 1, {_mat: 2, "stick": 1}, _stn, "combat")
_rec("bow", 1, {"stick": 3, "fiber": 3}, "table", "combat")
_rec("arrow", 4, {"stick": 1, "stone": 1, "fiber": 1}, "table", "combat")
_rec("shield", 1, {"plank": 4, "iron-ingot": 3}, "table", "combat")

# Armaduras
_ARMOR_COST = {"helmet": 5, "chest": 8, "pants": 7, "boots": 4}
for _tier, _mat in (("wood", "plank"), ("iron", "iron-ingot"), ("gold", "gold-ingot")):
    for _slot, _n in _ARMOR_COST.items():
        _rec(f"{_tier}-{_slot}", 1, {_mat: _n}, "table", "combat")

# Construcción
_rec("oven", 1, {"stone": 8}, "table", "build")
_rec("chest", 1, {"plank": 8}, "table", "build")
_rec("bed", 1, {"plank": 3, "wool": 3}, "table", "build")
_rec("wood-wall", 2, {"plank": 4}, "table", "build")
_rec("stone-wall", 2, {"stone-brick": 4}, "table", "build")
_rec("door", 1, {"plank": 4}, "table", "build")
_rec("fence", 2, {"stick": 4, "plank": 1}, "table", "build")

# Horno (el combustible se consume como ingrediente)
_rec("cooked-meat", 1, {"meat": 1, "wood": 1}, "oven", "cook")
_rec("iron-ingot", 1, {"iron-ore": 1, "coal": 1}, "oven", "cook")
_rec("gold-ingot", 1, {"gold-ore": 1, "coal": 1}, "oven", "cook")
_rec("glass", 1, {"sand": 2, "coal": 1}, "oven", "cook")

for _r in RECIPES:
    assert _r.result in ITEMS, _r.result
    for _k in _r.ing:
        assert _k in ITEMS, _k
