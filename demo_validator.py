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
    [1, 1, 0, 1, 1],
    [1, 0, 0, 0, 1],
    [1, 1, 1, 1, 1],
]
grid = Grid(tiles)
a = Robot("A", 1, 1, 1)
b = Robot("B", 1, 1, 3)
ws = Workspace(grid, a, b)

validator = Validator(ws, goal_a=(1, 3), goal_b=(1, 1))

# Test 1: correct path
path = ["S", "L", "U", "S", "R", "R", "S", "D", "L"]
result = validator.run(path, plot=True, plot_name="validator_correct_path")
print(result)

# reset
a.row, a.col = 1, 1
b.row, b.col = 1, 3
ws._control = "A"

# Test 2: invalid move mid-path
bad_path = ["S", "L", "U", "S", "R", "U", "S", "D", "L"]
result = validator.run(bad_path, plot=True, plot_name="validator_invalid_path")
print(result)
