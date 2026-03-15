from src.grid import Grid
from src.robot import Robot
from src.solver import Solver
from src.validator import Validator
from src.visualizer import draw_sequence, plots_path
from src.workspace import Workspace

# 1. define grid and robots
tiles = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1],
    [1, 1, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 1],
    [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 1],
    [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
]

grid = Grid(tiles)
b = Robot("B", 4, 4, 3)
a = Robot("A", 4, 8, 1)
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
draw_sequence(
    grid, snapshots, titles=vr.titles, save_path=plots_path("solution.png"), robot_size=a.n
)
