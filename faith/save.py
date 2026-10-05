"""Guardado y carga de partidas (JSON, escritura atómica)."""
import json
import os
import sys

VERSION = 2


def save_dir():
    base = os.environ.get("FAITH_SAVE_DIR")
    if not base:
        if sys.platform.startswith("win"):
            base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "FaithOfSurviving")
        else:
            base = os.path.join(os.path.expanduser("~"), ".faith_of_surviving")
    try:
        os.makedirs(base, exist_ok=True)
        test = os.path.join(base, ".w")
        with open(test, "w") as f:
            f.write("1")
        os.remove(test)
    except OSError:
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "saves")
        os.makedirs(base, exist_ok=True)
    return base


def save_path():
    return os.path.join(save_dir(), "savegame.json")


def exists():
    return os.path.isfile(save_path())


def write(data):
    path = save_path()
    tmp = path + ".tmp"
    data["v"] = VERSION
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(tmp, path)


def read():
    try:
        with open(save_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
        if d.get("v") != VERSION:
            return None
        return d
    except (OSError, ValueError):
        return None


def delete():
    try:
        os.remove(save_path())
    except OSError:
        pass
