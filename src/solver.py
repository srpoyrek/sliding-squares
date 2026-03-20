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

        out = bfs(self.ws, self.goal_a, self.goal_b)

        if out is None:
            return result

        result.solvable = True
        result.switches = out["switches"]
        result.path = out["path"]
        result.visited = out["visited"]
        return result
