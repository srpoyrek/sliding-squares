"""
run_tests.py
------------
Discovers all test cases in testcases/ and runs them.

After each test passes we run a batch simplification pass:
  1. Aggregate the blocker heatmap from the validated solution.
  2. Remove all black walls (zero contact). Optionally also thin the touched
     "orange" walls: --alternate strips every other one (row-major), while
     --keep-peaks keeps only each wall segment's highest-contact cell.
  3. Run the solver once on the simplified grid.
  4. If switches are preserved, save the simplified workspace into
     <plot_dir>/simplified/ alongside a comparison summary image.
  5. If switches changed, report it and skip saving.

Usage:
    python run_tests.py                       # run every test
    python run_tests.py <name>                # filter by substring
    python run_tests.py --alternate           # also strip every-other orange
    python run_tests.py --keep-peaks          # thin orange to per-segment peaks
"""

from __future__ import annotations

import argparse
import inspect
import multiprocessing as mp
import os
import sys
import time
import traceback

from src.directories import get_plots_dir, get_testcases_dir
from src.grid import Grid
from src.robot import Robot
from src.solver import Solver
from src.test_case import TestCase, TestResult
from src.validator import Validator
from src.visualizer import (
    _compute_contact_at,
    draw_sequence,
    draw_summary,
)
from src.workspace import Workspace

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


# ── Batch simplification (black + every-other-orange wall removal) ─────


def _aggregate_wall_counts(grid, snapshots):
    """Count wall contact at every step, for both robots — including the
    initial placement and the stationary robot's bracing at each step.

    Returns (counts, face_counts):
      counts      : (row, col) -> total contacts (the heatmap number)
      face_counts : (row, col, wall_face) -> contacts on that single face
    """
    opposite = {"N": "S", "S": "N", "E": "W", "W": "E"}
    counts: dict = {}
    face_counts: dict = {}

    def _tally(robot, other):
        _, face_walls = _compute_contact_at(grid, robot.row, robot.col, robot.n, other)
        for robot_side, walls in face_walls.items():
            wall_side = opposite[robot_side]
            for wc in walls:
                counts[wc] = counts.get(wc, 0) + 1
                fkey = (wc[0], wc[1], wall_side)
                face_counts[fkey] = face_counts.get(fkey, 0) + 1

    for a, b in snapshots:
        _tally(a, b)
        _tally(b, a)

    return counts, face_counts


def _count_walls(grid):
    return sum(1 for r in range(grid.rows) for c in range(grid.cols) if grid.tiles[r][c] != 0)


def _build_workspace_from_tiles(tiles, ref_ws):
    """Fresh Workspace with the given tile layout, robots at ref_ws's start."""
    n = ref_ws.robot_a.n
    grid = Grid([row[:] for row in tiles])
    a = Robot(ref_ws.robot_a.label, n, ref_ws.robot_a.row, ref_ws.robot_a.col)
    b = Robot(ref_ws.robot_b.label, n, ref_ws.robot_b.row, ref_ws.robot_b.col)
    return Workspace(grid, a, b)


def _orange_peak_keepers(face_counts):
    """Touched-wall cells to KEEP when thinning each side down to its peak.

    Split the touched walls into per-face straight edges: a cell pressed on
    its E/W face belongs to a vertical edge (group by column, consecutive
    rows); on its N/S face, a horizontal edge (group by row, consecutive
    cols). On each edge keep the cell(s) tied for the highest per-face contact
    count and drop the rest. A cell touched on two faces belongs to two edges
    and survives if it is a peak of either.

    `face_counts` maps (row, col, wall_face) -> contacts on that one face.
    """
    edges: dict = {}
    for (r, c, face), cnt in face_counts.items():
        if face in ("E", "W"):  # vertical wall: cells share a column
            edges.setdefault((face, c), []).append((r, r, c, cnt))
        else:  # "N"/"S" horizontal wall: cells share a row
            edges.setdefault((face, r), []).append((c, r, c, cnt))

    def _keep_run(run, out):
        peak = max(item[3] for item in run)
        out.extend((item[1], item[2]) for item in run if item[3] == peak)

    keepers: list = []
    for cells in edges.values():
        cells.sort()
        run = [cells[0]]
        for prev, cur in zip(cells, cells[1:]):
            if cur[0] == prev[0] + 1:
                run.append(cur)
            else:
                _keep_run(run, keepers)
                run = [cur]
        _keep_run(run, keepers)
    return keepers


