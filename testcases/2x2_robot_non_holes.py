"""
2x2_robot_non_holes.py
-------------------
Test case for a 2x2 robot scenario without holes.
swap robot positions
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.grid import Grid
from src.robot import Robot
from src.test_case import TestCase
from src.workspace import Workspace


class TwoByTwoNonHoles(TestCase):
    name = "2x2_robot_non_holes"

    def setup(self):
        tiles = [
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 1, 0, 0, 1, 1, 1],
            [1, 0, 0, 1, 0, 0, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1],
        ]

        robot_size = 2
        pos_a = (2, 1)
        pos_b = (4, 1)
        grid = Grid(tiles)
        a = Robot("A", robot_size, *pos_a)
        b = Robot("B", robot_size, *pos_b)
        ws = Workspace(grid, a, b)
        return ws, pos_b, pos_a
