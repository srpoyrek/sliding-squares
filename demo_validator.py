"""
demo_validator.py
-----------------
Manual demo for the validator.
"""

from src.grid import Grid
from src.robot import Robot
from src.validator import Validator
from src.workspace import Workspace

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
    "U",
    "S",
    "U",
    "R",
    "R",
    "R",
    "R",
    "R",
    "S",
    "D",
    "D",
    "R",
    "R",
    "R",
    "U",
    "U",
    "S",
    "L",
    "L",
    "L",
    "L",
    "L",
    "U",
    "U",
    "S",
    "D",
    "D",
    "L",
    "L",
    "L",
    "D",
    "S",
    "D",
]
result = validator.run(path, plot=True, plot_name="validator_correct_path")
print(result)

# reset
a.row, a.col = 1, 1
b.row, b.col = 1, 3
ws._control = a.label

# Test 2: invalid move mid-path
bad_path = ["S", "L", "U", "S", "R", "U", "S", "D", "L"]
result = validator.run(bad_path, plot=True, plot_name="validator_invalid_path")
print(result)
