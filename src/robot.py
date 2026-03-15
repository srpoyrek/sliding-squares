"""
robot.py
--------
A single n×n square robot.

Knows only:
  - its label
  - its size
  - its current position (top-left corner)

Does NOT know about:
  - the grid
  - other robots
  - whether a move is valid
"""


class Robot:
    """
    An n×n square robot on a grid.
    Position is the (row, col) of its top-left corner.
    """

    def __init__(self, label: str, n: int, row: int, col: int):
        """
        label : name, e.g. 'A' or 'B'
        n     : edge length in tiles
        row   : top-left row
        col   : top-left col
        """
        self.label = label
        self.n = n
        self.row = row
        self.col = col

    # ── Queries ─────────────────────────────────────────

    def position(self) -> tuple[int, int]:
        """Top-left corner (row, col)."""
        return (self.row, self.col)

    def cells(self) -> list[tuple[int, int]]:
        """All (row, col) tiles this robot occupies."""
        return [(self.row + dr, self.col + dc) for dr in range(self.n) for dc in range(self.n)]

    # ── Clone (for BFS) ─────────────────────────────────

    def clone(self) -> "Robot":
        """Return an independent copy of this robot."""
        return Robot(self.label, self.n, self.row, self.col)

    # ── Dunder ──────────────────────────────────────────

    def __repr__(self):
        return f"Robot(label={self.label!r}, n={self.n}, " f"row={self.row}, col={self.col})"

    def __eq__(self, other):
        return self.label == other.label and self.n == other.n

    def __hash__(self):
        return hash((self.label, self.n))


# ── Sanity check ────────────────────────────────────────

if __name__ == "__main__":
    a = Robot("A", 2, 1, 1)
    print(a)
    print("position:", a.position())
    print("cells:", a.cells())

    b = a.clone()
    b.row += 1
    print("original:", a)
    print("clone after row+=1:", b)
    print("b position:", b.position())
    print("b cells:", b.cells())
