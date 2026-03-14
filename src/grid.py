"""
grid.py
-------
The physical environment — a 2D map of free tiles and obstacles.

Knows nothing about robots.
"""


class Grid:
    """
    2D grid of tiles.
      0 = free
      1 = obstacle
    Origin (0,0) is top-left.
    Row increases downward, col increases rightward.
    """

    def __init__(self, tiles: list[list[int]]):
        """
        tiles: 2D list of ints.
               tiles[row][col] = 0 (free) or 1 (obstacle)
        """
        self.tiles = tiles
        self.rows  = len(tiles)
        self.cols  = len(tiles[0])

    # ── Queries ─────────────────────────────────────────

    def in_bounds(self, row: int, col: int) -> bool:
        """Is (row, col) within the grid?"""
        return 0 <= row < self.rows and 0 <= col < self.cols

    def is_free(self, row: int, col: int) -> bool:
        """Is (row, col) in bounds and not an obstacle?"""
        return self.in_bounds(row, col) and self.tiles[row][col] == 0

    def is_obstacle(self, row: int, col: int) -> bool:
        """Is (row, col) out of bounds or an obstacle?"""
        return not self.is_free(row, col)

    # ── Display ─────────────────────────────────────────

    def display(self):
        """Print the raw grid. '.' = free, '#' = obstacle."""
        print("  " + "".join(str(c % 10) for c in range(self.cols)))
        for r, row in enumerate(self.tiles):
            line = "".join('.' if cell == 0 else '#' for cell in row)
            print(f"{r % 10} {line}")

    # ── Dunder ──────────────────────────────────────────

    def __repr__(self):
        return f"Grid(rows={self.rows}, cols={self.cols})"


# ── Sanity check ────────────────────────────────────────

if __name__ == "__main__":
    tiles = [
        [1, 1, 1, 1, 1],
        [1, 0, 0, 0, 1],
        [1, 1, 0, 1, 1],
        [1, 1, 1, 1, 1],
    ]
    g = Grid(tiles)
    print(g)
    g.display()

    print("in_bounds(1,1):",  g.in_bounds(1, 1))   # True
    print("in_bounds(9,9):",  g.in_bounds(9, 9))   # False
    print("is_free(1,1):",    g.is_free(1, 1))      # True
    print("is_free(0,0):",    g.is_free(0, 0))      # False (obstacle)
    print("is_obstacle(0,0):", g.is_obstacle(0, 0)) # True