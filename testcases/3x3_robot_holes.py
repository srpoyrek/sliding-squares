"""
3x3_robot_holes.py
-------------------
Test case for a 3x3 robot scenario with holes.
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


class ThreeByThreeHoles(TestCase):
    name = "3x3_robot_holes"

    def setup(self):
        grid = Grid(rows=21, cols=19)
        grid.add_rect_boundary()
        grid.add_boundary(row=1, col=1, height=5, width=9)
        grid.add_boundary(row=1, col=10, height=4, width=1)
        grid.add_boundary(row=4, col=11)
        grid.add_boundary(row=1, col=15, height=2, width=3)
        grid.add_boundary(row=17, col=1, height=3, width=3)
        grid.add_boundary(row=6, col=16, height=14, width=2)
        grid.add_boundary(row=12, col=11, height=8, width=5)

        grid.add_hole(row=9, col=4, height=4, width=4)
        grid.add_hole(row=9, col=8)
        grid.add_hole(row=13, col=4)
        grid.add_hole(row=16, col=7)
        grid.add_hole(row=8, col=12)

        robot_size = 3
        pos_a = (3, 14)
        pos_b = (1, 11)
        a = Robot("A", robot_size, *pos_a)
        b = Robot("B", robot_size, *pos_b)
        ws = Workspace(grid, a, b)
        return ws, pos_b, pos_a
