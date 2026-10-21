"""
run_tests.py
------------
Discovers all test cases in testcases/ and runs them.

After each test passes we run every simplification recipe in simplify.RECIPES
(or the subset named on the command line). Each recipe:
  1. Aggregates the blocker heatmap from the validated solution.
  2. Removes untouched walls (zero contact) unless the recipe keeps them, and
     thins the touched ones by keeping each contact plateau plus enough spacing
     that an n×n robot still cannot cross.
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
    python run_tests.py --simplified uncrossable untouched_spaced   # a subset
    python run_tests.py 3x3 --simplified         # both filters at once

--testcases-dir / --out-dir redirect discovery and output to a different pair
of folders (e.g. testcases_building_blocks/ + plots/building_blocks/) without
touching testcases/ or plots/tests/. The landing page is relinked either way.
"""

from __future__ import annotations

import argparse
import inspect
import multiprocessing as mp
import os
import shutil
import sys
import time
import traceback

from src.bfs import _clear_caches, configure_caches_for_grid
from src.directories import get_plots_dir, get_testcases_dir
from src.grid import Grid
from src.report import (
    build_run,
    control_turns,
    write_global_index,
    write_local_report,
    write_run,
    write_site_index,
)
from src.robot import Robot
from src.simplify import RECIPES, describe_recipes, run_simplification
from src.solver import Solver
from src.test_case import TestCase, TestResult
from src.validator import Validator
from src.visualizer import draw_sequence
from src.workspace import Workspace

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


def _fmt_time(seconds: float) -> str:
    """Elapsed seconds with an explicit unit, e.g. ``688.0us`` / ``1.55s``."""
    if seconds < 1e-3:
        return f"{seconds * 1e6:.1f}us"
    if seconds < 1:
        return f"{seconds * 1e3:.1f}ms"
    return f"{seconds:.2f}s"


def _rel(path: str) -> str:
    """Repo-relative path. Absolute paths made the run log unreadable."""
    try:
        return os.path.relpath(path, BASE_DIR).replace("\\", "/")
    except ValueError:  # different drive on Windows
        return path


def _build_workspace_from_tiles(tiles, ref_ws):
    """Fresh Workspace with the given tile layout, robots at ref_ws's start."""
    n = ref_ws.robot_a.n
    grid = Grid([row[:] for row in tiles])
    a = Robot(ref_ws.robot_a.label, n, ref_ws.robot_a.row, ref_ws.robot_a.col)
    b = Robot(ref_ws.robot_b.label, n, ref_ws.robot_b.row, ref_ws.robot_b.col)
    return Workspace(grid, a, b)


# ── Test discovery and execution ────────────────────────────────────────


def _iter_testcase_modules(testcases_dir: str):
    """(dirpath, module_name) for every non-underscore .py file under
    testcases_dir, recursively — so a folder grouped into subfolders (e.g.
    testcases_building_blocks/n1/, n2/) is still discovered."""
    found = []
    for dirpath, dirnames, filenames in os.walk(testcases_dir):
        dirnames[:] = [d for d in dirnames if not d.startswith((".", "_"))]
        for fname in filenames:
            if fname.endswith(".py") and not fname.startswith("_"):
                found.append((dirpath, fname[:-3]))
    return sorted(found)


