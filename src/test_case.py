"""
test_case.py
------------
Base class for all test cases.
Every test case in testcases/ subclasses this.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TestResult:
    # Not a pytest test class despite the name — it is the solver harness's
    # result record. pytest matches on the `Test` prefix and would try to
    # collect it, warning that a class with __init__ cannot be collected.
    __test__ = False

    name: str
    passed: bool
    plot_path: Optional[str] = None
    error: Optional[str] = None
    time: Optional[str] = None  # human-readable, e.g. "1.5ms" — display only
    seconds: Optional[float] = None  # raw elapsed; sort and compare on THIS
    simplification: Optional[list] = None  # one status dict per recipe run
    report_path: Optional[str] = None  # the run's index.html (see src/report.py)

    def __repr__(self):
        status = "PASS" if self.passed else "FAIL"
        parts = [f"[{status}] {self.name}"]
        if self.time is not None:
            parts.append(f"Solver time={self.time}s")
        if self.error:
            parts.append(f"error={self.error!r}")
        return "  ".join(parts)


class TestCase:
    """
    Subclass this and implement setup().

    Minimal example:

        class MyTest(TestCase):
            name = "trivial 1x1"

            def setup(self):
                tiles = [[1,1,0,1,1],[1,0,0,0,1],[1,1,1,1,1]]
                grid  = Grid(tiles)
                a     = Robot('A', 1, 1, 1)
                b     = Robot('B', 1, 1, 3)
                ws    = Workspace(grid, a, b)
                return ws, (1,3), (1,1)
    """

    __test__ = False  # a solver test case, not a pytest one — see TestResult

    name: str = "unnamed"

    def setup(self):
        raise NotImplementedError
