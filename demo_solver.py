from __future__ import annotations

from src.grid import Grid
from src.robot import Robot
from src.solver import Solver
from src.validator import Validator
from src.visualizer import draw_sequence
from src.workspace import Workspace

grid = Grid(rows=23, cols=33)
grid.add_rect_boundary()
grid.add_boundary(row=1, col=1, height=4, width=20)
grid.add_boundary(row=5, col=1, height=1, width=17)
grid.add_boundary(row=6, col=17, height=3, width=1)
grid.add_boundary(row=1, col=25, height=2, width=1)
grid.add_boundary(row=1, col=26, height=1, width=6)
grid.add_boundary(row=2, col=30, height=2, width=2)
grid.add_boundary(row=19, col=1, height=3, width=8)
grid.add_boundary(row=20, col=13, height=2, width=19)
grid.add_boundary(row=17, col=14, height=3, width=18)
grid.add_boundary(row=14, col=15, height=3, width=2)

grid.add_hole(row=10, col=5, height=1, width=8)
grid.add_hole(row=11, col=5, height=1, width=6)
grid.add_hole(row=12, col=5, height=3, width=1)
grid.add_hole(row=12, col=10)

grid.add_hole(row=11, col=21, height=1, width=7)
grid.add_hole(row=9, col=22, height=2, width=1)
grid.add_hole(row=8, col=27, height=3, width=1)

robot_size = 4
pos_a = (2, 26)
pos_b = (6, 23)
a = Robot("A", robot_size, *pos_a)
b = Robot("B", robot_size, *pos_b)
ws = Workspace(grid, a, b)

# 2. solve — get minimum switches + path
result = Solver(ws, goal_a=(b.row, b.col), goal_b=(a.row, a.col)).solve()
print(result)
print(result.path)

# 4. validate the path
vr = Validator(ws, goal_a=(b.row, b.col), goal_b=(a.row, a.col)).run(result.path, plot=False)
print(vr)  # ValidationResult(valid=True, switches=2)

# 5. plot
snapshots = [[ra, rb] for ra, rb in vr.snapshots]
draw_sequence(grid, snapshots, titles=vr.titles, save_dir="plots/solution/", robot_size=a.n)
