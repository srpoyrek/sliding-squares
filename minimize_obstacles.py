"""
minimize_obstacles.py
---------------------
Finds the minimum set of obstacles/boundaries needed to maintain the baseline
switch count.

For every obstacle and boundary cell in the original grid, we:
  1. Deep-copy the entire workspace
  2. Disable that single cell (set it FREE)
  3. Run the solver
  4. Return whether that cell is *required* (removing it breaks or degrades
     the solution)

Parallel execution via multiprocessing.Pool.
After the search: plots the original grid, then the minimal grid + full path.

Usage:
    python minimize_obstacles.py <test_case_name>
"""

from __future__ import annotations

import multiprocessing as mp
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.grid import FREE, Grid
from src.robot import Robot
from src.solver import Solver
from src.workspace import Workspace

# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


def _test_cell(args: tuple) -> dict:
    """
    Worker function.

    Deep-copies the full workspace, disables *one* cell (obstacle or boundary),
    solves, and returns whether that cell is required.

    Parameters (packed into args for Pool.map compatibility)
    ---------------------------------------------------------
    workspace_tiles : list[list[int]]   — tile grid (copied, not mutated)
    rows, cols      : int               — grid dimensions
    r, c            : int               — cell to disable
    robot_a_info    : tuple             — (label, n, row, col)
    robot_b_info    : tuple             — (label, n, row, col)
    goal_a          : tuple             — (row, col)
    goal_b          : tuple             — (row, col)
    baseline_switches : int             — switches on the original grid

    Returns
    -------
    dict with keys: r, c, switches, required
        required=True  → removing this cell broke/degraded the solution
        required=False → safe to remove
    """
    (
        workspace_tiles,
        rows,
        cols,
        r,
        c,
        robot_a_info,
        robot_b_info,
        goal_a,
        goal_b,
        baseline_switches,
    ) = args

    # local imports so each worker is self-contained
    from src.grid import Grid
    from src.robot import Robot
    from src.solver import Solver
    from src.workspace import Workspace

    # --- deep-copy the tile grid, then disable the target cell ---
    tiles_copy = [row[:] for row in workspace_tiles]
    tiles_copy[r][c] = FREE

    grid = Grid(tiles=tiles_copy)
    robot_a = Robot(*robot_a_info)
    robot_b = Robot(*robot_b_info)
    ws = Workspace(grid, robot_a, robot_b)

    result = Solver(ws, goal_a, goal_b).solve()

    if not result.solvable:
        switches = -1
        required = True  # removing it made the problem unsolvable
    else:
        switches = result.switches
        # required if removing the cell keeps or worsens switch count
        required = switches >= baseline_switches

    return {"r": r, "c": c, "switches": switches, "required": required}


# ---------------------------------------------------------------------------
# Main minimizer
# ---------------------------------------------------------------------------