def discover_test_cases(testcases_dir: str | None = None) -> list[type]:
    """Every TestCase subclass found in `testcases_dir` (default testcases/)."""
    testcases_dir = testcases_dir or get_testcases_dir()
    cases = []
    for dirpath, mod_name in _iter_testcase_modules(testcases_dir):
        sys.path.insert(0, dirpath)
        module = __import__(mod_name)
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
        f"original: {walls_before} walls, {control_turns(switches)} control turns",
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

    `args` is (cls_name, recipes, want_png, strategy, testcases_dir, out_dir,
    delete_failed): `recipes` are simplify.RECIPES names to run after the test
    passes (empty = skip), `want_png` also renders the matplotlib per-switch
    images, `strategy` is the Solver search, `testcases_dir`/`out_dir` default
    to testcases/ and plots/tests/, `delete_failed` removes the test's source
    file and report folder if it does not pass. Travels as a tuple, not a
    module global, because the pool spawns fresh workers.
    """
    cls_name, recipes, want_png, strategy, testcases_dir, out_dir, delete_failed = args
    testcases_dir = testcases_dir or get_testcases_dir()
    out_dir = out_dir or os.path.join(get_plots_dir(), "tests")
    sys.path.insert(0, BASE_DIR)

    from src.test_case import TestCase, TestResult

    cls = None
    src_path = None
    for dirpath, mod_name in _iter_testcase_modules(testcases_dir):
        sys.path.insert(0, dirpath)
        module = __import__(mod_name)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, TestCase) and obj is not TestCase and obj.__name__ == cls_name:
                cls = obj
                src_path = os.path.join(dirpath, f"{mod_name}.py")
                break
        if cls:
            break

    tc = cls()  # type: ignore
    result = TestResult(name=tc.name, passed=False)
    # Known before anything is solved, so it is available for --delete-failed
    # cleanup even on a path that returns before ever writing a report.
    plot_dir = os.path.join(out_dir, tc.name.replace(" ", "_"))

    try:
        ws, goal_a, goal_b = tc.setup()

        # Cap the flood caches to this grid before anything is solved. The
        # caps are entry counts, and an entry's size grows with the grid, so
        # the module defaults that suit a 20x30 board would let a 100x100 one
        # hold gigabytes before evicting. Same per-worker budget as
        # find_hardest's --cache-mb default; the recipe re-solves run on
        # cropped grids, so sizing for the original is an upper bound for them.
        configure_caches_for_grid(ws.grid.rows, ws.grid.cols, ws.robot_a.n)

        # Solved twice, the second timed. This is the first solve in a freshly
        # spawned worker, and a first solve pays one-off costs -- heap growth,
        # the first execution of every code path -- that the recipe re-solves
        # further down never pay. Their times are compared against this one, so
        # the original has to be measured on the same footing: process warm.
        # The flood caches are cleared in between so the timed solve is not
        # handed the warm-up's floods either -- a recipe's re-solve starts with
        # no floods cached for its grid, and neither should this. The answer is
        # deterministic, so the timed result is the one used throughout.
        #
        # perf_counter, not time(): on Windows the wall clock ticks about every
        # 15.6 ms, so any solve faster than that measures as exactly 0.0. This is
        # a monotonic high-resolution timer, which is what a duration needs.
        Solver(ws, goal_a, goal_b, strategy=strategy).solve()
        _clear_caches()
        start = time.perf_counter()
        solver_result = Solver(ws, goal_a, goal_b, strategy=strategy).solve()
        elapsed = time.perf_counter() - start
        result.seconds = elapsed
        result.time = _fmt_time(elapsed)
        if not solver_result.solvable:
            result.error = "Solver returned solvable=False"
            return result

        vr = Validator(ws, goal_a, goal_b).run(solver_result.path, plot=False)
        if not vr.valid:
            result.error = f"Path invalid: {vr.failed_reason}"
            return result

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
                        strategy=strategy,
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
            solver_states=len(solver_result.visited),
            recipes=result.simplification,
        )
        write_run(run, plot_dir)
        result.report_path = write_local_report(run, plot_dir)

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        traceback.print_exc()

    if delete_failed and not result.passed:
        deleted = []
        if src_path and os.path.isfile(src_path):
            os.remove(src_path)
            deleted.append(src_path)
        if os.path.isdir(plot_dir):
            shutil.rmtree(plot_dir)
            deleted.append(plot_dir)
        if deleted:
            result.deleted = deleted

    return result


def _print_simplifications(simps: list, verbose: bool = False) -> None:
    """One summary line per test, or the full per-recipe detail with --verbose.

    Eight recipes across eight tests is 64 near-identical lines; what actually
    matters at a glance is how many held, which recipe won, and which broke.
    """
    if verbose:
        for simp in simps:
            _print_simplification(simp)
        return

    ok = [s for s in simps if s.get("preserved") and "error" not in s]
    bad = [s for s in simps if not s.get("preserved") or "error" in s]
    # The winner is the recipe that survived while leaving the fewest walls.
    best = min(ok, key=lambda s: s.get("walls_after", 10**9), default=None)
    parts = [f"recipes: {len(ok)}/{len(simps)} preserved"]
    if best:
        before, after = best.get("walls_before", 0), best.get("walls_after", 0)
        pct = 100.0 * (before - after) / before if before else 0.0
        parts.append(f"best {best['mode']} {before}->{after} walls (-{pct:.0f}%)")
    if bad:
        parts.append("failed: " + ", ".join(s.get("mode", "?") for s in bad))
    print("         " + "  ·  ".join(parts), flush=True)


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
    n_untouched = simp.get("removed_untouched", 0)
    n_thinned = simp.get("removed_thinned", 0)
    n_uncross = simp.get("removed_uncrossable", 0)
    pct = 100.0 * simp.get("removed", 0) / walls_before if walls_before else 0.0
    breakdown = f"untouched={n_untouched}"
    if n_thinned:
        breakdown += f", thinned={n_thinned}"
    if n_uncross:
        breakdown += f", uncrossable={n_uncross}"
    print(
        f"         {tag} -> turns={simp.get('new_switches')} (preserved), "
        f"walls {walls_before} -> {walls_after} "
        f"(-{simp.get('removed', 0)} {breakdown}, {pct:.1f}%) -> {simp.get('plot_dir')}",
        flush=True,
    )


def _print_result(r, verbose: bool = False) -> None:
    """One test's outcome: a headline line, then its recipe summary."""
    status = "PASS" if r.passed else "FAIL"
    head = f"[{status}] {r.name:<22} {r.time or '-':>8}"
    if r.report_path:
        head += f"  {_rel(r.report_path)}"
    print(head, flush=True)
    if r.error:
        print(f"         error: {r.error}", flush=True)
    if r.deleted:
        for path in r.deleted:
            print(f"         deleted: {_rel(path)}", flush=True)
    if r.simplification:
        _print_simplifications(r.simplification, verbose)