def _protected_walls(grid, ws, goal_a, goal_b):
    """Wall cells the robots rest against at their start and goal positions.
    These braces are always kept — thinning must not delete them.
    """
    n = ws.robot_a.n
    a_goal = Robot(ws.robot_a.label, n, *goal_a)
    b_goal = Robot(ws.robot_b.label, n, *goal_b)
    placements = [
        (ws.robot_a, ws.robot_b),
        (ws.robot_b, ws.robot_a),
        (a_goal, b_goal),
        (b_goal, a_goal),
    ]
    protected = set()
    for robot, other in placements:
        _, face_walls = _compute_contact_at(grid, robot.row, robot.col, robot.n, other)
        for walls in face_walls.values():
            protected.update(walls)
    return protected


def _crop_bounds(tiles):
    """Fully-wall rows/cols to peel from each side: (top, bottom, left, right).
    The grid edge bounds the robot like a wall, so an all-wall border is
    redundant and can be cropped away losslessly.
    """
    rows, cols = len(tiles), len(tiles[0])
    top = bottom = left = right = 0
    changed = True
    while changed:
        changed = False
        if top < rows - bottom and all(tiles[top][c] != 0 for c in range(left, cols - right)):
            top += 1
            changed = True
        if bottom < rows - top and all(
            tiles[rows - 1 - bottom][c] != 0 for c in range(left, cols - right)
        ):
            bottom += 1
            changed = True
        if left < cols - right and all(tiles[r][left] != 0 for r in range(top, rows - bottom)):
            left += 1
            changed = True
        if right < cols - left and all(
            tiles[r][cols - 1 - right] != 0 for r in range(top, rows - bottom)
        ):
            right += 1
            changed = True
    return top, bottom, left, right


def simplify_workspace(
    ws,
    contact_counts,
    face_counts=None,
    remove_alternate_orange=False,
    keep_orange_peaks=False,
    protected=None,
):
    """Wall-removal simplification driven by the contact heatmap.

    All black walls (contact count == 0) are removed. Touched "orange" walls
    (contact count > 0) are thinned, by at most one strategy:

      - `keep_orange_peaks`: split the touched walls into per-face straight
        edges and, on each, keep only the peak cell(s) — every cell tied for
        that edge's highest per-face contact count — removing the rest
        (needs `face_counts`).
      - `remove_alternate_orange`: remove every other orange wall in
        row-major order (the first cell, then skip every second).

    If both are set, `keep_orange_peaks` wins; with neither, orange is kept.
    Cells in `protected` are exempt from all removal (e.g. walls the robots
    rest against at their start/goal positions).

    Returns (simplified_workspace, removed_black, removed_orange).
    """
    rows, cols = ws.grid.rows, ws.grid.cols
    new_tiles = [row[:] for row in ws.grid.tiles]

    orange_cells = [
        (r, c)
        for r in range(rows)
        for c in range(cols)
        if new_tiles[r][c] != 0 and contact_counts.get((r, c), 0) > 0
    ]

    removed_orange = []
    if keep_orange_peaks:
        keepers = set(_orange_peak_keepers(face_counts or {}))
        removed_orange = [cell for cell in orange_cells if cell not in keepers]
    elif remove_alternate_orange:
        orange_cells.sort()
        removed_orange = orange_cells[::2]

    # Remove ALL black (zero-contact) walls, plus the thinned orange.
    protected = protected or set()
    removed_black = [
        (r, c)
        for r in range(rows)
        for c in range(cols)
        if new_tiles[r][c] != 0 and contact_counts.get((r, c), 0) == 0 and (r, c) not in protected
    ]
    removed_orange = [cell for cell in removed_orange if cell not in protected]

    for r, c in removed_black:
        new_tiles[r][c] = 0
    for r, c in removed_orange:
        new_tiles[r][c] = 0

    # Crop fully-wall outer borders, shifting the robots into the smaller grid.
    top, bottom, left, right = _crop_bounds(ws.grid.tiles)
    cropped = [row[left : cols - right] for row in new_tiles[top : rows - bottom]]
    n = ws.robot_a.n
    cropped_ws = Workspace(
        Grid(cropped),
        Robot(ws.robot_a.label, n, ws.robot_a.row - top, ws.robot_a.col - left),
        Robot(ws.robot_b.label, n, ws.robot_b.row - top, ws.robot_b.col - left),
    )
    return cropped_ws, removed_black, removed_orange, (top, left)


