"""
test_case.py
------------
Base class for all test cases.
Every test case in testcases/ subclasses this.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TestResult:
    name: str
    passed: bool
    plot_path: Optional[str] = None
    error: Optional[str] = None

    def __repr__(self):
        status = "PASS" if self.passed else "FAIL"
        parts = [f"[{status}] {self.name}"]
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

    name: str = "unnamed"

    def setup(self):
        raise NotImplementedError
