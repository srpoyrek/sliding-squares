"""
1x1_robot_no_holes.py
-------------------
Trivial 1x1 swap with a pocket.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.grid import Grid
from src.robot import Robot
from src.test_case import TestCase
from src.workspace import Workspace


class OneByOneNoHoles(TestCase):
    name = "1x1_robot_no_holes"

    def setup(self):
        tiles = [
            [1, 1, 0, 1, 1],
            [1, 0, 0, 0, 1],
            [1, 1, 1, 1, 1],
        ]
        robot_size = 1
        pos_a = (1, 1)
        pos_b = (1, 2)
        grid = Grid(tiles)
        a = Robot("A", robot_size, *pos_a)
        b = Robot("B", robot_size, *pos_b)
        ws = Workspace(grid, a, b)
        return ws, pos_b, pos_a
