"""
bitgrid.py
----------
A rows x cols set of cells as one Python int: bit ``r * cols + c`` is set iff
cell (r, c) is in the set.

This is the one bitmask type in the project. It serves both index spaces the
solver uses — a *cell* grid (the workspace's free cells, stride ``cols``) and a
*placement* grid (the top-left corners an n x n robot may occupy, stride
``cols - n + 1``) — and ``erode_window`` is the bridge from the first to the
second. Everything that once hand-rolled a mask (the workspace free key, the
flood fill, the valid and usable placement sets, the dig search's candidate
keys) goes through here, so the edge cases live in exactly one place: a
sideways shift must not wrap onto the neighbouring row, a membership test must
bounds-check before forming an index, and ``~`` must clip to the grid.

Why an int and not a set of tuples: one bit per cell against ~86 bytes per
tuple, and set algebra becomes single C-level operations on the whole grid —
a flood fill is a handful of shifts and ANDs per ring instead of a Python loop
per cell.
"""

from __future__ import annotations

import functools

# ── row-structured masks ─────────────────────────────────────────────────
# Pure geometry, memoised for the process: the same handful of (rows, cols)
# pairs come up for every solve on a grid.


@functools.lru_cache(maxsize=None)
def _every_row(rows: int, cols: int) -> int:
    """Bit 0 of every row. Multiplying a one-row pattern by it stamps the
    pattern into each row with no carries, since the pattern fits the row."""
    return sum(1 << (r * cols) for r in range(rows))


@functools.lru_cache(maxsize=None)
def _cols_from(rows: int, cols: int, k: int) -> int:
    """Every cell whose column is >= k."""
    if k >= cols:
        return 0
    pattern = ((1 << cols) - 1) ^ ((1 << max(k, 0)) - 1)
    return pattern * _every_row(rows, cols)


@functools.lru_cache(maxsize=None)
def _cols_below(rows: int, cols: int, k: int) -> int:
    """Every cell whose column is < k."""
    if k <= 0:
        return 0
    return ((1 << min(k, cols)) - 1) * _every_row(rows, cols)


