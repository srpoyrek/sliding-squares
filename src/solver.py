"""
solver.py
---------
Finds the minimum number of control switches to swap two robots in a given
workspace, and the actual command path. Three exact strategies: the mirror and
bidirectional BFS searches over states, and the clique-map finder, which builds
`SwapSolvability`'s map and reads the minimum off a walk over cliques.
"""

from __future__ import annotations

from src.bfs import bfs_bidirectional, bfs_mirror
from src.solvability import SwapSolvability
from src.workspace import Workspace


class SolverResult:
    def __init__(self):
        self.switches = None
        self.solvable = False
        self.path = []  # flat command list e.g. ['R','U','S','L','L','S','D','R']
        self.visited = {}  # state -> switch count (the searches only)
        # States the strategy held: len(visited) for the searches, the clique
        # map's state count for "solvability" — one axis for every strategy.
        self.states = None

    def __repr__(self):
        if not self.solvable:
            return "SolverResult(solvable=False)"
        return (
            f"SolverResult(solvable=True, switches={self.switches}, "
            f"path_length={len(self.path)})"
        )


class Solver:
    def __init__(
        self,
        workspace: Workspace,
        goal_a: tuple[int, int],
        goal_b: tuple[int, int],
        strategy: str = "mirror",
    ):
        """`strategy` selects the solver. "mirror" grows one forward tree and
        reads every backward distance off it via the A<->B relabelling;
        "bidirectional" grows the older forward/backward pair and is kept so
        the two can be cross-checked against each other; "solvability" builds
        the clique map and reads the minimum off a breadth-first walk over the
        cliques — exact per `SwapSolvability.shortest_trail`'s argument, and
        its path replays like any search's. The mirror search applies only
        when the goal is the start with the robots exchanged — with any other
        goal `solve` falls back to bidirectional whatever the setting, since
        `bfs_mirror` rejects such a goal outright."""
        self.ws = workspace
        self.goal_a = goal_a
        self.goal_b = goal_b
        self.strategy = strategy

    def solve(self, need_path: bool = True) -> SolverResult:
        result = SolverResult()

        # Both searches seed BOTH initial controllers, so min-switches over any
        # choice of first mover comes out of a single run; the mirror search
        # gets the last mover from the same seeding via the relabelling, the
        # bidirectional one from seeding both final controllers backwards.
        #
        # need_path=False is the fast path for callers that only need
        # (solvable, switches) — it skips path reconstruction, the visited-dict
        # copy, and the first-mover inference below.
        start_a = self.ws.robot_a.position()
        start_b = self.ws.robot_b.position()
        swapped_goal = self.goal_a == start_b and self.goal_b == start_a
        if self.strategy == "solvability":
            # The clique-map finder. No visited dict exists; `states` is the
            # map's own state count. Control at step 0 is the first segment's
            # mover, read off the segments the same way the searches report
            # their initial mover.
            sol = SwapSolvability.for_workspace(self.ws)
            segments = sol.shortest_trail((start_a, start_b), (self.goal_a, self.goal_b))
            if segments is None:
                return result
            result.solvable = True
            result.switches = max(0, len(segments) - 1)
            result.states = sol.states
            if not need_path:
                return result
            result.path = sol.commands(segments)
            first = segments[0][0] if segments else "A"
            self.ws._control = self.ws.robot_a if first == "A" else self.ws.robot_b
            return result
        if self.strategy == "mirror" and swapped_goal:
            out = bfs_mirror(self.ws, self.goal_a, self.goal_b, need_path=need_path)
        else:
            out = bfs_bidirectional(self.ws, self.goal_a, self.goal_b, need_path=need_path)
        if out is None:
            return result

        if not need_path:
            result.solvable = True
            result.switches = out["switches"]
            return result

        # Who holds control at step 0, so the validator and every downstream
        # replay follow the same alternation the search intended. The search
        # reports it from its own layer-0 parent entry; inferring it from the
        # first move command instead is wrong whenever the layer-0 segment is
        # empty, because the path then opens with a switch and the first robot
        # to *move* is the second to hold control. That case is common enough
        # to fail real test cases.
        self.ws._control = out.get("initial_mover") or self.ws.robot_a

        result.solvable = True
        result.switches = out["switches"]
        result.path = out["path"]
        result.visited = out["visited"]
        result.states = len(out["visited"])
        return result
