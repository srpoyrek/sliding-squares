"""
symmetry.py
-----------
Spatial symmetry helpers: transform tables, canonical keys, and detection of
label-swap symmetry (used by the solver to skip redundant dual-start BFS when
the workspace is symmetric under an A<->B label swap).

Conventions:
  cell_table : for individual cells (free_set members).
               Horizontal flip: (r, c) -> (r, C-1-c)
  pos_table  : for robot n*n-block top-left positions.
               Horizontal flip: (r, c) -> (r, C-n-c)   (NOT C-1-c)
               because the block occupies cols c..c+n-1 and its flipped image
               must start at C - (c+n-1) - 1 = C - n - c.

Transform indices:
    0 identity
    1 flip horizontal
    2 flip vertical
    3 rotate 180
  (square only)
    4 rotate 90 CW
    5 rotate 270 CW
    6 diagonal (main)
    7 anti-diagonal
"""

from __future__ import annotations

from typing import Dict, Tuple


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
