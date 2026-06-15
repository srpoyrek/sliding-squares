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
from src.simplify import run_simplification
from src.solver import Solver
from src.test_case import TestCase, TestResult
from src.validator import Validator
from src.visualizer import draw_sequence
from src.workspace import Workspace

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


def _build_workspace_from_tiles(tiles, ref_ws):
    """Fresh Workspace with the given tile layout, robots at ref_ws's start."""
    n = ref_ws.robot_a.n
    grid = Grid([row[:] for row in tiles])
    a = Robot(ref_ws.robot_a.label, n, ref_ws.robot_a.row, ref_ws.robot_a.col)
    b = Robot(ref_ws.robot_b.label, n, ref_ws.robot_b.row, ref_ws.robot_b.col)
    return Workspace(grid, a, b)


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

    `args` is (cls_name, simplified, remove_alternate_orange, keep_orange_peaks,
    keep_relative_robot_size).
    """
    cls_name, simplified, remove_alternate_orange, keep_orange_peaks, keep_relative = args
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
                result.simplification = run_simplification(  # type: ignore[attr-defined]
                    ws2,
                    goal_a2,
                    goal_b2,
                    vr,
                    plot_dir,
                    solver_result.switches,
                    tc.name,
                    remove_alternate_orange=remove_alternate_orange,
                    keep_orange_peaks=keep_orange_peaks,
                    keep_relative_robot_size=keep_relative,
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


def run_all(simplified, remove_alternate_orange, keep_orange_peaks, keep_relative):
    wall_start = time.time()
    classes = discover_test_cases()

    if not classes:
        print("No test cases found in testcases/")
        return

    print(f"Found {len(classes)} test case(s)\n")
    print("=" * 60)

    results = []
    jobs = [
        (cls.__name__, simplified, remove_alternate_orange, keep_orange_peaks, keep_relative)
        for cls in classes
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
    orange_mode.add_argument(
        "--keep-all-orange",
        action="store_true",
        help="Keep every touched (orange) wall regardless of contact count; "
        "only black walls are removed (and the grid cropped).",
    )
    orange_mode.add_argument(
        "--keep-relative-robot-size",
        action="store_true",
        help="Thin orange but keep peaks plus enough cells that no gap exceeds "
        "robot_size - 1, so the robot can't cross the boundary.",
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
            r = run_one(
                (
                    cls.__name__,
                    args.simplified,
                    args.alternate,
                    args.keep_peaks,
                    args.keep_relative_robot_size,
                )
            )
            print(r)
            if r.plot_path:
                print(f"         plot -> {r.plot_path}")
            if r.simplification:
                _print_simplification(r.simplification)
    else:
        run_all(args.simplified, args.alternate, args.keep_peaks, args.keep_relative_robot_size)