def _write_index(out_dir: str | None = None, size_charts: bool = True) -> None:
    """Refresh <out_dir>/index.html (default plots/tests/) and relink the
    landing page. `size_charts=False` skips the two robot-size charts (and
    computing their data) — meaningless when many tests share one robot size."""
    out_dir = out_dir or os.path.join(get_plots_dir(), "tests")
    dest = write_global_index(out_dir, size_charts=size_charts)
    if dest:
        print(f"\nOpen: {_rel(dest)}", flush=True)
    print(f"Linked: {_rel(write_site_index(get_plots_dir()))}", flush=True)


def run_all(
    recipes,
    want_png=False,
    verbose=False,
    strategy="mirror",
    testcases_dir=None,
    out_dir=None,
    size_charts=True,
    delete_failed=False,
):
    wall_start = time.time()
    classes = discover_test_cases(testcases_dir)

    if not classes:
        print(f"No test cases found in {testcases_dir or get_testcases_dir()}")
        return

    print(f"{len(classes)} test(s)", end="")
    if recipes:
        print(f" · {len(recipes)} simplify recipe(s) each", end="")
        print("  (--list-recipes for what they do, -v for per-recipe detail)", end="")
    print("\n" + "=" * 60)

    results = []
    jobs = [
        (cls.__name__, recipes, want_png, strategy, testcases_dir, out_dir, delete_failed)
        for cls in classes
    ]
    with mp.get_context("spawn").Pool(processes=min(8, mp.cpu_count())) as pool:
        for r in pool.imap_unordered(run_one, jobs):
            results.append(r)
            _print_result(r, verbose)

    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    print("\n" + "=" * 60)
    print(f"PASSED: {len(passed)} / {len(results)}")
    if failed:
        print(f"FAILED: {len(failed)}")
        for r in failed:
            print(f"  {r.name}: {r.error}")

    if delete_failed:
        deleted_paths = [p for r in results if r.deleted for p in r.deleted]
        print(f"Deleted: {len(deleted_paths)} path(s) from {len(failed)} failed test(s)")

    # Sorted on the raw float. Ranking the formatted strings compared "9.7ms"
    # against "1.55s" lexicographically and called the millisecond run slower.
    timed = [r for r in results if r.seconds is not None]
    if timed:
        slow = max(timed, key=lambda r: r.seconds)
        fast = min(timed, key=lambda r: r.seconds)
        print(f"\nSlowest: {slow.name} {slow.time}   Fastest: {fast.name} {fast.time}")
    print(f"Total wall time: {round(time.time() - wall_start, 2)}s")
    _write_index(out_dir, size_charts=size_charts)


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
        "-v",
        "--verbose",
        action="store_true",
        help="Print every recipe's full result instead of one summary line per "
        "test. Without it each test shows how many recipes held, which left the "
        "fewest walls, and which failed.",
    )
    parser.add_argument(
        "--png",
        action="store_true",
        help="Also render the matplotlib per-switch PNGs. Off by default: the "
        "HTML report covers the same ground without paying matplotlib's cost "
        "per frame, which dominates a run. Use this to cross-check the report "
        "against the images, or to produce figures for the paper.",
    )
    parser.add_argument(
        "--bidirectional",
        action="store_true",
        help="Solve with the older forward+backward search instead of the "
        "single-tree mirror search. Both are exact, so the switch counts must "
        "agree; the flag exists to check that they do.",
    )
    parser.add_argument(
        "--testcases-dir",
        default=None,
        metavar="DIR",
        help="Scan DIR instead of testcases/ — for a separate series such as "
        "testcases_building_blocks/. Default: testcases/.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        metavar="DIR",
        help="Write reports into DIR instead of plots/tests/. Default: " "plots/tests/.",
    )
    parser.add_argument(
        "--no-size-charts",
        action="store_true",
        help="Skip 'Robot size vs difficulty' and 'Solve cost vs robot size' "
        "on the index page, and skip computing their data. Meaningless when "
        "many tests share one robot size, as the building-block series does.",
    )
    parser.add_argument(
        "--delete-failed",
        action="store_true",
        help="Delete a failing test's .py source file and its plots/ report "
        "folder (if any) after solving. Requires --testcases-dir, so this "
        "cannot silently delete a hand-authored case from testcases/.",
    )
    args = parser.parse_args()

    if args.delete_failed and not args.testcases_dir:
        print("--delete-failed requires --testcases-dir (refusing to touch testcases/)")
        sys.exit(1)

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

    strategy = "bidirectional" if args.bidirectional else "mirror"

    if args.name:
        name = args.name.lower()
        classes = discover_test_cases(args.testcases_dir)
        matched = [cls for cls in classes if name in cls().name.lower()]
        if not matched:
            print(f"No test case matching '{args.name}'")
            sys.exit(1)
        deleted_paths = []
        for cls in matched:
            job = (
                cls.__name__,
                recipes,
                args.png,
                strategy,
                args.testcases_dir,
                args.out_dir,
                args.delete_failed,
            )
            r = run_one(job)
            _print_result(r, args.verbose)
            if r.deleted:
                deleted_paths.extend(r.deleted)
        if args.delete_failed:
            print(f"Deleted: {len(deleted_paths)} path(s)")
        _write_index(args.out_dir, size_charts=not args.no_size_charts)
    else:
        run_all(
            recipes,
            want_png=args.png,
            verbose=args.verbose,
            strategy=strategy,
            testcases_dir=args.testcases_dir,
            out_dir=args.out_dir,
            size_charts=not args.no_size_charts,
            delete_failed=args.delete_failed,
        )
