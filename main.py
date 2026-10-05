#!/usr/bin/env python3
"""Faith of Surviving – punto de entrada."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    from faith.game import Game
    Game().run()


if __name__ == "__main__":
    main()
