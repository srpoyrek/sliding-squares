"""
solvability.py
--------------
Decides whether the two robots can swap in a workspace — for one start, or for
every start pair at once — without searching for a path.

The swap is a connectivity question. Take the graph whose nodes are the
non-overlapping placement pairs (pos_a, pos_b) and whose edges are one robot
sliding one step while the other stands still. Sliding is reversible, so the
graph is undirected and its connected components decide everything: the start
(a, b) can swap iff (b, a) lies in the same component.

Exchanging the two labels — the symmetry `bfs_mirror` runs on — maps the graph
onto itself, so it maps components onto components. A component is therefore
either closed under the exchange or disjoint from its own image. In a closed
one every state X is a *swap combination*: X and its exchange are both
reachable from the start, which is exactly the meeting `bfs_mirror` tests its
frontier for, and the route to the exchange, relabelled and reversed, is the
second half of the swap. In a disjoint one no state is. Solvability is thus a
property of the component, and one swap combination anywhere in it settles it.

The graph is never built edge by edge. With one robot parked at q, the other
moves freely inside each connected piece of the placements usable around q, so
all states with that piece on one side and q on the other form a clique — one
union-find set. A piece is one bit-parallel flood and one union per member, so
the whole graph costs one flood per piece and O(|states|) unions, never a
successor enumeration per state.

Which robot moved last is ignored here: it changes the switch count, never
whether a state can be reached, since a robot may be handed control and not
move.
"""

from __future__ import annotations

from array import array
from typing import Iterator

from src.bitgrid import BitGrid
from src.canonical import blocks_overlap


def _pieces(region: BitGrid) -> Iterator[BitGrid]:
    """The connected pieces of `region`, one BitGrid each: flood from the lowest
    remaining bit, subtract, repeat."""
    rest = region
    while rest:
        piece = rest.flood((rest.bits & -rest.bits).bit_length() - 1)
        yield piece
        rest = rest - piece


