"""
solver.py
---------
Uses BFS to find the minimum number of control switches
to swap two robots in a given workspace.
Returns minimum switches and the actual command path.
"""

from __future__ import annotations

from src.bfs import bfs
from src.workspace import Workspace


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

        # Try both possible initial controllers — either robot can be the first
        # mover. The true minimum-switch count is min over both starts.
        outs = []
        for initial in (self.ws.robot_a, self.ws.robot_b):
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
