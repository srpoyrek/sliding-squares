"""
frontier.py
-----------
Frontier helpers for grow / dig searches over a free-cell region.

`initial_frontier` is the ring of obstacle cells directly adjacent to the free
region; `extend_frontier` updates that ring after one cell is dug free. Both are
pure functions on (cells, rows, cols) — no Grid or Workspace needed.
"""

from __future__ import annotations


def initial_frontier(rows, cols, free_cells):
    """Obstacle cells orthogonally adjacent to the free region."""
    front = set()
    for r, c in free_cells:
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if not (0 <= nr < rows and 0 <= nc < cols):
                continue
            cell = (nr, nc)
            if cell in free_cells:
                continue
            front.add(cell)
    return frozenset(front)


def extend_frontier(frontier, dug_cell, free_cells_after, rows, cols):
    """Frontier after `dug_cell` becomes free: drop it, add its still-blocked
    orthogonal neighbours."""
    new_front = set(frontier)
    new_front.discard(dug_cell)
    r, c = dug_cell
    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nr, nc = r + dr, c + dc
        if not (0 <= nr < rows and 0 <= nc < cols):
            continue
        cell = (nr, nc)
        if cell in free_cells_after:
            continue
        new_front.add(cell)
    return frozenset(new_front)