def _run_simplification(
    ws,
    goal_a,
    goal_b,
    vr,
    plot_dir,
    target_switches,
    test_name,
    remove_alternate_orange=False,
    keep_orange_peaks=False,
):
    """Run the simplification pass; save results into <plot_dir>/simplified/.
    Returns a status dict for the result summary.
    """
    counts, face_counts = _aggregate_wall_counts(ws.grid, vr.snapshots)
    walls_before = _count_walls(ws.grid)
    protected = _protected_walls(ws.grid, ws, goal_a, goal_b)

    simplified, removed_black, removed_orange, (off_r, off_c) = simplify_workspace(
        ws,
        counts,
        face_counts=face_counts,
        remove_alternate_orange=remove_alternate_orange,
        keep_orange_peaks=keep_orange_peaks,
        protected=protected,
    )
    goal_a = (goal_a[0] - off_r, goal_a[1] - off_c)
    goal_b = (goal_b[0] - off_r, goal_b[1] - off_c)
    walls_after = _count_walls(simplified.grid)
    removed_total = len(removed_black) + len(removed_orange)

    status: dict = {
        "removed": removed_total,
        "removed_black": len(removed_black),
        "removed_orange": len(removed_orange),
        "walls_before": walls_before,
        "walls_after": walls_after,
        "target_switches": target_switches,
    }

    if removed_total == 0:
        status["note"] = "no walls eligible for removal"
        status["preserved"] = True
        status["new_switches"] = target_switches
        return status

    # Verify the simplification with one solver call.
    res = Solver(simplified, goal_a, goal_b).solve()
    status["new_switches"] = res.switches if res.solvable else None
    status["preserved"] = res.solvable and res.switches == target_switches
    if not res.solvable:
        status["note"] = "simplified workspace is unsolvable"
    elif not status["preserved"]:
        status["note"] = (
            f"switches changed from {target_switches} to {res.switches} "
            "(removed walls were not all redundant)"
        )

    # Always save the attempted simplification — success or failure — so the
    # user can inspect what was removed and why.
    sub_dir = os.path.join(plot_dir, "simplified")
    os.makedirs(sub_dir, exist_ok=True)

    # Capture starting positions before validator mutates the workspace.
    start_a = (simplified.robot_a.row, simplified.robot_a.col)
    start_b = (simplified.robot_b.row, simplified.robot_b.col)

    if res.solvable:
        vr2 = Validator(simplified, goal_a, goal_b).run(res.path, plot=False)
        snapshots = [[a, b] for a, b in vr2.snapshots]
        draw_sequence(
            simplified.grid,
            snapshots,
            titles=vr2.titles,
            save_dir=sub_dir,
            robot_size=ws.robot_a.n,
        )

    if status["preserved"]:
        outcome = f"PRESERVED — switches stayed at {target_switches}"
    elif res.solvable:
        outcome = f"FAILED — switches changed from {target_switches} to {res.switches}"
    else:
        outcome = "FAILED — simplified workspace is unsolvable"

    with open(os.path.join(sub_dir, "simplification.txt"), "w") as f:
        f.write(
            f"Status: {outcome}\n"
            f"Walls before: {walls_before}\n"
            f"Walls after:  {walls_after}\n"
            f"Black walls removed ({len(removed_black)}): {removed_black}\n"
            f"Orange walls removed ({len(removed_orange)}): {removed_orange}\n"
        )

    # Comparison summary image: original | simplified | stats.
    pct = 100.0 * removed_total / walls_before if walls_before else 0.0
    stats = [
        ("test", test_name),
        ("status", outcome),
        ("grid", f"{ws.grid.rows} x {ws.grid.cols}"),
        ("robot size", f"{ws.robot_a.n} x {ws.robot_a.n}"),
        ("original switches", target_switches),
        (
            "simplified switches",
            res.switches if res.solvable else "unsolvable",
        ),
        ("walls before", walls_before),
        ("walls after", walls_after),
        ("removed black", len(removed_black)),
        ("removed orange", len(removed_orange)),
        ("total removed", f"{removed_total} ({pct:.1f}%)"),
    ]
    summary_a = Robot(simplified.robot_a.label, simplified.robot_a.n, *start_a)
    summary_b = Robot(simplified.robot_b.label, simplified.robot_b.n, *start_b)
    panels = [
        (ws.grid, [ws.robot_a, ws.robot_b], "original"),
        (simplified.grid, [summary_a, summary_b], "simplified"),
    ]
    draw_summary(
        panels,
        stats,
        os.path.join(sub_dir, "summary.png"),
        title=f"{test_name}  —  {outcome}",
    )

    status["plot_dir"] = sub_dir
    return status


