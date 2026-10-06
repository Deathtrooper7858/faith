#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pygame-ce",
# ]
# ///
"""Faith of Surviving – punto de entrada."""
import asyncio
import os
import sys
import pygame

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def main():
    from faith.game import Game
    game = Game()
    await game.run_async()


def run_sync():
    from faith.game import Game
    Game().run()


if __name__ == "__main__":
    # In Pygbag / WebAssembly (Android WebView), an event loop is already running.
    if sys.platform == "emscripten" or "pygbag" in sys.modules:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            asyncio.ensure_future(main())
        else:
            asyncio.run(main())
    else:
        # Desktop native (Windows .exe, macOS, Linux)
        run_sync()
