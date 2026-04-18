"""
solver.py
---------
Uses BFS to find the minimum number of control switches
to swap two robots in a given workspace.
Returns minimum switches and the actual command path.
"""

from __future__ import annotations

from src.bfs import bfs_bidirectional
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

        # Bidirectional BFS: seeds BOTH initial controllers in forward layer 0
        # and BOTH final controllers in backward layer 0, so we get min-switches
        # over any choice of first/last mover in a single run.
        out = bfs_bidirectional(self.ws, self.goal_a, self.goal_b)
        if out is None:
            return result

        # Derive which robot moved first from the returned path so the
        # validator/downstream replay starts with the correct ctrl.
        path = out["path"]
        first_cmd = next((c for c in path if c in ("U", "D", "L", "R")), None)
        first_switch_index = next((i for i, c in enumerate(path) if c == "S"), len(path))
        # If path starts with 'S', the initial controller was the non-A robot;
        # otherwise A (since the BFS treats A as default when no switch yet).
        # Simpler: read the direction of the very first move relative to both
        # robots' starting positions to infer the mover; fallback to A.
        initial_mover = self.ws.robot_a
        if first_cmd is not None and first_switch_index > 0:
            # The first move is made by whichever initial-controller was chosen.
            # We determine it by simulating: is the first cmd legal for A or B?
            cand_a, cand_b = self.ws.robot_a, self.ws.robot_b
            # Heuristic — choose based on which robot can legally execute first_cmd.
            # If ambiguous, default to A.
            try:
                if self.ws.can_move(cand_a, first_cmd):
                    initial_mover = cand_a
                elif self.ws.can_move(cand_b, first_cmd):
                    initial_mover = cand_b
            except Exception:
                pass
        elif first_switch_index == 0:
            # Path starts with 'S', so the first-controller didn't move (but the
            # seed was A by convention). After the switch the other robot moves.
            initial_mover = self.ws.robot_a
        self.ws._control = initial_mover

        result.solvable = True
        result.switches = out["switches"]
        result.path = out["path"]
        result.visited = out["visited"]
        return result
