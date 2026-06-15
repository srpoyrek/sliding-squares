"""
canonical.py
------------
Reusable API for robot placements and workspace canonicalization.

Two things live here, extracted from find_hardest_workspace.py so any module can
use them:

  1. Placement enumeration — every way two n*n robots can TOUCH:
       all_adjacent_placements : full-edge contact only
       all_touching_placements : full edge + partial edge + corner

  2. Canonicalization — collapse the symmetric duplicates. The `Canonicalizer`
     holds the D4 transform tables for one (rows, cols, n) and turns a workspace
     (free-cell set + the two robot top-lefts) into a single canonical key that
     is identical for any rotation / flip / mirror of the workspace and for the
     A<->B label swap. Use it to dedup placements or whole workspaces.

This module is self-contained: it owns the spatial-symmetry primitives
(transform tables + lex-min canonical key) and the friendly Canonicalizer /
placement helpers built on top of them.
"""

from __future__ import annotations

from typing import Dict, Tuple

# ---------------------------------------------------------------------------
# Spatial symmetry primitives
#
# Transform indices:
#     0 identity   1 flip-h   2 flip-v   3 rot180
#   (square only)  4 rot90CW  5 rot270CW  6 diagonal  7 anti-diagonal
# cell_table : per free-cell.          Horizontal flip (r, c) -> (r, C-1-c)
# pos_table  : per robot n*n top-left.  Horizontal flip (r, c) -> (r, C-n-c)
# ---------------------------------------------------------------------------


def build_transform_tables(rows: int, cols: int, n: int):
    """Return (n_kinds, cell_table, pos_table) for an rows*cols grid and n*n robot."""
    R, C = rows, cols
    is_square = R == C
    n_kinds = 8 if is_square else 4

    cell_table: Dict[Tuple[int, int], Tuple[Tuple[int, int], ...]] = {}
    for r in range(R):
        for c in range(C):
            tforms = [
                (r, c),
                (r, C - 1 - c),
                (R - 1 - r, c),
                (R - 1 - r, C - 1 - c),
            ]
            if is_square:
                tforms.extend(
                    [
                        (c, R - 1 - r),
                        (C - 1 - c, r),
                        (c, r),
                        (C - 1 - c, R - 1 - r),
                    ]
                )
            cell_table[(r, c)] = tuple(tforms)

    pos_table: Dict[Tuple[int, int], Tuple[Tuple[int, int], ...]] = {}
    for r in range(R - n + 1):
        for c in range(C - n + 1):
            tforms = [
                (r, c),
                (r, C - n - c),
                (R - n - r, c),
                (R - n - r, C - n - c),
            ]
            if is_square:
                tforms.extend(
                    [
                        (c, R - n - r),
                        (C - n - c, r),
                        (c, r),
                        (C - n - c, R - n - r),
                    ]
                )
            pos_table[(r, c)] = tuple(tforms)

    return n_kinds, cell_table, pos_table


def canonical_key(free_set, pos_a, pos_b, n_kinds, cell_table, pos_table, bit_stride):
    """Lex-min canonical form over all spatial transforms and both label orderings."""
    best = None
    for k in range(n_kinds):
        transformed_free = 0
        for c in free_set:
            r, col = cell_table[c][k]
            transformed_free |= 1 << (r * bit_stride + col)

        a_t = pos_table[pos_a][k]
        b_t = pos_table[pos_b][k]
        cand1 = (transformed_free, a_t, b_t)
        cand2 = (transformed_free, b_t, a_t)
        if best is None or cand1 < best:
            best = cand1
        if cand2 < best:
            best = cand2
    return best


def is_label_swap_symmetric(
    tiles,
    rows: int,
    cols: int,
    pos_a,
    pos_b,
    goal_a,
    goal_b,
    n_kinds,
    cell_table,
    pos_table,
) -> bool:
    """
    Is there a non-identity spatial transform that:
      - leaves the tile layout invariant,
      - swaps pos_a <-> pos_b,
      - swaps goal_a <-> goal_b?

    When yes, BFS(A-first) and BFS(B-first) return the same switch count — so
    the solver can skip one of them. Cost is O(rows*cols*K) per check, K <= 8.
    """
    # Skip identity (k=0): it can't swap unless pos_a == pos_b.
    for k in range(1, n_kinds):
        if pos_table[pos_a][k] != pos_b or pos_table[pos_b][k] != pos_a:
            continue
        if pos_table[goal_a][k] != goal_b or pos_table[goal_b][k] != goal_a:
            continue
        walls_ok = True
        for r in range(rows):
            if not walls_ok:
                break
            for c in range(cols):
                tr, tc = cell_table[(r, c)][k]
                if tiles[tr][tc] != tiles[r][c]:
                    walls_ok = False
                    break
        if walls_ok:
            return True
    return False


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def robot_block(top_left, n):
    """The set of cells an n*n robot at `top_left` occupies."""
    r, c = top_left
    return {(r + dr, c + dc) for dr in range(n) for dc in range(n)}


def blocks_overlap(a, b, n):
    """Do two n*n blocks with top-lefts a and b overlap?"""
    return abs(a[0] - b[0]) < n and abs(a[1] - b[1]) < n


# ---------------------------------------------------------------------------
# Placement enumeration — the partial / complete / corner touches
# ---------------------------------------------------------------------------


def all_adjacent_placements(rows, cols, n):
    """Full-edge-adjacent pairs only: B directly right of or below A."""
    for r in range(rows - n + 1):
        for c in range(cols - 2 * n + 1):
            yield ((r, c), (r, c + n))
    for r in range(rows - 2 * n + 1):
        for c in range(cols - n + 1):
            yield ((r, c), (r + n, c))
    return


