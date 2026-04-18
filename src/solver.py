"""
solver.py
---------
Uses BFS to find the minimum number of control switches
to swap two robots in a given workspace.
Returns minimum switches and the actual command path.
"""

from __future__ import annotations

from src.bfs import bfs
from src.symmetry import build_transform_tables, is_label_swap_symmetric
from src.workspace import Workspace

# Cache transform tables per (rows, cols, n) so repeated Solver calls on
# different workspaces of the same shape share the same tables.
_TRANSFORM_CACHE: dict = {}


def _get_transforms(rows: int, cols: int, n: int):
    key = (rows, cols, n)
    if key not in _TRANSFORM_CACHE:
        _TRANSFORM_CACHE[key] = build_transform_tables(rows, cols, n)
    return _TRANSFORM_CACHE[key]


class SolverResult:
    def __init__(self):
        self.switches = None
        self.solvable = False
        self.path = []  # flat command list e.g. ['R','U','S','L','L','S','D','R']
        self.visited = {}  # state -> switch count

    def __repr__(self):
        if not self.solvable:
            return "SolverResult(solvable=False)"
        return (
            f"SolverResult(solvable=True, switches={self.switches}, "
            f"path_length={len(self.path)})"
        )


class Solver:
    def __init__(self, workspace: Workspace, goal_a: tuple[int, int], goal_b: tuple[int, int]):
        self.ws = workspace
        self.goal_a = goal_a
        self.goal_b = goal_b

    def solve(self) -> SolverResult:
        result = SolverResult()

        # If the workspace is label-swap symmetric (there's a spatial transform
        # that swaps A and B's starts/goals and preserves walls), then BFS with
        # A first and BFS with B first must give the same switch count — skip
        # the second call.
        rows, cols = self.ws.grid.rows, self.ws.grid.cols
        n = self.ws.robot_a.n
        n_kinds, cell_table, pos_table = _get_transforms(rows, cols, n)
        symmetric = is_label_swap_symmetric(
            self.ws.grid.tiles,
            rows,
            cols,
            self.ws.robot_a.position(),
            self.ws.robot_b.position(),
            self.goal_a,
            self.goal_b,
            n_kinds,
            cell_table,
            pos_table,
        )
        initials = (self.ws.robot_a,) if symmetric else (self.ws.robot_a, self.ws.robot_b)

        outs = []
        for initial in initials:
            self.ws._control = initial
            out = bfs(self.ws, self.goal_a, self.goal_b)
            if out is not None:
                outs.append((initial, out))

        if not outs:
            return result

        best_initial, best = min(outs, key=lambda x: x[1]["switches"])
        # Leave workspace's initial controller set to the winning choice so
        # downstream validation replays the path from the correct starting control.
        self.ws._control = best_initial
        result.solvable = True
        result.switches = best["switches"]
        result.path = best["path"]
        result.visited = best["visited"]
        return result
