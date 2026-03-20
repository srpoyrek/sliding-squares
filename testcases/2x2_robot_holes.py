"""
2x2_robot_holes.py
-------------------
Test case for a 2x2 robot scenario with holes.
swap robot positions
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.grid import Grid
from src.robot import Robot
from src.test_case import TestCase
from src.workspace import Workspace


class TwoByTwoHoles(TestCase):
    name = "2x2_robot_holes"

    def setup(self):
        grid = Grid(rows=17, cols=12)
        grid.add_rect_boundary()
        grid.add_boundary(row=1, col=1, height=2, width=2)
        grid.add_boundary(row=8, col=1, height=8, width=5)
        grid.add_boundary(row=8, col=6, height=3, width=1)
        grid.add_boundary(row=15, col=8, height=1, width=3)
        grid.add_boundary(row=9, col=9, height=1, width=2)
        grid.add_hole(row=12, col=8)
        grid.add_hole(row=5, col=3)
        grid.add_hole(row=3, col=5)
        grid.add_hole(row=6, col=8)
        grid.add_hole(row=3, col=6, height=3, width=3)

        robot_size = 2
        pos_a = (12, 6)
        pos_b = (14, 6)
        a = Robot("A", robot_size, *pos_a)
        b = Robot("B", robot_size, *pos_b)
        ws = Workspace(grid, a, b)
        return ws, pos_b, pos_a
