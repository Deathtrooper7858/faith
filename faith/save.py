"""Guardado y carga de partidas (JSON, escritura atómica con backup)."""
import json
import os
import shutil
import sys

VERSION = 2
_dir_cache = None
_last_env_dir = None


def save_dir():
    global _dir_cache, _last_env_dir
    env_dir = os.environ.get("FAITH_SAVE_DIR")
    if _dir_cache is not None and env_dir == _last_env_dir and os.path.isdir(_dir_cache):
        return _dir_cache

    _last_env_dir = env_dir
    base = env_dir
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

    _dir_cache = base
    return base


def save_path():
    return os.path.join(save_dir(), "savegame.json")


def bak_path():
    return os.path.join(save_dir(), "savegame.json.bak")


def exists():
    return os.path.isfile(save_path()) or os.path.isfile(bak_path())


def write(data):
    path = save_path()
    tmp = path + ".tmp"
    data["v"] = VERSION
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        # Preservar el archivo anterior como copia de respaldo (.bak)
        if os.path.isfile(path):
            try:
                shutil.copyfile(path, bak_path())
            except OSError:
                pass
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def read():
    for p in (save_path(), bak_path()):
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict) and d.get("v") == VERSION:
                return d
        except (OSError, ValueError):
            continue
    return None


def delete():
    for p in (save_path(), bak_path(), save_path() + ".tmp"):
        try:
            if os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass

