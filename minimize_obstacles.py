"""
minimize_obstacles.py
---------------------
Greedy obstacle minimizer.

Given a workspace, start/goal positions, and a baseline control switch count,
removes obstacles one at a time and checks if the switch count drops.
Irrelevant obstacles are removed permanently from the grid.

Returns the minimal set of obstacles that still forces the same switch count.

Usage:
    from minimize_obstacles import minimize_obstacles
    minimal_grid, essential_obstacles = minimize_obstacles(ws, goal_a, goal_b)
"""

from __future__ import annotations

import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.grid import FREE, Grid
from src.robot import Robot
from src.solver import Solver
from src.workspace import Workspace


def minimize_obstacles(
    ws: Workspace,
    goal_a: tuple,
    goal_b: tuple,
) -> tuple[Grid, set]:
    """
    Greedily remove obstacles that don't contribute to the max switch count.

    Parameters
    ----------
    ws     : Workspace with the original grid and robots
    goal_a : (row, col) goal for robot A
    goal_b : (row, col) goal for robot B

    Returns
    -------
    (minimal_grid, essential_obstacles)
        minimal_grid       : Grid with only essential obstacles remaining
        essential_obstacles: set of (row, col) positions that are load-bearing
    """
    # ── baseline solve ───────────────────────────────────
    baseline = Solver(ws, goal_a, goal_b).solve()
    if not baseline.solvable:
        raise ValueError("Original workspace is not solvable.")

    baseline_switches = baseline.switches
    print(f"Baseline control switches: {baseline_switches}")

    # ── work on a deep copy of the grid ─────────────────
    grid = copy.deepcopy(ws.grid)
    all_obstacles = grid.get_all_obstacles()
    essential = all_obstacles.copy()

    print(f"Total obstacles: {len(all_obstacles)}")

    removed = 0
    for i, (r, c) in enumerate(sorted(all_obstacles)):
        original_val = grid.tiles[r][c]

        # temporarily remove this obstacle
        grid.tiles[r][c] = FREE

        # rebuild workspace with modified grid
        robot_a = Robot(ws.robot_a.label, ws.robot_a.n, ws.robot_a.row, ws.robot_a.col)
        robot_b = Robot(ws.robot_b.label, ws.robot_b.n, ws.robot_b.row, ws.robot_b.col)
        test_ws = Workspace(grid, robot_a, robot_b)

        result = Solver(test_ws, goal_a, goal_b).solve()

        if result.solvable and result.switches <= baseline_switches:  # type: ignore
            # obstacle is load-bearing — restore it
            grid.tiles[r][c] = original_val
            print(
                f"  [{i+1}/{len(all_obstacles)}] kept ({r},{c}) — switches dropped to {
                    result.switches}"
            )
        else:
            # obstacle not needed — keep it removed
            essential.discard((r, c))
            removed += 1
            print(
                f"  [{i+1}/{len(all_obstacles)}] removed ({r},{c}) — switches {
                    result.switches if result.solvable else 'unsolvable'}"
            )

    print(f"\nDone. Removed {removed} / {len(all_obstacles)} obstacles.")
    print(f"Essential obstacles remaining: {len(essential)}")

    return grid, essential


if __name__ == "__main__":
    import inspect
    import os
    import sys

    from src.test_case import TestCase
    from src.validator import Validator
    from src.visualizer import draw_sequence

    if len(sys.argv) < 2:
        print("Usage: python minimize_obstacles.py <test_case_name>")
        print("Example: python minimize_obstacles.py 2x2_robot_no_holes")
        sys.exit(1)

    test_name = sys.argv[1]
    sys.path.insert(0, "testcases")
    module = __import__(test_name)

    cls = next(
        obj
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, TestCase) and obj is not TestCase
    )

    tc = cls()
    ws, goal_a, goal_b = tc.setup()

    out_dir = os.path.join("plots", "minimize", test_name)
    os.makedirs(out_dir, exist_ok=True)

    # ── baseline ─────────────────────────────────────────
    baseline_result = Solver(ws, goal_a, goal_b).solve()
    print(f"Baseline switches: {baseline_result.switches}")

    vr_baseline = Validator(ws, goal_a, goal_b).run(baseline_result.path, plot=False)
    snapshots = [[a, b] for a, b in vr_baseline.snapshots]
    draw_sequence(
        ws.grid,
        snapshots,
        titles=vr_baseline.titles,
        save_dir=os.path.join(out_dir, "baseline"),
        robot_size=ws.robot_a.n,
    )
    print(f"Baseline turns saved to {os.path.join(out_dir, 'baseline')}")

    ws.robot_a.row, ws.robot_a.col = tc.setup()[0].robot_a.row, tc.setup()[0].robot_a.col
    ws.robot_b.row, ws.robot_b.col = tc.setup()[0].robot_b.row, tc.setup()[0].robot_b.col

    # ── minimize ─────────────────────────────────────────
    minimal_grid, essential = minimize_obstacles(ws, goal_a, goal_b)

    # solve minimal grid
    robot_a = Robot(ws.robot_a.label, ws.robot_a.n, ws.robot_a.row, ws.robot_a.col)
    robot_b = Robot(ws.robot_b.label, ws.robot_b.n, ws.robot_b.row, ws.robot_b.col)
    minimal_ws = Workspace(minimal_grid, robot_a, robot_b)

    minimal_result = Solver(minimal_ws, goal_a, goal_b).solve()
    print(f"Minimal switches: {minimal_result.switches}")

    vr_minimal = Validator(minimal_ws, goal_a, goal_b).run(minimal_result.path, plot=False)
    snapshots_min = [[a, b] for a, b in vr_minimal.snapshots]
    draw_sequence(
        minimal_grid,
        snapshots_min,
        titles=vr_minimal.titles,
        save_dir=os.path.join(out_dir, "minimal"),
        robot_size=ws.robot_a.n,
    )
    print(f"Minimal turns saved to {os.path.join(out_dir, 'minimal')}")
    print(f"\nEssential obstacles: {len(essential)} / {len(ws.grid.get_all_obstacles())}")
