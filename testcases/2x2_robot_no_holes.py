"""
2x2_robot_no_holes.py
-------------------
Test case for a 2x2 robot scenario without holes.
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


class TwoByTwoNoHoles(TestCase):
    name = "2x2_robot_no_holes"

    def setup(self):
        grid = Grid(rows=7, cols=9)
        grid.add_rect_boundary()
        grid.add_boundary(row=1, col=3, height=2, width=1)
        grid.add_boundary(row=1, col=6, height=2, width=2)
        grid.add_boundary(row=5, col=3, height=1, width=5)

        robot_size = 2
        pos_a = (2, 1)
        pos_b = (4, 1)
        a = Robot("A", robot_size, *pos_a)
        b = Robot("B", robot_size, *pos_b)
        ws = Workspace(grid, a, b)
        return ws, pos_b, pos_a
