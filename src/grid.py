"""
grid.py
-------
The physical environment — a 2D map of free tiles and obstacles.

Knows nothing about robots.
"""

from __future__ import annotations

from typing import Optional

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
        Grid(tiles)             — from existing 2D list (backward compatible)
        Grid(rows=R, cols=C)    — empty grid, add obstacles manually
    """

    def __init__(
        self,
        tiles: Optional[list[list[int]]] = None,
        rows: Optional[int] = None,
        cols: Optional[int] = None,
    ):
        if tiles is not None:
            self.tiles = tiles
            self.rows = len(tiles)
            self.cols = len(tiles[0])
        elif rows is not None and cols is not None:
            self.rows = rows
            self.cols = cols
            self.tiles = [[0] * cols for _ in range(rows)]
        else:
            raise ValueError("Provide either tiles or both rows and cols.")

    # ── Construction helpers ─────────────────────────────
    def add_hole(self, row: int, col: int, height: int = 1, width: int = 1):
        """Set a rectangle of cells as internal holes/islands."""
        for dr in range(height):
            for dc in range(width):
                self.tiles[row + dr][col + dc] = HOLE

    def add_boundary(self, row: int, col: int, height: int = 1, width: int = 1):
        """Set a rectangle of cells as boundary — same as add_hole but marks as BOUNDARY."""
        for dr in range(height):
            for dc in range(width):
                self.tiles[row + dr][col + dc] = BOUNDARY

    def add_rect_boundary(self):
        """Draw the full perimeter of the grid as boundary."""
        for c in range(self.cols):
            self.tiles[0][c] = BOUNDARY
            self.tiles[self.rows - 1][c] = BOUNDARY
        for r in range(1, self.rows - 1):
            self.tiles[r][0] = BOUNDARY
            self.tiles[r][self.cols - 1] = BOUNDARY

    # ── Queries ─────────────────────────────────────────

    def in_bounds(self, row: int, col: int) -> bool:
        """Is (row, col) within the grid?"""
        return 0 <= row < self.rows and 0 <= col < self.cols

    def is_free(self, row: int, col: int) -> bool:
        """Is (row, col) in bounds and not an obstacle?"""
        return self.in_bounds(row, col) and self.tiles[row][col] == FREE

    def is_boundary(self, row: int, col: int) -> bool:
        """Is (row, col) a boundary wall?"""
        return self.in_bounds(row, col) and self.tiles[row][col] == BOUNDARY

    def is_hole(self, row: int, col: int) -> bool:
        """Is (row, col) an internal hole / island?"""
        return self.in_bounds(row, col) and self.tiles[row][col] == HOLE

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
