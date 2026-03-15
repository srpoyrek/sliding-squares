"""
workspace.py
------------
The grid + both robots + all movement rules.

Owns:
  - the Grid
  - robot A and robot B
  - all queries that require knowing BOTH robots or the grid

This is the only place where:
  - robot positions are changed
  - collision between robots is checked
  - valid moves are determined
"""

from src.grid import Grid
from src.robot import Robot
from src.state import State

DIRECTIONS = {
    "U": (-1, 0),
    "D": (1, 0),
    "L": (0, -1),
    "R": (0, 1),
}

COMMANDS = {
    "UP": "U",
    "DOWN": "D",
    "LEFT": "L",
    "RIGHT": "R",
    "CONTROL_SWITCH": "S",
}


class Workspace:
    """
    Combines a Grid with two robots and enforces movement rules.
    """

    def __init__(self, grid: Grid, robot_a: Robot, robot_b: Robot):
        self.grid = grid
        self.robot_a = robot_a
        self.robot_b = robot_b
        self._control = self.robot_a  # which robot is currently being controlled

    # ── Grid queries ────────────────────────────────────

    def robot_fits_at(self, robot: Robot, row: int, col: int) -> bool:
        """
        Would robot fit at (row, col) without hitting any obstacle or wall?
        Does NOT check collision with the other robot.
        """
        for dr in range(robot.n):
            for dc in range(robot.n):
                if self.grid.is_obstacle(row + dr, col + dc):
                    return False
        return True

    # ── Robot-vs-robot queries ───────────────────────────

    def robots_overlap(
        self, row_a: int, col_a: int, n_a: int, row_b: int, col_b: int, n_b: int
    ) -> bool:
        """
        Would two robots overlap?
        Each robot has its own size (n_a, n_b) — they don't have to match.
        """
        return not (
            row_a + n_a <= row_b
            or row_b + n_b <= row_a
            or col_a + n_a <= col_b
            or col_b + n_b <= col_a
        )

    # ── Movement ────────────────────────────────────────

    def can_move(self, robot: Robot, direction: str) -> bool:
        """
        Can `robot` move one step in `direction`?
        Checks: grid fit + no collision with the other robot.
        """
        if direction not in DIRECTIONS:
            return False

        dr, dc = DIRECTIONS[direction]
        new_row = robot.row + dr
        new_col = robot.col + dc

        # Check grid
        if not self.robot_fits_at(robot, new_row, new_col):
            return False

        # Check collision with other robot
        other = self.robot_b if robot.label == self.robot_a.label else self.robot_a
        if self.robots_overlap(new_row, new_col, robot.n, other.row, other.col, other.n):
            return False

        return True

    def do_move(self, robot: Robot, direction: str) -> bool:
        """
        Move `robot` one step in `direction` if valid.
        Returns True if move was made, False if invalid.
        """
        if not self.can_move(robot, direction):
            return False

        dr, dc = DIRECTIONS[direction]
        robot.row += dr
        robot.col += dc
        return True

    # ── State snapshot (for BFS) ────────────────────────

    def get_state(self) -> State:
        """
        Return a frozen State snapshot of current robot positions.
        BFS uses this to track visited situations.
        """
        from src.state import State

        return State(
            pos_a=self.robot_a.position(), pos_b=self.robot_b.position(), control=self._control
        )

    def load_state(self, state: State):
        """
        Restore robot positions from a State snapshot.
        BFS uses this to backtrack.
        """
        self.robot_a.row, self.robot_a.col = state.pos_a
        self.robot_b.row, self.robot_b.col = state.pos_b
        self._control = state.control

    # ── Dunder ──────────────────────────────────────────

    def __repr__(self):
        return (
            f"Workspace(grid={self.grid}, "
            f"A={self.robot_a.position()}, "
            f"B={self.robot_b.position()})"
        )


# ── Sanity check ────────────────────────────────────────

if __name__ == "__main__":
    import matplotlib.pyplot as plt

    from src.directories import plots_path
    from src.visualizer import draw

    tiles = [
        [1, 1, 1, 1, 1],
        [1, 1, 0, 1, 1],
        [1, 0, 0, 0, 1],
        [1, 1, 1, 1, 1],
    ]
    grid = Grid(tiles)
    a = Robot("A", 1, 2, 1)
    b = Robot("B", 1, 2, 2)
    ws = Workspace(grid, a, b)

    print(ws)
    print("can A move R?", ws.can_move(a, "R"))  # True
    print("can A move U?", ws.can_move(a, "U"))  # False (obstacle)
    print("can B move L?", ws.can_move(b, "L"))  # True
    print("can B move R?", ws.can_move(b, "R"))  # False (wall)

    # Snapshot before moves
    s0 = ws.get_state()
    print("\nstate before moves:", s0)

    ws.do_move(b, "L")
    ws.do_move(b, "U")

    s1 = ws.get_state()
    print("state after moves: ", s1)

    # Restore
    ws.load_state(s0)
    print("state after restore:", ws.get_state())

    # Visualize
    out = plots_path("workspace_test.png")
    draw(grid, robots=[a, b], title="Workspace sanity check", show=False)
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Saved {out}")
