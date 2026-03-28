"""
run_tests.py
------------
Discovers all test cases in testcases/ and runs them.

Usage:
    python run_tests.py
"""

from __future__ import annotations

import inspect
import multiprocessing as mp
import os
import sys
import time
import traceback

from src.directories import get_plots_dir, get_testcases_dir
from src.solver import Solver
from src.test_case import TestCase, TestResult
from src.validator import Validator
from src.visualizer import draw_sequence

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


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


def run_one(cls_name: str) -> TestResult:
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

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        traceback.print_exc()

    return result


def run_all():
    wall_start = time.time()
    classes = discover_test_cases()

    if not classes:
        print("No test cases found in testcases/")
        return

    print(f"Found {len(classes)} test case(s)\n")
    print("=" * 60)

    results = []
    with mp.get_context("spawn").Pool(processes=min(8, mp.cpu_count())) as pool:
        for r in pool.imap_unordered(run_one, [cls.__name__ for cls in classes]):
            results.append(r)
            print(r, flush=True)
            if r.plot_path:
                print(f"         plot -> {r.plot_path}", flush=True)

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
        print(f"\nSlowest: {max(times)}  Fastest: {min(times)}")
    print(f"\nTotal wall time: {round(time.time() - wall_start, 2)}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        name = sys.argv[1].lower()
        classes = discover_test_cases()
        matched = [cls for cls in classes if name in cls().name.lower()]
        if not matched:
            print(f"No test case matching '{sys.argv[1]}'")
            sys.exit(1)
        for cls in matched:
            r = run_one(cls.__name__)
            print(r)
            if r.plot_path:
                print(f"         plot -> {r.plot_path}")
    else:
        run_all()
