"""
5x5_robot_non_holes.py
-------------------
Test case for a 5x5 robot scenario without holes.
swap robot positions
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.grid import Grid
from src.robot import Robot
from src.test_case import TestCase
from src.workspace import Workspace


class FiveByFiveNonHoles(TestCase):
    name = "5x5_robot_non_holes"

    def setup(self):
        grid = Grid(rows=27, cols=20)
        grid.add_rect_boundary()
        grid.add_boundary(row=1, col=1, height=3, width=8)

        robot_size = 5
        pos_a = (20, 10)
        pos_b = (15, 14)
        a = Robot("A", robot_size, *pos_a)
        b = Robot("B", robot_size, *pos_b)
        ws = Workspace(grid, a, b)
        return ws, pos_b, pos_a
