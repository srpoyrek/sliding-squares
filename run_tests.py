"""
run_tests.py
------------
Discovers all test cases in testcases/ and runs them.

After each test passes we run every simplification recipe in simplify.RECIPES
(or the subset named on the command line). Each recipe:
  1. Aggregates the blocker heatmap from the validated solution.
  2. Removes black walls (zero contact) unless the recipe keeps them, and thins
     the touched "orange" walls by its chosen strategy — every other one,
     per-edge contact peaks, or peaks plus robot-size spacing.
  3. Optionally frees every wall the robot could never cross (exact, lossless).
  4. Crops all-wall borders and runs the solver once on the result.
  5. Saves the simplified workspace, a solved sequence and a comparison summary
     into <plot_dir>/simplified/<recipe>/ — one folder per recipe, so the
     strategies sit side by side on the same test instead of overwriting.
  6. Reports PRESERVED or FAILED per recipe.

Usage:
    python run_tests.py                          # run every test, no simplify
    python run_tests.py <name>                   # filter tests by substring
    python run_tests.py --simplified             # + EVERY simplify recipe
    python run_tests.py --simplified uncrossable black_peaks   # a subset
    python run_tests.py 3x3 --simplified         # both filters at once
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
from src.report import build_run, write_global_index, write_local_report, write_run
from src.robot import Robot
from src.simplify import RECIPES, describe_recipes, run_simplification
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


def _write_recipe_index(simplified_dir, test_name, switches, statuses) -> None:
    """Write simplified/README.txt — the map for the sibling recipe folders.

    Without it a reader lands on eight same-looking directories with no way to
    tell what each one did or which won, so this names every recipe, explains
    it, and ranks them by how few walls survived.
    """
    os.makedirs(simplified_dir, exist_ok=True)
    walls_before = next((s["walls_before"] for s in statuses if "walls_before" in s), "?")
    lines = [
        f"{test_name} — simplification recipes",
        f"original: {walls_before} walls, {switches} control switches",
        "",
        "Each subfolder is one recipe, holding its own summary.png, solved",
        "sequence and simplification.txt. Ranked by fewest walls surviving.",
        "",
        f"{'recipe'.ljust(28)}{'walls'.rjust(6)}{'removed'.rjust(9)}  status",
        "-" * 72,
    ]

    def rank(s):
        return s.get("walls_after", 10**9)

    for s in sorted(statuses, key=rank):
        name = s.get("mode", "?")
        if "error" in s:
            lines.append(f"{name.ljust(28)}{'—'.rjust(6)}{'—'.rjust(9)}  ERROR: {s['error']}")
            continue
        state = "PRESERVED" if s.get("preserved") else f"FAILED ({s.get('new_switches')})"
        lines.append(
            f"{name.ljust(28)}{str(s.get('walls_after', '?')).rjust(6)}"
            f"{str(s.get('removed', '?')).rjust(9)}  {state}"
        )
    lines.append("")
    lines.append(describe_recipes())

    with open(os.path.join(simplified_dir, "README.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def run_one(args) -> TestResult:
    """Run a single test by class name.

    `args` is (cls_name, recipes, want_png) where `recipes` is a list of names
    from simplify.RECIPES to run after the test passes (empty list = skip), and
    `want_png` keeps the matplotlib per-switch images alongside the HTML report.
    """
    cls_name, recipes, want_png = args
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

        # perf_counter, not time(): on Windows the wall clock ticks about every
        # 15.6 ms, so any solve faster than that measures as exactly 0.0. This is
        # a monotonic high-resolution timer, which is what a duration needs.
        start = time.perf_counter()
        solver_result = Solver(ws, goal_a, goal_b).solve()
        elapsed = time.perf_counter() - start
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
        if want_png:
            draw_sequence(
                ws.grid,
                snapshots,
                titles=vr.titles,
                save_dir=plot_dir,
                robot_size=ws.robot_a.n,
            )
        result.plot_path = plot_dir
        result.passed = True

        # Validator mutated ws.robot_a/b to their final positions, so the start
        # state is read back from the test case rather than from `ws`.
        start_ws, _, _ = tc.setup()

        # Simplification passes — only when requested via --simplified. Each
        # recipe writes to its own <plot_dir>/simplified/<mode>/ folder, so they
        # can all run against the same solved test and be compared side by side.
        # Validator mutated `ws.robot_a/b`, and so does each pass, so the
        # workspace is rebuilt from the test case for every recipe.
        if recipes:
            result.simplification = []
            for recipe in recipes:
                try:
                    ws2, goal_a2, goal_b2 = tc.setup()
                    status = run_simplification(
                        ws2,
                        goal_a2,
                        goal_b2,
                        vr,
                        plot_dir,
                        solver_result.switches,
                        tc.name,
                        want_png=want_png,
                        **RECIPES[recipe]["kwargs"],
                    )
                except Exception as e:
                    status = {"mode": recipe, "error": f"{type(e).__name__}: {e}"}
                result.simplification.append(status)

            _write_recipe_index(
                os.path.join(plot_dir, "simplified"),
                tc.name,
                solver_result.switches,
                result.simplification,
            )

        # Emitted last so the record carries the recipe outcomes. run.json is the
        # source of truth; index.html and render_run.py both derive from it.
        run = build_run(
            name=tc.name,
            grid=start_ws.grid,
            robot_a=start_ws.robot_a,
            robot_b=start_ws.robot_b,
            goal_a=goal_a,
            goal_b=goal_b,
            snapshots=snapshots,
            titles=vr.titles,
            switches=solver_result.switches,
            path=solver_result.path,
            solver_seconds=elapsed,
            recipes=result.simplification,
        )
        write_run(run, plot_dir)
        result.report_path = write_local_report(run, plot_dir)

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        traceback.print_exc()

    return result


def _print_simplifications(simps: list) -> None:
    for simp in simps:
        _print_simplification(simp)


def _print_simplification(simp: dict) -> None:
    tag = f"simplify[{simp.get('mode', '?')}]"
    if "error" in simp:
        print(f"         {tag} -> ERROR: {simp['error']}", flush=True)
        return
    if simp.get("note") and simp.get("removed", 0) == 0:
        print(f"         {tag} -> {simp['note']}", flush=True)
        return
    if not simp.get("preserved", False):
        print(
            f"         {tag} -> FAILED: {simp.get('note', 'unknown')}; "
            f"would have removed {simp.get('removed', 0)} wall(s) "
            f"-> {simp.get('plot_dir')}",
            flush=True,
        )
        return
    walls_before = simp.get("walls_before", 0)
    walls_after = simp.get("walls_after", 0)
    n_black = simp.get("removed_black", 0)
    n_orange = simp.get("removed_orange", 0)
    n_uncross = simp.get("removed_uncrossable", 0)
    pct = 100.0 * simp.get("removed", 0) / walls_before if walls_before else 0.0
    breakdown = f"black={n_black}"
    if n_orange:
        breakdown += f", orange={n_orange}"
    if n_uncross:
        breakdown += f", uncrossable={n_uncross}"
    print(
        f"         {tag} -> switches={simp.get('new_switches')} (preserved), "
        f"walls {walls_before} -> {walls_after} "
        f"(-{simp.get('removed', 0)} {breakdown}, {pct:.1f}%) -> {simp.get('plot_dir')}",
        flush=True,
    )


def _write_index() -> None:
    """Refresh plots/tests/index.html — the one page listing every run."""
    dest = write_global_index(os.path.join(get_plots_dir(), "tests"))
    if dest:
        print(f"\nindex -> {dest}", flush=True)


def run_all(recipes, want_png=False):
    wall_start = time.time()
    classes = discover_test_cases()

    if not classes:
        print("No test cases found in testcases/")
        return

    print(f"Found {len(classes)} test case(s)")
    if recipes:
        print(f"Simplification recipes ({len(recipes)}): {', '.join(recipes)}")
        print("  what each does: python run_tests.py --list-recipes")
        print("  per-test ranking: plots/tests/<name>/simplified/README.txt")
    print()
    print("=" * 60)

    results = []
    jobs = [(cls.__name__, recipes, want_png) for cls in classes]
    with mp.get_context("spawn").Pool(processes=min(8, mp.cpu_count())) as pool:
        for r in pool.imap_unordered(run_one, jobs):
            results.append(r)
            print(r, flush=True)
            if r.plot_path:
                print(f"         plot -> {r.plot_path}", flush=True)
            if r.report_path:
                print(f"         report -> {r.report_path}", flush=True)
            if r.simplification:
                _print_simplifications(r.simplification)

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
    _write_index()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run sliding-squares test cases.")
    parser.add_argument(
        "name",
        nargs="?",
        help="Substring filter — only run tests whose name contains this.",
    )
    parser.add_argument(
        "--simplified",
        nargs="*",
        metavar="RECIPE",
        default=None,
        help="Run the wall-simplification passes after each test. Bare "
        "--simplified runs EVERY recipe (" + ", ".join(RECIPES) + "), each "
        "writing to its own plots/tests/<name>/simplified/<recipe>/ folder so "
        "they can be compared side by side. Name recipes to run a subset. "
        "Without the flag, run_tests.py only solves and plots.",
    )
    parser.add_argument(
        "--list-recipes",
        action="store_true",
        help="Print every simplification recipe and what it does, then exit.",
    )
    parser.add_argument(
        "--png",
        action="store_true",
        help="Also render the matplotlib per-switch PNGs. Off by default: the "
        "HTML report covers the same ground without paying matplotlib's cost "
        "per frame, which dominates a run. Use this to cross-check the report "
        "against the images, or to produce figures for the paper.",
    )
    args = parser.parse_args()

    if args.list_recipes:
        print(describe_recipes())
        sys.exit(0)

    # None = flag absent; [] = bare --simplified, meaning every recipe.
    if args.simplified is None:
        recipes = []
    elif args.simplified:
        unknown = [r for r in args.simplified if r not in RECIPES]
        if unknown:
            print(f"Unknown recipe(s): {', '.join(unknown)}")
            print(f"Available: {', '.join(RECIPES)}")
            sys.exit(1)
        recipes = list(args.simplified)
    else:
        recipes = list(RECIPES)

    if args.name:
        name = args.name.lower()
        classes = discover_test_cases()
        matched = [cls for cls in classes if name in cls().name.lower()]
        if not matched:
            print(f"No test case matching '{args.name}'")
            sys.exit(1)
        for cls in matched:
            r = run_one((cls.__name__, recipes, args.png))
            print(r)
            if r.plot_path:
                print(f"         plot -> {r.plot_path}")
            if r.report_path:
                print(f"         report -> {r.report_path}")
            if r.simplification:
                _print_simplifications(r.simplification)
        _write_index()
    else:
        run_all(recipes, want_png=args.png)
