"""
Render a matrix, read it back: every reading must re-render identically, and
the true geometry must be among them whenever the picture has a state square.
"""

from __future__ import annotations

import random

import pytest

from run_tests import discover_test_cases
from src.bitgrid import BitGrid
from src.state_matrix import STATE, WALL, StateMatrix


def _dilated_free(rows, cols, free, n):
    """The best recoverable free area, as a Reading's row strings."""
    col_span = cols - n + 1
    grid = [[False] * cols for _ in range(rows)]
    for i in BitGrid.coerce(rows, cols, free).erode_window(n).indices():
        r, c = divmod(i, col_span)
        for rr in range(r, r + n):
            for cc in range(c, c + n):
                grid[rr][cc] = True
    return tuple("".join("." if f else "#" for f in row) for row in grid)


def _check_roundtrip(rows, cols, free, n):
    matrix = StateMatrix.render(rows, cols, free, n)
    if all(ch == WALL for row in matrix.cells for ch in row):
        return  # no corner fits anywhere: there is nothing to read back
    found = matrix.reconstruct()
    assert found, "a non-empty matrix must have at least one reading"
    for r in found:
        redrawn = StateMatrix.render(r.rows, r.cols, r.free_cells, r.n)
        assert redrawn.cells == matrix.cells, (r.rows, r.cols, r.n)
    if not any(STATE in row for row in matrix.cells):
        return  # no states: the picture pins no single geometry
    expected = _dilated_free(rows, cols, free, n)
    assert any((r.rows, r.cols, r.n) == (rows, cols, n) and r.free == expected for r in found), (
        rows,
        cols,
        n,
    )


def test_roundtrip_on_random_boards():
    rng = random.Random(7)
    for _ in range(60):
        rows, cols = rng.randint(2, 6), rng.randint(2, 6)
        n = rng.randint(1, 2)
        free = {(r, c) for r in range(rows) for c in range(cols) if rng.random() < 0.8}
        _check_roundtrip(rows, cols, free, n)


@pytest.mark.parametrize("case", discover_test_cases(), ids=lambda case: case.name)
def test_roundtrip_on_the_shipped_cases(case):
    ws, _goal_a, _goal_b = case().setup()
    _check_roundtrip(ws.grid.rows, ws.grid.cols, ws.grid.free, ws.robot_a.n)


def test_start_marker_reads_back_as_a_workspace():
    rows, cols, n = 3, 4, 2
    col_span = cols - n + 1
    free = {(r, c) for r in range(rows) for c in range(cols)}
    matrix = StateMatrix.render(rows, cols, free, n)
    a, b = (0, 0), (1, 2)
    start = (a[0] * col_span + a[1], b[0] * col_span + b[1])
    found = [r for r in matrix.reconstruct(start=start) if (r.rows, r.cols, r.n) == (rows, cols, n)]
    assert found and found[0].pos_a == a and found[0].pos_b == b
    ws = found[0].workspace()
    assert (ws.grid.rows, ws.grid.cols) == (rows, cols)
    assert ws.robot_a.position() == a and ws.robot_b.position() == b
    assert ws.robot_a.n == n


def test_workspace_without_a_start_marker_refuses():
    matrix = StateMatrix.render(2, 3, {(r, c) for r in range(2) for c in range(3)}, 1)
    reading = matrix.reconstruct()[0]
    with pytest.raises(ValueError):
        reading.workspace()


def test_one_by_one_robots_are_ambiguous_by_design():
    # n = 1: the x squares carry no geometry, 2x3 and 3x2 both read back.
    free = {(r, c) for r in range(2) for c in range(3)}
    matrix = StateMatrix.render(2, 3, free, 1)
    dims = {(r.rows, r.cols) for r in matrix.reconstruct()}
    assert (2, 3) in dims and (3, 2) in dims
