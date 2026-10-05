"""Lógica de fabricación (independiente de la interfaz)."""
from . import items, audio
from .entities.drops import scatter


def station_ok(recipe, level, player):
    st = recipe.station
    if st == "hand":
        return True
    kind = "crafting_table" if st == "table" else "oven"
    return level.station_near(player.x, player.y - 10, kind)


def can_craft(recipe, level, player):
    return station_ok(recipe, level, player) and player.inv.has(recipe.ing)


def max_crafts(recipe, player):
    return min(player.inv.count(k) // v for k, v in recipe.ing.items())


def craft(recipe, level, player, times=1, host=None):
    """Fabrica `times` veces. Devuelve cuántas se hicieron."""
    done = 0
    for _ in range(times):
        if not can_craft(recipe, level, player):
            break
        if not player.inv.consume(recipe.ing):
            break
        left = player.inv.add(recipe.result, recipe.count)
        if left:
            scatter(level, player.x, player.y - 10, recipe.result, left, 50)
        done += 1
    if done:
        player.stats["crafted"] += done
        audio.play("craft", 0.8)
        if recipe.station == "oven":
            for st in level.structs_near(player.x, player.y - 10, 64 * 3.2):
                if st.kind == "oven":
                    st.lit_ms = 4500
                    break
        if host:
            host.toast_item(recipe.result, recipe.count * done)
    return done
