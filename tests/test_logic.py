"""Pruebas unitarias de la lógica pura (sin ventana). Ejecutar:  python -m unittest discover -s tests"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
try:
    import pygame  # noqa: F401
except ImportError:                       # entorno sin pygame: usar el shim de pruebas
    sys.path.insert(0, os.path.join(ROOT, "tests", "pygame_shim"))
    import pygame  # noqa: F401

from faith import items, inventory as I, settings as S
from faith.world import terrain as T, cavegen
from faith.util import Noise, hash01


class TestItems(unittest.TestCase):
    def test_recipes_reference_valid_items(self):
        for r in items.RECIPES:
            self.assertIn(r.result, items.ITEMS)
            for k in r.ing:
                self.assertIn(k, items.ITEMS)

    def test_every_item_has_existing_icon_or_special(self):
        for d in items.ITEMS.values():
            if d.icon.startswith("@"):
                continue
            self.assertTrue(os.path.isfile(os.path.join(ROOT, "assets", "images", *d.icon.split("/"))), d.icon)

    def test_tool_tiers_scale(self):
        a, b, c = (items.ITEMS[f"{t}-pickaxe"] for t in ("wood", "stone", "iron"))
        self.assertLess(a.get("tier"), b.get("tier"))
        self.assertLess(b.get("tier"), c.get("tier"))
        self.assertLess(a.get("power"), c.get("power"))


class TestInventory(unittest.TestCase):
    def test_add_stacks_and_overflow(self):
        inv = I.Inventory()
        self.assertEqual(inv.add("wood", 100), 0)
        self.assertEqual(inv.count("wood"), 100)
        self.assertEqual(inv.slots[0].count, 64)
        full = I.Inventory()
        full.slots = [I.ItemStack("stone", 64) for _ in full.slots]
        self.assertEqual(full.add("wood", 5), 5)

    def test_tools_do_not_stack(self):
        inv = I.Inventory()
        inv.add("stone-axe", 2)
        self.assertEqual(sum(1 for s in inv.slots if s), 2)

    def test_consume_and_has(self):
        inv = I.Inventory()
        inv.add("plank", 7)
        self.assertTrue(inv.has({"plank": 7}))
        self.assertFalse(inv.has({"plank": 8}))
        self.assertTrue(inv.consume({"plank": 3}))
        self.assertEqual(inv.count("plank"), 4)
        self.assertFalse(inv.consume({"plank": 9}))
        self.assertEqual(inv.count("plank"), 4)

    def test_slot_click_split_merge(self):
        slots = [I.ItemStack("wood", 10), None, I.ItemStack("wood", 60)]
        cur = I.slot_click(slots, 0, None, 3)                # clic derecho: coge la mitad
        self.assertEqual((cur.count, slots[0].count), (5, 5))
        cur = I.slot_click(slots, 1, cur, 1)                 # soltar en vacío
        self.assertIsNone(cur)
        self.assertEqual(slots[1].count, 5)
        cur = I.slot_click(slots, 2, I.ItemStack("wood", 10), 1)   # fusionar con tope 64
        self.assertEqual(slots[2].count, 64)
        self.assertEqual(cur.count, 6)

    def test_durability_wear_breaks_tool(self):
        inv = I.Inventory()
        inv.add("wood-axe", 1)
        inv.slots[0].dur = 2
        self.assertFalse(inv.wear_held(1))
        self.assertTrue(inv.wear_held(1))
        self.assertIsNone(inv.slots[0])

    def test_json_roundtrip(self):
        inv = I.Inventory()
        inv.add("iron-sword", 1)
        inv.add("apple", 5)
        inv.armor["helmet"] = I.ItemStack("iron-helmet")
        inv.selected = 3
        inv2 = I.Inventory()
        inv2.load_json(inv.to_json())
        self.assertEqual(inv2.count("apple"), 5)
        self.assertEqual(inv2.armor["helmet"].id, "iron-helmet")
        self.assertEqual(inv2.selected, 3)
        self.assertEqual(inv2.defense(), inv.defense())

    def test_defense_sums_armor(self):
        inv = I.Inventory()
        inv.armor["chest"] = I.ItemStack("gold-chest")
        inv.armor["boots"] = I.ItemStack("iron-boots")
        self.assertEqual(inv.defense(), items.ITEMS["gold-chest"].get("defense") + items.ITEMS["iron-boots"].get("defense"))


class TestWorld(unittest.TestCase):
    def test_noise_range_and_determinism(self):
        n1, n2 = Noise(42), Noise(42)
        for i in range(200):
            v = n1.fbm(i * 0.31, i * 0.17, 3)
            self.assertTrue(0.0 <= v <= 1.0)
            self.assertEqual(v, n2.fbm(i * 0.31, i * 0.17, 3))
        self.assertNotEqual(Noise(1).value(3.3, 4.4), Noise(2).value(3.3, 4.4))

    def test_hash_handles_negative_coords(self):
        self.assertTrue(0.0 <= hash01(3, -17, -5) <= 1.0)

    def test_spawn_area_is_safe_grass(self):
        for seed in (1, 99, 12345, 777777):
            t = T.Terrain(seed)
            for dx in range(-6, 7):
                for dy in range(-6, 7):
                    if dx * dx + dy * dy < 49:
                        self.assertEqual(t.tile(dx, dy), T.GRASS)

    def test_terrain_is_deterministic(self):
        a, b = T.Terrain(5), T.Terrain(5)
        for x in range(-40, 40, 7):
            for y in range(-40, 40, 5):
                self.assertEqual(a.tile(x, y), b.tile(x, y))

    def test_cave_is_connected_and_has_resources(self):
        for seed in range(6):
            g = cavegen.generate(seed)
            floor = set(g["floor"])
            self.assertGreater(len(floor), 800)
            self.assertIn(g["spawn"], floor)
            self.assertEqual(g["tiles"][g["door"]], T.CAVE_DOOR)
            self.assertGreater(len(g["ores"]), 5)
            # todo suelo es alcanzable desde la entrada
            seen, stack = {g["spawn"]}, [g["spawn"]]
            while stack:
                x, y = stack.pop()
                for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (x + d[0], y + d[1])
                    if n in floor and n not in seen:
                        seen.add(n)
                        stack.append(n)
            self.assertEqual(seen, floor)


if __name__ == "__main__":
    unittest.main()
