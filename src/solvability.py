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

The build also remembers its proof pairs — the two states whose joining caused
each pointer write. Those pairs form a spanning trail of every island, so
`trail` can replay a legal solution between any two states with no search at
all; its switch count follows the filing order, not the minimum. When the
minimum is wanted, `shortest_trail` / `min_switches` run breadth-first over the
stored cliques themselves — far fewer nodes than states — and return a provably
switch-minimal solution, cross-checked against the solver in the tests.
"""

from __future__ import annotations

from array import array
from collections import deque
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
        self._trail: dict = {}
        self._cliques: dict = {}
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
            pieces = []
            for piece in _pieces(usable):
                self.floods += 1
                pieces.append(piece)
                members = piece.indices()
                head = members[0]
                # Both roles at once: the parked robot is B and A roams the
                # piece — states (p, parked) — or it is A and B roams — states
                # (parked, q). The squares are the same size, so the piece is
                # the same either way.
                for m in members[1:]:
                    first, second = head * max_pos + parked, m * max_pos + parked
                    if union(first, second):
                        self._remember(first, second)
                    first, second = parked * max_pos + head, parked * max_pos + m
                    if union(first, second):
                        self._remember(first, second)
            # The cliques themselves are kept: `shortest_trail` walks them, and
            # unlike the union-find skeleton they include every connection.
            self._cliques[parked] = tuple(pieces)

    def _find(self, x: int) -> int:
        parent = self._parent
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def _union(self, x: int, y: int) -> bool:
        """Join the two states' sets; True when something was actually written,
        which is exactly when the pair is new evidence worth remembering."""
        rx, ry = self._find(x), self._find(y)
        if rx == ry:
            return False
        self._parent[ry] = rx
        return True

    def _remember(self, x: int, y: int) -> None:
        """One proof pair per write: the two states whose joining caused it.
        Both lie in the current clique, so a pair is one legal segment, and the
        written pairs form a spanning trail of every island — what `trail`
        walks. O(states) extra memory; nothing on the query path."""
        self._trail.setdefault(x, []).append(y)
        self._trail.setdefault(y, []).append(x)

    def _segments(self, pairs) -> list:
        """(src, dst) state-id pairs — each inside one clique — rendered as
        segments (mover, src, dst, parked): one robot sliding while the other
        stands. Consecutive hops around the same parked robot merge into one
        segment and empty hops are dropped."""
        segments: list = []
        for src, dst in pairs:
            if src == dst:
                continue
            sa, sb = divmod(src, self._max_pos)
            da, db = divmod(dst, self._max_pos)
            parked_is_a = sa == da
            mover = "B" if parked_is_a else "A"
            seg = (
                mover,
                divmod(sb if parked_is_a else sa, self._col_span),
                divmod(db if parked_is_a else da, self._col_span),
                divmod(sa if parked_is_a else sb, self._col_span),
            )
            if segments and segments[-1][0] == mover and segments[-1][3] == seg[3]:
                segments[-1] = (mover, segments[-1][1], seg[2], seg[3])
            else:
                segments.append(seg)
        return segments

    def _piece_index(self, parked: int, cell: int) -> int:
        """Which of `parked`'s regions holds placement index `cell`."""
        pos = divmod(cell, self._col_span)
        for idx, piece in enumerate(self._cliques[parked]):
            if pos in piece:
                return idx
        raise AssertionError(f"placement {pos} is not usable around parked index {parked}")

    def _same_piece(self, parked: int, x: int, y: int) -> bool:
        """Can one robot slide from placement x to y while the other stands at
        `parked` — are both in one region around it?"""
        pos_x, pos_y = divmod(x, self._col_span), divmod(y, self._col_span)
        for piece in self._cliques[parked]:
            if pos_x in piece:
                return pos_y in piece
        return False

    def _shortcut(self, s0: int, segments: list) -> list:
        """Greedy pass over a trail: from each boundary state, jump to the
        farthest later boundary state reachable in ONE segment — same robot
        parked in both, the other robot's two placements in one region —
        repeated to a fixed point. Stays legal throughout and usually collapses
        most of a remembered trail's slack, but proves nothing about the
        minimum; `shortest_trail` does."""
        max_pos, col_span = self._max_pos, self._col_span

        def boundary_states(segs):
            out = [s0]
            for mover, _src, dst, parked in segs:
                p = parked[0] * col_span + parked[1]
                d = dst[0] * col_span + dst[1]
                out.append(d * max_pos + p if mover == "A" else p * max_pos + d)
            return out

        changed = True
        while changed:
            changed = False
            states = boundary_states(segments)
            pairs = []
            i = 0
            while i < len(states) - 1:
                j_best = i + 1
                for j in range(len(states) - 1, i, -1):
                    a1, b1 = divmod(states[i], max_pos)
                    a2, b2 = divmod(states[j], max_pos)
                    if (a1 == a2 and self._same_piece(a1, b1, b2)) or (
                        b1 == b2 and self._same_piece(b1, a1, a2)
                    ):
                        j_best = j
                        break
                if j_best > i + 1:
                    changed = True
                pairs.append((states[i], states[j_best]))
                i = j_best
            segments = self._segments(pairs)
        return segments

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

    def trail(self, start, goal, shortcut: bool = False) -> list | None:
        """A solution remembered by the build: the unique route through the
        proof pairs from `start` to `goal`, as segments (mover, src, dst,
        parked) — robot `mover` slides src -> dst while the other stands at
        parked. None when the two states share no island; empty when they are
        the same state. Every segment is legal; the segment count follows the
        order the build filed things and is NOT minimal. `shortcut=True` runs
        the greedy collapse over it (see `_shortcut`) — shorter, still not
        proven minimal; `shortest_trail` is the exact one."""
        s0, g0 = self._state(*start), self._state(*goal)
        if self._find(s0) != self._find(g0):
            return None
        parent: dict = {s0: None}
        stack = [s0]
        while stack:
            v = stack.pop()
            if v == g0:
                break
            for nxt in self._trail.get(v, ()):
                if nxt not in parent:
                    parent[nxt] = v
                    stack.append(nxt)
        hops = []
        cur = g0
        while parent[cur] is not None:
            hops.append((parent[cur], cur))
            cur = parent[cur]
        hops.reverse()
        segments = self._segments(hops)
        return self._shortcut(s0, segments) if shortcut else segments

    def shortest_trail(self, start, goal) -> list | None:
        """An optimal solution, in `trail`'s segment format, whose count is
        provably minimal in switches (``len - 1 == min_switches``); None when
        no island joins the two states, empty when they are equal.

        Runs breadth-first over the cliques the build kept — one node per
        (parked placement, region, which robot roams), an edge where two
        cliques share a state. Why that is exact: every solution's segments
        each lie inside one clique, and consecutive segments meet at a shared
        state, so solutions are precisely walks in this graph with switches =
        cliques visited − 1; conversely any walk unfolds into a solution by
        sliding between the shared states inside each region. The first walk
        breadth-first order finds is therefore a minimum — the same quantity
        the solver proves, which the tests cross-check case by case."""
        s0, g0 = self._state(*start), self._state(*goal)
        if self._find(s0) != self._find(g0):
            return None
        if s0 == g0:
            return []
        max_pos = self._max_pos
        s_a, s_b = divmod(s0, max_pos)
        g_a, g_b = divmod(g0, max_pos)
        g_a_pos, g_b_pos = divmod(g_a, self._col_span), divmod(g_b, self._col_span)

        def holds_goal(lab, parked, pi):
            piece = self._cliques[parked][pi]
            if lab == 0:
                return parked == g_b and g_a_pos in piece
            return parked == g_a and g_b_pos in piece

        # Clique id: (lab, parked, piece). lab 0 = B parked, A roams;
        # lab 1 = A parked, B roams. Both of the start's cliques are seeded,
        # which is what lets either robot make the first move for free.
        parent: dict = {}
        queue = deque()
        hit = None
        for cid in ((0, s_b, self._piece_index(s_b, s_a)), (1, s_a, self._piece_index(s_a, s_b))):
            if cid in parent:
                continue
            parent[cid] = None
            if holds_goal(*cid):
                hit = cid
                break
            queue.append(cid)
        while hit is None and queue:
            cid = queue.popleft()
            lab, parked, pi = cid
            for member in self._cliques[parked][pi].indices():
                ncid = (1 - lab, member, self._piece_index(member, parked))
                if ncid in parent:
                    continue
                via = member * max_pos + parked if lab == 0 else parked * max_pos + member
                parent[ncid] = (cid, via)
                if holds_goal(*ncid):
                    hit = ncid
                    break
                queue.append(ncid)
        if hit is None:
            raise AssertionError("one island but no clique walk — the build is inconsistent")
        vias = []
        cid = hit
        while parent[cid] is not None:
            cid, via = parent[cid]
            vias.append(via)
        vias.reverse()
        waypoints = [s0, *vias, g0]
        return self._segments(zip(waypoints, waypoints[1:]))

    def min_switches(self, start, goal) -> int | None:
        """The exact minimum control switches from `start` to `goal`: the
        length of `shortest_trail` minus one, 0 when the states are equal,
        None when they share no island. Exactness per `shortest_trail`."""
        best = self.shortest_trail(start, goal)
        return None if best is None else max(0, len(best) - 1)

    def commands(self, segments) -> list:
        """`trail` / `shortest_trail` segments as the flat command list the
        validator replays: one shortest cell route per segment — the same
        rendering rule the solver's `_render_segments` applies — with "S"
        between segments. Commands name no robot, so the caller reads who
        holds control at step 0 off the first segment's mover."""
        out: list = []
        for index, (_mover, src, dst, parked) in enumerate(segments):
            if index:
                out.append("S")
            out.extend(self._route_cmds(src, dst, parked))
        return out

    def _route_cmds(self, src, dst, parked) -> list:
        """U/D/L/R steps of one shortest walk src -> dst inside the region
        around `parked`: a queue BFS over the stored piece, its parent
        pointers kept only long enough to read the moves back."""
        if src == dst:
            return []
        col_span = self._col_span
        parked_i = parked[0] * col_span + parked[1]
        src_i = src[0] * col_span + src[1]
        piece = self._cliques[parked_i][self._piece_index(parked_i, src_i)]
        dst_i = dst[0] * col_span + dst[1]
        prev: dict = {src_i: None}
        queue = deque([src_i])
        while queue:
            v = queue.popleft()
            if v == dst_i:
                break
            r, c = divmod(v, col_span)
            for dr, dc, cmd in ((-1, 0, "U"), (1, 0, "D"), (0, -1, "L"), (0, 1, "R")):
                nxt = (r + dr, c + dc)
                if nxt not in piece:
                    continue
                nxt_i = nxt[0] * col_span + nxt[1]
                if nxt_i in prev:
                    continue
                prev[nxt_i] = (v, cmd)
                queue.append(nxt_i)
        cmds: list = []
        cur = dst_i
        while prev[cur] is not None:
            cur, cmd = prev[cur]
            cmds.append(cmd)
        cmds.reverse()
        return cmds

    def solvable_starts(self) -> Iterator[tuple]:
        """Every ordered (pos_a, pos_b) from which the robots can swap. (a, b)
        and (b, a) are two starts and both are listed: the swap is the same
        either way, but which robot is A — and so moves first — is not."""
        for s in self._all_states():
            if self._find(s) == self._find(self._exchange(s)):
                yield self._pair(s)
