"""
grid.py
-------
The physical environment — a 2D map of free tiles and obstacles.

Knows nothing about robots.

Stored as two BitGrids, `free` and `holes`; a boundary wall is any cell that
is neither. That is two ints for the whole map instead of a list of lists plus
a set of tuples per obstacle kind, and it is the same free mask every solver
cache keys on, so nothing has to be re-derived or kept in sync. `tiles` is a
derived view for the readers that want a 2D list; writers use the methods.
"""

from __future__ import annotations

from typing import Optional

from src.bitgrid import BitGrid

FREE = 0
BOUNDARY = 1
HOLE = -1


class Grid:
    """
    2D grid of tiles.
      0 = free
      1 = boundary (perimeter wall)
     -1 = hole / island (internal obstacle)
    Origin (0,0) is top-left.
    Row increases downward, col increases rightward.

    Two ways to create:
        Grid(tiles)             — from an existing 2D list
        Grid(rows=R, cols=C)    — all-free grid, add obstacles with the methods

    `free` is the source of truth and may be replaced wholesale — the dig
    search does exactly that, pointing one shared grid at candidate after
    candidate — because every cache downstream keys on its bits.
    """

    def __init__(
        self,
        tiles: Optional[list[list[int]]] = None,
        rows: Optional[int] = None,
        cols: Optional[int] = None,
    ):
        if tiles is not None:
            self.rows = len(tiles)
            self.cols = len(tiles[0])
            self.free = BitGrid.from_tiles(tiles, lambda v: v == FREE)
            self.holes = BitGrid.from_tiles(tiles, lambda v: v == HOLE)
        elif rows is not None and cols is not None:
            self.rows = rows
            self.cols = cols
            self.free = BitGrid.full(rows, cols)
            self.holes = BitGrid.empty(rows, cols)
        else:
            raise ValueError("Provide either tiles or both rows and cols.")

    # ── Derived views ────────────────────────────────────

    @property
    def obstacles(self) -> BitGrid:
        """Every cell that is not free — boundary and hole alike."""
        return ~self.free

    @property
    def boundaries(self) -> BitGrid:
        return ~self.free - self.holes

    @property
    def tiles(self) -> list[list[int]]:
        """The map as a 2D list of FREE / BOUNDARY / HOLE.

        Materialised on every access — it is a view, not storage. Read from it
        freely; writing into it changes a throwaway list, so mutations go
        through `add_hole`, `add_boundary`, `set_free` or by assigning `free`.
        """
        free, holes, cols = self.free.bits, self.holes.bits, self.cols
        out = []
        for r in range(self.rows):
            base = r * cols
            row = []
            for c in range(cols):
                i = base + c
                if (free >> i) & 1:
                    row.append(FREE)
                elif (holes >> i) & 1:
                    row.append(HOLE)
                else:
                    row.append(BOUNDARY)
            out.append(row)
        return out

    # ── Construction helpers ─────────────────────────────

    def add_hole(self, row: int, col: int, height: int = 1, width: int = 1):
        """Set a rectangle of cells as internal holes/islands."""
        block = self.free.rect(row, col, height, width)
        self.free = self.free - block
        self.holes = self.holes | block

    def add_boundary(self, row: int, col: int, height: int = 1, width: int = 1):
        """Set a rectangle of cells as boundary — same as add_hole but marks as BOUNDARY."""
        block = self.free.rect(row, col, height, width)
        self.free = self.free - block
        self.holes = self.holes - block

    def set_free(self, row: int, col: int, height: int = 1, width: int = 1):
        """Carve a rectangle of cells free."""
        block = self.free.rect(row, col, height, width)
        self.free = self.free | block
        self.holes = self.holes - block

    def add_rect_boundary(self):
        """Draw the full perimeter of the grid as boundary."""
        interior = self.free.rect(1, 1, self.rows - 2, self.cols - 2)
        border = BitGrid.full(self.rows, self.cols) - interior
        self.free = self.free - border
        self.holes = self.holes - border

    def get_holes(self) -> set:
        """Return set of all hole cell positions (row, col)."""
        return set(self.holes.cells())

    def get_boundaries(self) -> set:
        """Return set of all boundary cell positions (row, col)."""
        return set(self.boundaries.cells())

    def get_all_obstacles(self) -> set:
        """Return set of all obstacle positions — both holes and boundaries."""
        return set(self.obstacles.cells())

    # ── Queries ─────────────────────────────────────────

    def in_bounds(self, row: int, col: int) -> bool:
        """Is (row, col) within the grid?"""
        return 0 <= row < self.rows and 0 <= col < self.cols

    def is_free(self, row: int, col: int) -> bool:
        """Is (row, col) in bounds and not an obstacle?"""
        return (row, col) in self.free

    def is_boundary(self, row: int, col: int) -> bool:
        """Is (row, col) a boundary wall?"""
        return (
            self.in_bounds(row, col)
            and (row, col) not in self.free
            and ((row, col) not in self.holes)
        )

    def is_hole(self, row: int, col: int) -> bool:
        """Is (row, col) an internal hole / island?"""
        return (row, col) in self.holes

    def is_obstacle(self, row: int, col: int) -> bool:
        """Is (row, col) out of bounds or any kind of obstacle?"""
        return not self.is_free(row, col)

    # ── Display ─────────────────────────────────────────

    def display(self):
        """Print the raw grid. '.' = free, '#' = boundary, 'O' = hole."""
        symbols = {FREE: ".", BOUNDARY: "#", HOLE: "O"}
        print("  " + "".join(str(c % 10) for c in range(self.cols)))
        for r, row in enumerate(self.tiles):
            line = "".join(symbols[cell] for cell in row)
            print(f"{r % 10} {line}")

    # ── Dunder ──────────────────────────────────────────

    def __repr__(self):
        return f"Grid(rows={self.rows}, cols={self.cols})"


# ── Sanity check ────────────────────────────────────────

if __name__ == "__main__":
    g = Grid(rows=6, cols=8)
    g.add_boundary(0, 0, height=1, width=8)
    g.add_hole(2, 2, height=2, width=2)
    g.add_hole(1, 5)
    g.display()

    print()
    print("is_free(1,1):", g.is_free(1, 1))  # True
    print("is_boundary(0,0):", g.is_boundary(0, 0))  # True
    print("is_hole(2,2):", g.is_hole(2, 2))  # True
    print("is_obstacle(2,2):", g.is_obstacle(2, 2))  # True  (hole is also obstacle)
    print("is_obstacle(0,0):", g.is_obstacle(0, 0))  # True  (boundary is also obstacle)
