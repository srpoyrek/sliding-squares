"""
state_matrix.py
---------------
Render the solvability page's wall/overlap/state picture, and read such a
picture back into every workspace that draws exactly it. Axes are placement
corners; the x squares pin (placement width, n); the free area is the union
of the standable corners' footprints. Cells no footprint covers return as
walls. Ambiguous pictures (n = 1, or no state square) return every reading.
"""

from __future__ import annotations

from src.bitgrid import BitGrid
from src.workspace import Workspace

WALL, OVERLAP, STATE = "#", "x", "."


class Reading:
    """One workspace a matrix reads back to. `free` is row strings,
    `free_cells` the (row, col) set BitGrid.coerce takes."""

    def __init__(self, rows, cols, n, free, free_cells, pos_a=None, pos_b=None):
        self.rows = rows
        self.cols = cols
        self.n = n
        self.free = free
        self.free_cells = free_cells
        self.pos_a = pos_a
        self.pos_b = pos_b

    def __repr__(self):
        return f"Reading({self.rows}x{self.cols}, n={self.n})"

    def workspace(self) -> Workspace:
        """The reading as a Workspace; needs the start marker for positions."""
        if self.pos_a is None or self.pos_b is None:
            raise ValueError("no start marker was given to reconstruct()")
        return Workspace.from_free_cells(
            self.rows, self.cols, self.free_cells, self.pos_a, self.pos_b, self.n
        )


class StateMatrix:
    """The picture as row strings: row = A's corner, column = B's."""

    def __init__(self, cells):
        span = len(cells)
        if any(len(row) != span for row in cells):
            raise ValueError("the matrix must be square")
        self.cells = tuple(cells)
        self.span = span

    @classmethod
    def render(cls, rows: int, cols: int, free, n: int) -> StateMatrix:
        """WALL where a corner cannot hold the robot, OVERLAP on collision,
        STATE otherwise."""
        valid = set(BitGrid.coerce(rows, cols, free).erode_window(n).indices())
        col_span = cols - n + 1
        span = (rows - n + 1) * col_span
        out = []
        for a in range(span):
            ra, ca = divmod(a, col_span)
            row = []
            for b in range(span):
                rb, cb = divmod(b, col_span)
                if a not in valid or b not in valid:
                    row.append(WALL)
                elif abs(ra - rb) < n and abs(ca - cb) < n:
                    row.append(OVERLAP)
                else:
                    row.append(STATE)
            out.append("".join(row))
        return cls(out)

    @classmethod
    def for_workspace(cls, ws) -> StateMatrix:
        """The matrix for a Workspace's grid and robot size."""
        return cls.render(ws.grid.rows, ws.grid.cols, ws.grid.free, ws.robot_a.n)

    def reconstruct(self, start: tuple | None = None) -> list:
        """Every workspace that draws this picture, as `Reading`s; `start` is
        the marked square as (row index, column index)."""
        cells, span = self.cells, self.span
        valid = [i for i in range(span) if any(ch != WALL for ch in cells[i])]
        vset = set(valid)
        for i in range(span):
            if (i in vset) != any(cells[a][i] != WALL for a in range(span)):
                raise ValueError("wall rows and wall columns disagree: not a state matrix")
        found = []
        for col_span in range(1, span + 1):
            if span % col_span:
                continue
            row_span = span // col_span
            # Larger n only restate a saturated picture on a bigger board.
            for n in range(1, max(row_span, col_span) + 1):
                reading = self._try(valid, row_span, col_span, n)
                if reading is None:
                    continue
                if start is not None:
                    reading.pos_a = divmod(start[0], col_span)
                    reading.pos_b = divmod(start[1], col_span)
                found.append(reading)
        return found

    def _try(self, valid, row_span, col_span, n):
        """One (placement grid, n) reading, or None on contradiction."""
        cells = self.cells
        for a in valid:
            ra, ca = divmod(a, col_span)
            for b in valid:
                rb, cb = divmod(b, col_span)
                touches = abs(ra - rb) < n and abs(ca - cb) < n
                if touches != (cells[a][b] == OVERLAP):
                    return None
        rows, cols = row_span + n - 1, col_span + n - 1
        free = [[False] * cols for _ in range(rows)]
        for i in valid:
            r, c = divmod(i, col_span)
            for rr in range(r, r + n):
                for cc in range(c, c + n):
                    free[rr][cc] = True
        # Every wall corner must genuinely fail to fit on that free area.
        vset = set(valid)
        for i in range(row_span * col_span):
            if i in vset:
                continue
            r, c = divmod(i, col_span)
            if all(free[rr][cc] for rr in range(r, r + n) for cc in range(c, c + n)):
                return None
        return Reading(
            rows,
            cols,
            n,
            tuple("".join("." if f else "#" for f in row) for row in free),
            frozenset((r, c) for r in range(rows) for c in range(cols) if free[r][c]),
        )
