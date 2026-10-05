#!/usr/bin/env python3
"""Faith of Surviving – punto de entrada."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def main():
    from faith.game import Game
    game = Game()
    await game.run_async()


def run_sync():
    from faith.game import Game
    Game().run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        run_sync()