def all_touching_placements(rows, cols, n):
    """All non-overlapping A/B placements where the two n*n blocks touch —
    full edge, partial edge, or just a corner. Includes everything
    `all_adjacent_placements` yields plus partial-offset and corner pairs.

    Non-overlapping + touching condition: (|dr|==n AND |dc|<=n) OR
    (|dr|<=n AND |dc|==n), where (dr, dc) = pos_b - pos_a.
    """
    offsets = []
    for dr in range(-n, n + 1):
        for dc in range(-n, n + 1):
            if dr == 0 and dc == 0:
                continue
            if abs(dr) == n or abs(dc) == n:
                offsets.append((dr, dc))

    for r_a in range(rows - n + 1):
        for c_a in range(cols - n + 1):
            for dr, dc in offsets:
                r_b = r_a + dr
                c_b = c_a + dc
                if 0 <= r_b <= rows - n and 0 <= c_b <= cols - n:
                    yield ((r_a, c_a), (r_b, c_b))
    return


def pick_central_placements(keepers, rows, cols, n):
    """From canonical-deduped keepers, return ONE representative per contact
    orientation class, picking whichever placement sits closest to the grid
    center.

    Valid because any workspace reachable from a non-central placement is also
    reachable from a central one (leave the corresponding cells undug to
    replicate the other placement's grid-boundary walls), so the central
    representative suffices.
    """
    center_r = (rows - 1) / 2.0
    center_c = (cols - 1) / 2.0

    def orient(pa, pb):
        # Key by (|dr|, |dc|) so reflections/rotations collapse to one class;
        # covers full-edge, partial-edge, and corner touching.
        dr = pb[0] - pa[0]
        dc = pb[1] - pa[1]
        return (min(abs(dr), abs(dc)), max(abs(dr), abs(dc)))

    def dist_sq(pa, pb):
        r_lo = min(pa[0], pb[0])
        r_hi = max(pa[0], pb[0]) + n - 1
        c_lo = min(pa[1], pb[1])
        c_hi = max(pa[1], pb[1]) + n - 1
        mid_r = (r_lo + r_hi) / 2.0
        mid_c = (c_lo + c_hi) / 2.0
        return (mid_r - center_r) ** 2 + (mid_c - center_c) ** 2

    best: dict = {}
    for pa, pb in keepers:
        o = orient(pa, pb)
        d = dist_sq(pa, pb)
        if o not in best or d < best[o][1]:
            best[o] = ((pa, pb), d)
    return [pair for pair, _ in best.values()]


# ---------------------------------------------------------------------------
# Canonicalizer — workspace / placement canonical keys
# ---------------------------------------------------------------------------


class Canonicalizer:
    """D4 + A<->B canonical keys for one (rows, cols, n).

    Build once, reuse for many keys (the transform tables are the expensive
    part). Two workspaces related by any rotation / flip / mirror, or by
    swapping the A and B labels, produce the SAME key.
    """

    def __init__(self, rows, cols, n):
        self.rows = rows
        self.cols = cols
        self.n = n
        self.n_kinds, self.cell_table, self.pos_table = build_transform_tables(rows, cols, n)
        self.bit_stride = cols

    def key(self, free_set, pos_a, pos_b):
        """Canonical key of a workspace = its free-cell set plus the two robot
        top-left positions, lex-min over all symmetries and both label orders."""
        return canonical_key(
            frozenset(free_set),
            pos_a,
            pos_b,
            self.n_kinds,
            self.cell_table,
            self.pos_table,
            self.bit_stride,
        )

    def placement_key(self, pos_a, pos_b):
        """Canonical key of a bare placement — just the two robot blocks, no
        other walls. Useful for deduping touching placements."""
        free = robot_block(pos_a, self.n) | robot_block(pos_b, self.n)
        return self.key(free, pos_a, pos_b)

    def key_for_workspace(self, ws):
        """Canonical key from a Workspace object (free cells = tiles == 0)."""
        free = {
            (r, c)
            for r in range(ws.grid.rows)
            for c in range(ws.grid.cols)
            if ws.grid.tiles[r][c] == 0
        }
        return self.key(free, ws.robot_a.position(), ws.robot_b.position())

    def dedup_placements(self, placements):
        """Collapse symmetric placements.

        Returns (keepers, groups):
          keepers : one representative (pos_a, pos_b) per symmetry class
          groups  : {representative -> [all members of its class]}
        """
        seen: dict = {}
        groups: dict = {}
        for pos_a, pos_b in placements:
            k = self.placement_key(pos_a, pos_b)
            if k in seen:
                groups[seen[k]].append((pos_a, pos_b))
            else:
                seen[k] = (pos_a, pos_b)
                groups[(pos_a, pos_b)] = [(pos_a, pos_b)]
        return list(seen.values()), groups

    def unique_touching(self, touching="all"):
        """Distinct touching placements after symmetry collapse.

        touching="all"  -> full edge + partial edge + corner (default)
        touching="edge" -> full-edge contact only
        """
        gen = all_touching_placements if touching == "all" else all_adjacent_placements
        keepers, _ = self.dedup_placements(gen(self.rows, self.cols, self.n))
        return keepers


# ---------------------------------------------------------------------------
# One-shot convenience wrappers (build a Canonicalizer per call)
# ---------------------------------------------------------------------------


def workspace_canonical_key(rows, cols, n, free_set, pos_a, pos_b):
    """Canonical key for a single workspace. For many keys, build a
    Canonicalizer once and call .key() instead."""
    return Canonicalizer(rows, cols, n).key(free_set, pos_a, pos_b)


def unique_touching_placements(rows, cols, n, touching="all"):
    """Symmetry-deduped touching placements for a grid. For repeated use, build
    a Canonicalizer once and call .unique_touching() instead."""
    return Canonicalizer(rows, cols, n).unique_touching(touching)
