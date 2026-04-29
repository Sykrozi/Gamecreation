import sys
import os

# Ensure game/ is on the path so relative imports work
sys.path.insert(0, os.path.dirname(__file__))

from main import Game

if __name__ == "__main__":
    Game().run()