def minimize_obstacles(
    ws: Workspace,
    goal_a: tuple,
    goal_b: tuple,
    baseline_switches: int,
    processes: int = 4,
) -> tuple[Grid, set]:
    """
    Test every obstacle and boundary cell in parallel.

    Returns
    -------
    minimal_grid : Grid   — grid containing only the required cells
    required_set : set    — {(r, c), ...} of cells that must be kept
    """
    original_tiles = [row[:] for row in ws.grid.tiles]
    original_grid = ws.grid

    # collect ALL non-free cells (obstacles + boundaries)
    all_cells = sorted(original_grid.get_all_obstacles())  # adjust if you
    # have a separate get_all_boundaries(); just extend all_cells with those

    print(f"Cells to test : {len(all_cells)}  (obstacles + boundaries)")
    print(f"Baseline switches : {baseline_switches}")
    print(f"Workers : {processes}\n")

    robot_a_info = (ws.robot_a.label, ws.robot_a.n, ws.robot_a.row, ws.robot_a.col)
    robot_b_info = (ws.robot_b.label, ws.robot_b.n, ws.robot_b.row, ws.robot_b.col)

    args = [
        (
            original_tiles,
            original_grid.rows,
            original_grid.cols,
            r,
            c,
            robot_a_info,
            robot_b_info,
            goal_a,
            goal_b,
            baseline_switches,
        )
        for r, c in all_cells
    ]

    # --- parallel execution ---
    # Use "spawn" explicitly to avoid deadlocks on macOS/Linux with
    # modules that use threads internally (matplotlib, etc.).
    ctx = mp.get_context("spawn")
    required_set: set = set()
    done = 0
    with ctx.Pool(processes=processes) as pool:
        for res in pool.imap_unordered(_test_cell, args):
            done += 1
            r, c, switches, required = res["r"], res["c"], res["switches"], res["required"]
            tag = switches if switches != -1 else "unsolvable"
            if required:
                required_set.add((r, c))
                print(
                    f"  [{done:>3}/{len(all_cells)}] KEEP ({r},{c}) switches without it → {tag}",
                    flush=True,
                )
            else:
                print(
                    f"  [{done:>3}/{len(all_cells)}] REMOVE ({r},{c}) switches without it → {tag}",
                    flush=True,
                )

    print(f"\nRequired cells : {len(required_set)} / {len(all_cells)}")

    # --- build minimal grid: start blank, re-add only required cells ---
    minimal_grid = Grid(rows=original_grid.rows, cols=original_grid.cols)
    for r, c in required_set:
        minimal_grid.tiles[r][c] = original_tiles[r][c]

    return minimal_grid, required_set


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import inspect

    from src.test_case import TestCase
    from src.validator import Validator
    from src.visualizer import draw_sequence

    if len(sys.argv) < 2:
        print("Usage: python minimize_obstacles.py <test_case_name>")
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

    # ------------------------------------------------------------------ #
    # 1. BASELINE — solve + plot the original grid                        #
    # ------------------------------------------------------------------ #
    print("=" * 60)
    print("ORIGINAL GRID")
    print("=" * 60)
    ws.grid.display()

    baseline_result = Solver(ws, goal_a, goal_b).solve()
    baseline_switches = baseline_result.switches
    print(f"Baseline switches: {baseline_switches}\n")

    vr_baseline = Validator(ws, goal_a, goal_b).run(baseline_result.path, plot=False)
    draw_sequence(
        ws.grid,
        [[a, b] for a, b in vr_baseline.snapshots],
        titles=vr_baseline.titles,
        save_dir=os.path.join(out_dir, "original"),
        robot_size=ws.robot_a.n,
    )
    print(f"Original plot saved → {os.path.join(out_dir, 'original')}\n")

    # ------------------------------------------------------------------ #
    # 2. MINIMIZE — parallel search                                       #
    # ------------------------------------------------------------------ #
    print("=" * 60)
    print("MINIMIZING")
    print("=" * 60)

    ws_fresh, goal_a, goal_b = tc.setup()  # fresh robots for minimize call
    minimal_grid, required_set = minimize_obstacles(
        ws_fresh,
        goal_a,
        goal_b,
        baseline_switches,
        processes=4,  # type: ignore
    )

    print("\n" + "=" * 60)
    print("MINIMAL GRID")
    print("=" * 60)
    minimal_grid.display()

    # ------------------------------------------------------------------ #
    # 3. FINAL SOLVE — on the minimal grid, plot the full solution path   #
    # ------------------------------------------------------------------ #
    robot_a = Robot(
        ws_fresh.robot_a.label, ws_fresh.robot_a.n, ws_fresh.robot_a.row, ws_fresh.robot_a.col
    )
    robot_b = Robot(
        ws_fresh.robot_b.label, ws_fresh.robot_b.n, ws_fresh.robot_b.row, ws_fresh.robot_b.col
    )
    minimal_ws = Workspace(minimal_grid, robot_a, robot_b)

    minimal_result = Solver(minimal_ws, goal_a, goal_b).solve()
    print(f"Minimal grid switches: {minimal_result.switches}")

    vr_minimal = Validator(minimal_ws, goal_a, goal_b).run(minimal_result.path, plot=False)
    draw_sequence(
        minimal_grid,
        [[a, b] for a, b in vr_minimal.snapshots],
        titles=vr_minimal.titles,
        save_dir=os.path.join(out_dir, "minimal"),
        robot_size=ws_fresh.robot_a.n,
    )
    print(f"Minimal plot  saved → {os.path.join(out_dir, 'minimal')}")
