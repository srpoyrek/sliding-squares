"""
frontier.py
-----------
Frontier helpers for grow / dig searches over a free region.

`initial_frontier` is the ring of blocked cells directly adjacent to the free
region; `extend_frontier` updates that ring after cells are dug free. Both take
and return `BitGrid`s, so a search that carries its candidate regions as masks
never has to inflate one into a set of (row, col) tuples to ask what it may dig
next — which is what a dig search does once per node, for every node.

Neither function needs a Grid or a Workspace: a ring is a property of the free
region and the grid shape alone.
"""

from __future__ import annotations

from src.bitgrid import BitGrid


def initial_frontier(free: BitGrid) -> BitGrid:
    """Blocked cells orthogonally adjacent to the free region.

    The region grown by one ring, minus the region itself. `dilate` drops
    whatever falls off an edge, so a cell outside the grid can never enter the
    frontier and no explicit bounds test is needed.
    """
    return free.dilate() - free


def extend_frontier(frontier: BitGrid, dug: BitGrid, free_after: BitGrid) -> BitGrid:
    """The frontier after `dug` becomes free.

    The dug cells' still-blocked orthogonal neighbours join the ring, and every
    cell that is now free leaves it — including the dug cells themselves, which
    is why one subtraction of `free_after` covers both.
    """
    return (frontier | dug.dilate()) - free_after
