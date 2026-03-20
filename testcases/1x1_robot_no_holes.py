"""
1x1_robot_no_holes.py
-------------------
Trivial 1x1 swap with a pocket.
"""

from __future__ import annotations

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
        grid = Grid(rows=3, cols=5)
        grid.add_boundary(row=2, col=0, height=1, width=5)
        grid.add_boundary(row=0, col=0, height=2, width=1)
        grid.add_boundary(row=0, col=4, height=2, width=1)
        grid.add_boundary(row=0, col=1, height=1, width=1)
        grid.add_boundary(row=0, col=3, height=1, width=1)
        robot_size = 1
        pos_a = (1, 1)
        pos_b = (1, 2)
        a = Robot("A", robot_size, *pos_a)
        b = Robot("B", robot_size, *pos_b)
        ws = Workspace(grid, a, b)
        return ws, pos_b, pos_a
