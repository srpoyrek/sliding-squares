"""
run_tests.py
------------
Discovers all test cases in testcases/ and runs them.

Usage:
    python run_tests.py
"""

import inspect
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.directories import get_plots_dir, get_testcases_dir
from src.solver import Solver
from src.test_case import TestCase, TestResult
from src.validator import Validator
from src.visualizer import draw_sequence


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


def run_one(cls: type) -> TestResult:
    tc = cls()
    result = TestResult(name=tc.name, passed=False)

    try:
        ws, goal_a, goal_b = tc.setup()

        solver_result = Solver(ws, goal_a, goal_b).solve()
        if not solver_result.solvable:
            result.error = "Solver returned solvable=False"
            return result

        vr = Validator(ws, goal_a, goal_b).run(solver_result.path, plot=False)
        if not vr.valid:
            result.error = f"Path invalid: {vr.failed_reason}"
            return result

        plots_tests_dir = os.path.join(get_plots_dir(), "tests")
        os.makedirs(plots_tests_dir, exist_ok=True)
        plot_file = os.path.join(plots_tests_dir, f"{tc.name.replace(' ', '_')}.png")

        snapshots = [[a, b] for a, b in vr.snapshots]
        draw_sequence(
            ws.grid,
            snapshots,
            titles=vr.titles,
            save_path=plot_file,
            robot_size=ws.robot_a.n,
        )
        result.plot_path = plot_file
        result.passed = True

    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        traceback.print_exc()

    return result


def run_all():
    classes = discover_test_cases()

    if not classes:
        print("No test cases found in testcases/")
        return

    print(f"Found {len(classes)} test case(s)\n")
    print("=" * 60)

    results = []
    for cls in classes:
        r = run_one(cls)
        results.append(r)
        print(r)
        if r.plot_path:
            print(f"         plot -> {r.plot_path}")

    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    print("\n" + "=" * 60)
    print(f"PASSED: {len(passed)} / {len(results)}")
    if failed:
        print(f"FAILED: {len(failed)}")
        for r in failed:
            print(f"  {r.name}: {r.error}")


if __name__ == "__main__":
    run_all()
