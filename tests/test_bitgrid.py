"""
Proves BitGrid's primitives against brute-force loops on small grids.

Every operation the solver leans on — shift, rect, flood, erode_window — is
checked cell by cell against the obvious Python implementation, on random
grids and on the shapes that break bit tricks: one column wide, one row tall,
edges, and a serpentine corridor whose width is far larger than its area
would suggest. If these hold, the searches built on them see exactly the
sets they would have seen from the tuple code they replaced.
"""

from __future__ import annotations

import random
from collections import deque

import pytest

from src.bitgrid import BitGrid

SHAPES = [(1, 1), (1, 7), (7, 1), (3, 5), (5, 3), (8, 8), (6, 11)]


def _random_grid(rng, rows, cols, density=0.6):
    cells = {(r, c) for r in range(rows) for c in range(cols) if rng.random() < density}
    return cells, BitGrid.from_cells(rows, cols, cells)


def _brute_shift(cells, rows, cols, dr, dc):
    return {(r + dr, c + dc) for r, c in cells if 0 <= r + dr < rows and 0 <= c + dc < cols}


def _brute_flood(cells, rows, cols, start):
    seen = {start}
    queue = deque([start])
    while queue:
        r, c = queue.popleft()
        for nr, nc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if (nr, nc) in cells and (nr, nc) not in seen:
                seen.add((nr, nc))
                queue.append((nr, nc))
    return seen


def _brute_erode(cells, rows, cols, n):
    return {
        (r, c)
        for r in range(rows - n + 1)
        for c in range(cols - n + 1)
        if all((r + dr, c + dc) in cells for dr in range(n) for dc in range(n))
    }


@pytest.mark.parametrize("rows,cols", SHAPES)
def test_cells_round_trip_and_membership(rows, cols):
    rng = random.Random(rows * 31 + cols)
    cells, g = _random_grid(rng, rows, cols)
    assert set(g.cells()) == cells
    assert g.count() == len(cells)
    assert all((r, c) in g for r, c in cells)
    # Off-grid cells are never members, even where an index would alias.
    assert (-1, 0) not in g and (0, -1) not in g
    assert (rows, 0) not in g and (0, cols) not in g
    assert g.to_tiles() == [[1 if (r, c) in cells else 0 for c in range(cols)] for r in range(rows)]


@pytest.mark.parametrize("rows,cols", SHAPES)
def test_shift_matches_brute_force_and_never_wraps(rows, cols):
    rng = random.Random(rows * 7 + cols)
    cells, g = _random_grid(rng, rows, cols)
    for dr in range(-2, 3):
        for dc in range(-2, 3):
            assert set(g.shift(dr, dc).cells()) == _brute_shift(cells, rows, cols, dr, dc), (dr, dc)
    # The classic failure: a full row shifted sideways must lose exactly one
    # column, not spill into the row below.
    full = BitGrid.full(rows, cols)
    assert full.shift(0, 1).count() == rows * max(cols - 1, 0)
    assert full.shift(0, -1).count() == rows * max(cols - 1, 0)


@pytest.mark.parametrize("rows,cols", SHAPES)
def test_rect_clips_to_grid(rows, cols):
    g = BitGrid.empty(rows, cols)
    for r0, c0, h, w in [
        (0, 0, rows, cols),
        (-2, -2, 3, 3),
        (rows - 1, cols - 1, 5, 5),
        (1, 1, 0, 3),
    ]:
        expect = {
            (r, c)
            for r in range(max(r0, 0), min(rows, r0 + h))
            for c in range(max(c0, 0), min(cols, c0 + w))
        }
        assert set(g.rect(r0, c0, h, w).cells()) == expect, (r0, c0, h, w)


def test_invert_and_algebra_clip_to_grid():
    g = BitGrid.from_cells(3, 4, {(0, 0), (2, 3)})
    assert (~g).count() == 12 - 2
    assert ~~g == g
    assert (g | ~g) == BitGrid.full(3, 4)
    assert (g & ~g) == BitGrid.empty(3, 4)
    assert (BitGrid.full(3, 4) - g) == ~g
    with pytest.raises(ValueError):
        _ = g & BitGrid.empty(4, 3)


@pytest.mark.parametrize("rows,cols", SHAPES)
def test_flood_matches_queue_bfs(rows, cols):
    rng = random.Random(rows * 13 + cols)
    for _ in range(20):
        cells, g = _random_grid(rng, rows, cols, density=0.7)
        start = (rng.randrange(rows), rng.randrange(cols))
        reached = set(g.flood(g.index(*start)).cells())
        # The start is always included, as the queue BFS includes it.
        assert reached == _brute_flood(cells | {start}, rows, cols, start), start


def test_flood_serpentine_needs_many_passes_but_is_exact():
    # A corridor that snakes back and forth: its reachable set is small in
    # area but very long in path, so a flood that stopped early would miss
    # the far end.
    rows, cols = 9, 9
    cells = set()
    for r in range(0, rows, 2):
        cells |= {(r, c) for c in range(cols)}
    for r in range(1, rows, 2):
        cells.add((r, cols - 1 if (r // 2) % 2 == 0 else 0))
    g = BitGrid.from_cells(rows, cols, cells)
    assert set(g.flood(g.index(0, 0)).cells()) == cells


@pytest.mark.parametrize("rows,cols", SHAPES)
@pytest.mark.parametrize("n", [1, 2, 3])
def test_erode_window_matches_placement_scan(rows, cols, n):
    rng = random.Random(rows * 17 + cols * 3 + n)
    cells, g = _random_grid(rng, rows, cols, density=0.8)
    eroded = g.erode_window(n)
    assert (eroded.rows, eroded.cols) == (max(rows - n + 1, 0), max(cols - n + 1, 0))
    assert set(eroded.cells()) == _brute_erode(cells, rows, cols, n)


def test_erode_window_full_grid_is_every_placement():
    g = BitGrid.full(5, 6)
    assert g.erode_window(2).count() == 4 * 5
    assert g.erode_window(1) == BitGrid.full(5, 6)
    assert g.erode_window(7).count() == 0