class SwapSolvability:
    """The components of a workspace's configuration graph, and the exchange
    test that turns them into swap solvability.

    Build once per (free region, n); each query is then a few union-find
    lookups. `free` is a BitGrid, its bits, or an iterable of (row, col) —
    the forms `Workspace.from_free_cells` takes. Positions are top-left corners
    in the placement grid, as everywhere else in the project.

    Attributes:
        valid  : the n x n placements over `free`, a placement BitGrid
        states : non-overlapping ordered placement pairs — the graph's nodes
        floods : flood fills run to build the map, one per clique joined — the
                 build's cost in the same unit a solve pays its floods in
    """

    def __init__(self, rows: int, cols: int, free, n: int):
        self.rows = rows
        self.cols = cols
        self.n = n
        self.free = BitGrid.coerce(rows, cols, free)
        self.valid = self.free.erode_window(n)
        self._col_span = self.valid.cols
        self._max_pos = self.valid.rows * self.valid.cols
        # One entry per ordered placement pair, overlapping pairs included as
        # never-touched singletons: a state id is then a plain multiply-add,
        # and 8 bytes each is what keeps V^2 entries affordable.
        self._parent = array("q", range(self._max_pos * self._max_pos))
        self.states = 0
        self.floods = 0
        self._build()

    @classmethod
    def for_workspace(cls, ws) -> SwapSolvability:
        """The map for a Workspace's grid and robot size."""
        return cls(ws.grid.rows, ws.grid.cols, ws.grid.free, ws.robot_a.n)

    # ── build ────────────────────────────────────────────

    def _build(self) -> None:
        valid, n, max_pos, col_span = self.valid, self.n, self._max_pos, self._col_span
        union = self._union
        for parked in valid.indices():
            r, c = divmod(parked, col_span)
            # Every placement that does not overlap the parked robot — the
            # same set `bfs._usable` floods: two n x n squares overlap exactly
            # when both offsets are below n, a (2n-1) x (2n-1) block of indices.
            usable = valid - valid.rect(r - n + 1, c - n + 1, 2 * n - 1, 2 * n - 1)
            self.states += usable.count()
            for piece in _pieces(usable):
                self.floods += 1
                members = piece.indices()
                head = members[0]
                # Both roles at once: the parked robot is B and A roams the
                # piece — states (p, parked) — or it is A and B roams — states
                # (parked, q). The squares are the same size, so the piece is
                # the same either way.
                for m in members[1:]:
                    union(head * max_pos + parked, m * max_pos + parked)
                    union(parked * max_pos + head, parked * max_pos + m)

    def _find(self, x: int) -> int:
        parent = self._parent
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def _union(self, x: int, y: int) -> None:
        rx, ry = self._find(x), self._find(y)
        if rx != ry:
            self._parent[ry] = rx

    # ── state ids ────────────────────────────────────────

    def _state(self, pos_a, pos_b) -> int:
        """The id of (pos_a, pos_b), refusing anything that is not a state: a
        robot not fitting where it stands, or the two overlapping."""
        if pos_a not in self.valid or pos_b not in self.valid:
            raise ValueError(f"not an n x n placement over the free region: {pos_a}, {pos_b}")
        if blocks_overlap(pos_a, pos_b, self.n):
            raise ValueError(f"robots overlap: {pos_a}, {pos_b}")
        ai = pos_a[0] * self._col_span + pos_a[1]
        bi = pos_b[0] * self._col_span + pos_b[1]
        return ai * self._max_pos + bi

    def _exchange(self, state: int) -> int:
        """The state with the two labels exchanged — `bfs_mirror`'s mirror,
        without the control bit."""
        ai, bi = divmod(state, self._max_pos)
        return bi * self._max_pos + ai

    def _pair(self, state: int) -> tuple:
        ai, bi = divmod(state, self._max_pos)
        return divmod(ai, self._col_span), divmod(bi, self._col_span)

    def _all_states(self) -> Iterator[int]:
        """Every state id — the ordered non-overlapping placement pairs."""
        placements = self.valid.indices()
        n, max_pos, col_span = self.n, self._max_pos, self._col_span
        for ai in placements:
            a = divmod(ai, col_span)
            for bi in placements:
                if blocks_overlap(a, divmod(bi, col_span), n):
                    continue
                yield ai * max_pos + bi

    # ── queries ──────────────────────────────────────────

    def solvable(self, pos_a, pos_b) -> bool:
        """Can A at `pos_a` and B at `pos_b` end up exchanged? True iff the
        start's component contains its own exchange."""
        state = self._state(pos_a, pos_b)
        return self._find(state) == self._find(self._exchange(state))

    def is_swap_combination(self, start, candidate) -> bool:
        """Is `candidate` a swap combination for `start`: reachable from it,
        with its exchange reachable too? Then the route to the exchange,
        relabelled and run backwards, carries `candidate` on to the exchanged
        start — the join `bfs_mirror` makes at its meeting state.

        Symmetric in its two arguments, and constant across a component: true
        of every other state in a solvable start's component, false of every
        state in an unsolvable one. A swap combination is a second state, so
        the same state on both sides is refused; `solvable` answers that.
        """
        root = self._find(self._state(*start))
        target = self._state(*candidate)
        if target == self._state(*start):
            raise ValueError(f"a swap combination is a second state, not the start: {start}")
        return root == self._find(target) and root == self._find(self._exchange(target))

    def swap_combinations(self, pos_a, pos_b) -> list:
        """Every swap combination for the start, as ((ra, ca), (rb, cb)) pairs —
        the rest of the component when the start can swap, the start itself
        not listed against itself, and nothing when it cannot."""
        state = self._state(pos_a, pos_b)
        root = self._find(state)
        if root != self._find(self._exchange(state)):
            return []
        found = (s for s in self._all_states() if s != state and self._find(s) == root)
        return [self._pair(s) for s in found]

    def solvable_starts(self) -> Iterator[tuple]:
        """Every ordered (pos_a, pos_b) from which the robots can swap. (a, b)
        and (b, a) are two starts and both are listed: the swap is the same
        either way, but which robot is A — and so moves first — is not."""
        for s in self._all_states():
            if self._find(s) == self._find(self._exchange(s)):
                yield self._pair(s)
