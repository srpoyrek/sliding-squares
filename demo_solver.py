from src.grid import Grid
from src.robot import Robot
from src.solver import Solver
from src.validator import Validator
from src.visualizer import draw_sequence, plots_path
from src.workspace import Workspace

grid = Grid(rows=7, cols=9)
grid.add_boundary()
grid.add_obstacle(row=1, col=3, height=2, width=1)
grid.add_obstacle(row=1, col=6, height=2, width=2)
grid.add_obstacle(row=5, col=3, height=1, width=5)

robot_size = 2
pos_a = (2, 1)
pos_b = (4, 1)
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
draw_sequence(
    grid, snapshots, titles=vr.titles, save_path=plots_path("solution.png"), robot_size=a.n
)