# ── Test discovery and execution ────────────────────────────────────────


def discover_test_cases() -> list[type]:
    testcases_dir = get_testcases_dir()
    sys.path.insert(0, testcases_dir)
    cases = []
    for fname in sorted(os.listdir(testcases_dir)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        module = __import__(fname[:-3])
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, TestCase) and obj is not TestCase:
                cases.append(obj)
    return cases


def run_one(args) -> TestResult:
    """Run a single test by class name.

    `args` is (cls_name, simplified, remove_alternate_orange, keep_orange_peaks).
    """
    cls_name, simplified, remove_alternate_orange, keep_orange_peaks = args
    sys.path.insert(0, BASE_DIR)
    sys.path.insert(0, get_testcases_dir())

    from src.directories import get_testcases_dir as _get_testcases_dir
    from src.test_case import TestCase, TestResult

    cls = None
    for fname in sorted(os.listdir(_get_testcases_dir())):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        module = __import__(fname[:-3])
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, TestCase) and obj is not TestCase and obj.__name__ == cls_name:
                cls = obj
                break
        if cls:
            break

    tc = cls()  # type: ignore
    result = TestResult(name=tc.name, passed=False)

    try:
        ws, goal_a, goal_b = tc.setup()

        start = time.time()
        solver_result = Solver(ws, goal_a, goal_b).solve()
        elapsed = time.time() - start
        if elapsed < 0.001:
            result.time = f"{elapsed*1_000_000:.1f}u"  # type: ignore
        elif elapsed < 1:
            result.time = f"{elapsed*1000:.1f}m"  # type: ignore
        else:
            result.time = f"{elapsed:.2f}"  # type: ignore
        if not solver_result.solvable:
            result.error = "Solver returned solvable=False"
            return result

        vr = Validator(ws, goal_a, goal_b).run(solver_result.path, plot=False)
        if not vr.valid:
            result.error = f"Path invalid: {vr.failed_reason}"
            return result

        plots_tests_dir = os.path.join(get_plots_dir(), "tests")
        plot_dir = os.path.join(plots_tests_dir, tc.name.replace(" ", "_"))

        snapshots = [[a, b] for a, b in vr.snapshots]
        draw_sequence(
            ws.grid,
            snapshots,
            titles=vr.titles,
            save_dir=plot_dir,
            robot_size=ws.robot_a.n,
        )
        result.plot_path = plot_dir
        result.passed = True

        # Simplification pass — only when explicitly requested via --simplified.
        # Validator mutated `ws.robot_a/b`, so rebuild from the test case to get
        # fresh starting positions.
        if simplified:
            try:
                ws2, goal_a2, goal_b2 = tc.setup()
                result.simplification = _run_simplification(  # type: ignore[attr-defined]
                    ws2,
                    goal_a2,
                    goal_b2,
                    vr,
                    plot_dir,
                    solver_result.switches,
                    tc.name,
                    remove_alternate_orange=remove_alternate_orange,
                    keep_orange_peaks=keep_orange_peaks,
                )
            except Exception as e:
                result.simplification = {"error": f"{type(e).__name__}: {e}"}  # type: ignore[attr-defined]

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        traceback.print_exc()

    return result


