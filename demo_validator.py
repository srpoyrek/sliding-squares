"""
demo_validator.py
-----------------
Manual demo for the validator.
"""

from __future__ import annotations

from src.grid import Grid
from src.path_resolver import PathResolver
from src.robot import Robot
from src.validator import Validator
from src.workspace import COMMANDS, Workspace

tiles = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 0, 0, 1, 0, 0, 1, 1, 1],
    [1, 0, 0, 1, 0, 0, 1, 1, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1],
]

grid = Grid(tiles)
a = Robot("A", 2, 2, 1)
b = Robot("B", 2, 4, 1)
ws = Workspace(grid, a, b)

validator = Validator(ws, goal_a=(4, 1), goal_b=(2, 1))

# Test 1: correct path
path = [
    "US",
    "U5RS",
    "2D3R2US",
    "5L2US",
    "2D3LDS",
    "D",
]
resolver = PathResolver(valid_commands=set(COMMANDS.values()))
path_resolved = resolver.resolve(path)
result = validator.run(path_resolved, plot=True, plot_name="validator_correct_path")
print(result)

# reset
a.row, a.col = 1, 1
b.row, b.col = 1, 3
ws._control = a

# Test 2: invalid move mid-path
bad_path = ["S", "LUS", "RUS", "DL"]
bad_path_resolved = resolver.resolve(bad_path)
result = validator.run(bad_path_resolved, plot=True, plot_name="validator_invalid_path")
print(result)