class BitGrid:
    """An immutable set of cells on a rows x cols grid, stored as one int.

    Instances compare and hash by value, so one can key a cache directly, and
    every operation returns a new BitGrid — nothing here mutates. Two grids
    combine only when they have the same shape; a mismatch raises rather than
    silently misaligning rows.
    """

    __slots__ = ("rows", "cols", "bits")

    def __init__(self, rows: int, cols: int, bits: int = 0):
        self.rows = rows
        self.cols = cols
        self.bits = bits

    # ── constructors ─────────────────────────────────────

    @classmethod
    def empty(cls, rows: int, cols: int) -> BitGrid:
        return cls(rows, cols, 0)

    @classmethod
    def full(cls, rows: int, cols: int) -> BitGrid:
        return cls(rows, cols, (1 << (rows * cols)) - 1)

    @classmethod
    def from_cells(cls, rows: int, cols: int, cells) -> BitGrid:
        bits = 0
        for r, c in cells:
            bits |= 1 << (r * cols + c)
        return cls(rows, cols, bits)

    @classmethod
    def from_tiles(cls, tiles, predicate) -> BitGrid:
        """The cells of a 2D list whose value satisfies ``predicate``."""
        rows = len(tiles)
        cols = len(tiles[0]) if rows else 0
        bits = 0
        for r, row in enumerate(tiles):
            for c, value in enumerate(row):
                if predicate(value):
                    bits |= 1 << (r * cols + c)
        return cls(rows, cols, bits)

    # ── queries ──────────────────────────────────────────

    def index(self, r: int, c: int) -> int:
        """The bit index of cell (r, c) — the same flattening the packed state
        ids use, so an index moves between the two without translation."""
        return r * self.cols + c

    def __contains__(self, cell) -> bool:
        # Bounds first: an off-grid cell must be rejected before its index is
        # formed, or (r, -1) aliases to the last column of the row above and a
        # negative row becomes a negative shift.
        r, c = cell
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            return False
        return (self.bits >> (r * self.cols + c)) & 1 == 1

    def count(self) -> int:
        return bin(self.bits).count("1")

    def __bool__(self) -> bool:
        return self.bits != 0

    def indices(self) -> tuple:
        """The set bits as ascending indices. Isolating the lowest set bit with
        ``m & -m`` and locating it with ``bit_length`` is a few big-int ops per
        bit — fine for producing a list once, not for a per-cell hot loop."""
        out = []
        m = self.bits
        while m:
            low = m & -m
            out.append(low.bit_length() - 1)
            m ^= low
        return tuple(out)

    def cells(self):
        """The set cells as (row, col), ascending by row then column."""
        cols = self.cols
        for i in self.indices():
            yield divmod(i, cols)

    def to_tiles(self, inside: int = 1, outside: int = 0) -> list[list[int]]:
        """Materialise a 2D list, ``inside`` where a bit is set."""
        bits, cols = self.bits, self.cols
        return [
            [inside if (bits >> (r * cols + c)) & 1 else outside for c in range(cols)]
            for r in range(self.rows)
        ]

    # ── value semantics ──────────────────────────────────

    def __eq__(self, other) -> bool:
        return isinstance(other, BitGrid) and (
            (self.rows, self.cols, self.bits) == (other.rows, other.cols, other.bits)
        )

    def __hash__(self) -> int:
        return hash((self.rows, self.cols, self.bits))

    def __repr__(self) -> str:
        return f"BitGrid({self.rows}x{self.cols}, {self.count()} cells)"

    # ── set algebra ──────────────────────────────────────

    def _same_shape(self, other: BitGrid) -> None:
        if self.rows != other.rows or self.cols != other.cols:
            raise ValueError(
                f"grid shape mismatch: {self.rows}x{self.cols} vs {other.rows}x{other.cols}"
            )

    def __and__(self, other: BitGrid) -> BitGrid:
        self._same_shape(other)
        return BitGrid(self.rows, self.cols, self.bits & other.bits)

    def __or__(self, other: BitGrid) -> BitGrid:
        self._same_shape(other)
        return BitGrid(self.rows, self.cols, self.bits | other.bits)

    def __xor__(self, other: BitGrid) -> BitGrid:
        self._same_shape(other)
        return BitGrid(self.rows, self.cols, self.bits ^ other.bits)

    def __sub__(self, other: BitGrid) -> BitGrid:
        self._same_shape(other)
        return BitGrid(self.rows, self.cols, self.bits & ~other.bits)

    def __invert__(self) -> BitGrid:
        # Clipped to the grid: a bare ~ on an int would set every bit above the
        # grid too, and those would leak into any later shift down.
        return BitGrid(self.rows, self.cols, ((1 << (self.rows * self.cols)) - 1) ^ self.bits)

    # ── geometry ─────────────────────────────────────────

    def rect(self, r0: int, c0: int, height: int, width: int) -> BitGrid:
        """The cells of a rectangle, clipped to the grid — so a rectangle that
        starts above or left of the grid, or runs past its edge, is simply
        cut off rather than an error."""
        r1 = min(self.rows, r0 + height)
        c1 = min(self.cols, c0 + width)
        r0 = max(0, r0)
        c0 = max(0, c0)
        if r1 <= r0 or c1 <= c0:
            return BitGrid(self.rows, self.cols, 0)
        row_bits = ((1 << (c1 - c0)) - 1) << c0
        bits = 0
        for r in range(r0, r1):
            bits |= row_bits << (r * self.cols)
        return BitGrid(self.rows, self.cols, bits)

    def shift(self, dr: int, dc: int) -> BitGrid:
        """Every cell moved by (dr, dc). Cells pushed off the grid are dropped,
        and a sideways move never wraps onto the neighbouring row: the shifted
        bits are ANDed with the columns a genuine move can land in."""
        rows, cols, bits = self.rows, self.cols, self.bits
        if dc > 0:
            bits = (bits << dc) & _cols_from(rows, cols, dc)
        elif dc < 0:
            bits = (bits >> -dc) & _cols_below(rows, cols, cols + dc)
        if dr > 0:
            bits = (bits << (dr * cols)) & ((1 << (rows * cols)) - 1)
        elif dr < 0:
            bits >>= (-dr) * cols
        return BitGrid(rows, cols, bits)

    def flood(self, start_index: int) -> BitGrid:
        """The cells reachable from ``start_index`` by 4-neighbour steps that
        stay inside this set — bit-parallel.

        Each pass grows the reached set by one ring in all four directions at
        once: four shifts, four ANDs, three ORs on one integer, all in C. The
        number of passes is the width of the region reached, not the number of
        cells in it, which is what stops a flood's cost scaling with how much
        free space there is. Down is a shift by one row and up a shift back;
        sideways is a shift by one, pre-masked so nothing wraps onto the
        neighbouring row. Bits pushed past the top exceed every set bit and die
        in the AND; bits pushed below row 0 fall off the shift. The start cell
        is always included, whether or not it is in the set — a robot standing
        on a square can reach that square.
        """
        rows, cols, within = self.rows, self.cols, self.bits
        step_right = within & _cols_from(rows, cols, 1)
        step_left = within & _cols_below(rows, cols, cols - 1)
        reach = 1 << start_index
        while True:
            grown = (
                reach
                | ((reach << 1) & step_right)
                | ((reach >> 1) & step_left)
                | ((reach << cols) & within)
                | ((reach >> cols) & within)
            )
            if grown == reach:
                return BitGrid(rows, cols, reach)
            reach = grown

    def erode_window(self, n: int) -> BitGrid:
        """The top-left corners at which an n x n window lies entirely inside
        this set, as a *placement* grid of (rows-n+1) x (cols-n+1).

        This is the bridge from cell space to placement space. Bit i of the
        result-in-progress ANDs together cell i and its n*n - 1 window-mates,
        each brought into position with one shift of the whole grid — n*n
        operations for every placement at once, instead of n*n per placement.
        A shifted copy carries cells from the next row into the last n-1
        columns, so those columns are masked out before the rows are packed
        down to the narrower placement stride; rows past the bottom read as
        zeros and drop out on their own.
        """
        rows, cols = self.rows, self.cols
        row_span, col_span = rows - n + 1, cols - n + 1
        if row_span <= 0 or col_span <= 0:
            return BitGrid(max(row_span, 0), max(col_span, 0), 0)
        v = self.bits
        for dr in range(n):
            for dc in range(n):
                if dr or dc:
                    v &= self.bits >> (dr * cols + dc)
        v &= _cols_below(rows, cols, col_span)
        row_mask = (1 << col_span) - 1
        out = 0
        for r in range(row_span):
            out |= ((v >> (r * cols)) & row_mask) << (r * col_span)
        return BitGrid(row_span, col_span, out)