def _print_simplification(simp: dict) -> None:
    if "error" in simp:
        print(f"         simplify -> ERROR: {simp['error']}", flush=True)
        return
    if simp.get("note") and simp.get("removed", 0) == 0:
        print(f"         simplify -> {simp['note']}", flush=True)
        return
    if not simp.get("preserved", False):
        print(
            f"         simplify -> FAILED: {simp.get('note', 'unknown')}; "
            f"would have removed {simp.get('removed', 0)} wall(s) "
            f"-> {simp.get('plot_dir')}",
            flush=True,
        )
        return
    walls_before = simp.get("walls_before", 0)
    walls_after = simp.get("walls_after", 0)
    n_black = simp.get("removed_black", 0)
    n_orange = simp.get("removed_orange", 0)
    pct = 100.0 * simp.get("removed", 0) / walls_before if walls_before else 0.0
    breakdown = f"black={n_black}"
    if n_orange:
        breakdown += f", orange={n_orange}"
    print(
        f"         simplify -> switches={simp.get('new_switches')} (preserved), "
        f"walls {walls_before} -> {walls_after} "
        f"(-{simp.get('removed', 0)} {breakdown}, {pct:.1f}%) -> {simp.get('plot_dir')}",
        flush=True,
    )


def run_all(simplified: bool, remove_alternate_orange: bool, keep_orange_peaks: bool):
    wall_start = time.time()
    classes = discover_test_cases()

    if not classes:
        print("No test cases found in testcases/")
        return

    print(f"Found {len(classes)} test case(s)\n")
    print("=" * 60)

    results = []
    jobs = [
        (cls.__name__, simplified, remove_alternate_orange, keep_orange_peaks) for cls in classes
    ]
    with mp.get_context("spawn").Pool(processes=min(8, mp.cpu_count())) as pool:
        for r in pool.imap_unordered(run_one, jobs):
            results.append(r)
            print(r, flush=True)
            if r.plot_path:
                print(f"         plot -> {r.plot_path}", flush=True)
            if r.simplification:
                _print_simplification(r.simplification)

    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    print("\n" + "=" * 60)
    print(f"PASSED: {len(passed)} / {len(results)}")
    if failed:
        print(f"FAILED: {len(failed)}")
        for r in failed:
            print(f"  {r.name}: {r.error}")

    times = [r.time for r in results if r.time is not None]
    if times:
        print(f"\nSlowest: {max(times)}s  Fastest: {min(times)}s")
    print(f"\nTotal wall time: {round(time.time() - wall_start, 2)}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run sliding-squares test cases.")
    parser.add_argument(
        "name",
        nargs="?",
        help="Substring filter — only run tests whose name contains this.",
    )
    parser.add_argument(
        "--simplified",
        action="store_true",
        help="Run the wall-simplification pass after each test. Without this "
        "flag, run_tests.py only solves and plots (its original behaviour).",
    )
    orange_mode = parser.add_mutually_exclusive_group()
    orange_mode.add_argument(
        "--alternate",
        action="store_true",
        help="In addition to removing all black walls, also remove every "
        "other orange wall (touched walls, alternating in row-major order). "
        "Default: only black walls are removed.",
    )
    orange_mode.add_argument(
        "--keep-peaks",
        action="store_true",
        help="In addition to removing all black walls, thin each touched wall "
        "edge down to its peak cell(s) — the cells tied for that edge's highest "
        "per-face contact count — removing the rest.",
    )
    args = parser.parse_args()

    if args.name:
        name = args.name.lower()
        classes = discover_test_cases()
        matched = [cls for cls in classes if name in cls().name.lower()]
        if not matched:
            print(f"No test case matching '{args.name}'")
            sys.exit(1)
        for cls in matched:
            r = run_one((cls.__name__, args.simplified, args.alternate, args.keep_peaks))
            print(r)
            if r.plot_path:
                print(f"         plot -> {r.plot_path}")
            if r.simplification:
                _print_simplification(r.simplification)
    else:
        run_all(args.simplified, args.alternate, args.keep_peaks)
