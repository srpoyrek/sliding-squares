"""
find_hardest_workspace.py
-------------------------
Self-contained, optimized candidate generator for hardest workspaces.
Uses enqueue-time depth filtering and a sound symmetric connectivity pre-check.
"""

from __future__ import annotations

import argparse
import heapq
import multiprocessing as mp
import os
import shutil
import threading
import time
from collections import deque

from src.bfs import pack_cells_mask
from src.directories import get_plots_dir
from src.grid import Grid
from src.lru import LRUCache
from src.robot import Robot
from src.solver import Solver
from src.symmetry import build_transform_tables, canonical_key
from src.validator import Validator
from src.visualizer import draw_sequence
from src.workspace import Workspace


def _build_workspace(rows, cols, free_cells, pos_a, pos_b, n):
    tiles = [[1] * cols for _ in range(rows)]
    for r, c in free_cells:
        tiles[r][c] = 0
    grid = Grid(tiles)
    a = Robot("A", n, pos_a[0], pos_a[1])
    b = Robot("B", n, pos_b[0], pos_b[1])
    ws = Workspace(grid, a, b)
    ws._free_key = pack_cells_mask(free_cells, cols)
    return ws


def _free_set(ws):
    return {
        (r, c) for r in range(ws.grid.rows) for c in range(ws.grid.cols) if ws.grid.tiles[r][c] == 0
    }


def _robot_block(top_left, n):
    r, c = top_left
    return {(r + dr, c + dc) for dr in range(n) for dc in range(n)}


def _initial_frontier(rows, cols, free_cells):
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


def _extend_frontier(frontier, dug_cell, free_cells_after, rows, cols):
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


def _valid_block_positions(rows, cols, free_cells, n):
    valid = set()
    for r in range(rows - n + 1):
        for c in range(cols - n + 1):
            ok = True
            for ir in range(n):
                for ic in range(n):
                    if (r + ir, c + ic) not in free_cells:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                valid.add((r, c))
    return valid


def _extend_valid(valid, dug_cell, free_cells_after, rows, cols, n):
    """Incrementally update valid-block-positions after digging one cell.
    Only top-lefts whose n*n footprint contains the dug cell can change."""
    r_star, c_star = dug_cell
    r_lo = max(0, r_star - n + 1)
    r_hi = min(rows - n, r_star)
    c_lo = max(0, c_star - n + 1)
    c_hi = min(cols - n, c_star)

    new_valid = set(valid)
    for r in range(r_lo, r_hi + 1):
        for c in range(c_lo, c_hi + 1):
            if (r, c) in new_valid:
                continue
            ok = True
            for ir in range(n):
                for ic in range(n):
                    if (r + ir, c + ic) not in free_cells_after:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                new_valid.add((r, c))
    return new_valid


def robot_can_reach_goal_ignoring_other(valid, start, goal):
    if goal not in valid:
        return False
    queue = deque([start])
    visited = {start}
    while queue:
        curr = queue.popleft()
        if curr == goal:
            return True
        r, c = curr
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nbr = (r + dr, c + dc)
            if nbr in valid and nbr not in visited:
                visited.add(nbr)
                queue.append(nbr)
    return False


def valid_has_bypass(valid, start, n):
    """N-aware topology check (tight): swap is feasible only if the component
    of `valid` containing `start` satisfies:

      - contains a vertex of degree >= 3 whose branches reach positions with
        axis-diff >= n from the vertex in at least TWO directions (so one
        branch can serve as the "parking" spot for one robot while the others
        form the corridor the other robot traverses without overlap), OR
      - contains a cycle that spans two positions with axis-diff >= n (a
        cycle big enough to accommodate two non-overlapping n x n robots).

    For n = 1 this reduces to the simple "degree >= 3 or cycle" check because
    any edge in the valid graph has axis-diff exactly 1 = n.

    O(|component|^2) worst case. Necessary condition only — some apparently
    feasible configurations may still be infeasible due to geometric
    constraints the solver resolves — but always sound (never falsely rejects).
    """
    if start not in valid:
        return False
    seen = {start}
    queue = deque([start])
    component = []
    edge_halves = 0
    degree_3_vertices = []
    while queue:
        pos = queue.popleft()
        component.append(pos)
        r, c = pos
        deg = 0
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nbr = (r + dr, c + dc)
            if nbr in valid:
                deg += 1
                edge_halves += 1
                if nbr not in seen:
                    seen.add(nbr)
                    queue.append(nbr)
        if deg >= 3:
            degree_3_vertices.append(pos)

    vertices = len(component)
    edges = edge_halves // 2
    has_cycle = edges > vertices - 1

    if not (degree_3_vertices or has_cycle):
        return False  # pure path — no swap for any n

    # For each degree->=3 vertex, count branches that extend to axis-diff >= n.
    # Need at least 2 such branches: one serves as parking, another as corridor.
    for v in degree_3_vertices:
        neighbors = []
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nb = (v[0] + dr, v[1] + dc)
            if nb in valid:
                neighbors.append(nb)
        deep_branches = 0
        for branch_start in neighbors:
            # DFS into branch, forbidden from crossing v. Stop at first
            # position with axis-diff >= n from v (short-circuit).
            stack = [branch_start]
            branch_seen = {v, branch_start}
            branch_deep = False
            while stack:
                curr = stack.pop()
                if abs(curr[0] - v[0]) >= n or abs(curr[1] - v[1]) >= n:
                    branch_deep = True
                    break
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nb = (curr[0] + dr, curr[1] + dc)
                    if nb in valid and nb not in branch_seen:
                        branch_seen.add(nb)
                        stack.append(nb)
            if branch_deep:
                deep_branches += 1
                if deep_branches >= 2:
                    return True

    # Cycle fallback: A cycle allows a swap if it can accommodate two
    # non-overlapping robots. This requires the cycle to span at
    # least n units in BOTH dimensions.
    if has_cycle:
        for i, p1 in enumerate(component):
            for p2 in component[i + 1 :]:
                if abs(p1[0] - p2[0]) >= n and abs(p1[1] - p2[1]) >= n:
                    return True
    return False


def _solve_payload(payload):
    """Worker function: rebuild workspace and run solver.
    Used by the batch-parallel solver pool in dig_search.
    Payload: (rows, cols, n, free_cells_frozen, pos_a, pos_b, goal_a, goal_b)
    Returns: (solvable, switches)
    """
    rows, cols, n, free_cells, pos_a, pos_b, goal_a, goal_b = payload
    ws = _build_workspace(rows, cols, set(free_cells), pos_a, pos_b, n)
    res = Solver(ws, goal_a, goal_b).solve()
    return res.solvable, res.switches


def _plot_proof(ws_template, goals, save_dir):
    rows, cols, n = ws_template.grid.rows, ws_template.grid.cols, ws_template.robot_a.n
    pos_a, pos_b = ws_template.robot_a.position(), ws_template.robot_b.position()
    free = _free_set(ws_template)
    ws = _build_workspace(rows, cols, free, pos_a, pos_b, n)
    res = Solver(ws, goals[0], goals[1]).solve()
    if not res.solvable:
        return False, "unsolvable on replay"
    vr = Validator(ws, goals[0], goals[1]).run(res.path, plot=False)
    if not vr.valid:
        return False, f"validator failed: {vr.failed_reason}"
    snapshots = [[a, b] for a, b in vr.snapshots]
    os.makedirs(save_dir, exist_ok=True)
    draw_sequence(ws.grid, snapshots, titles=vr.titles, save_dir=save_dir, robot_size=n)
    return True, res.switches


# ---------------------------------------------------------------------------
# Symmetry: transform tables and canonical keys
# ---------------------------------------------------------------------------

_N_KINDS = None
_CELL_TABLE = None
_POS_TABLE = None
_BIT_STRIDE = None  # grid width in cols; used to pack (r, c) into a single bit index
_CELL_BITS = None  # {(r, c): (bit_under_k0, bit_under_k1, ...)} for incremental canon


def _build_cell_bits(cell_table, bit_stride):
    """Precompute, per cell, the bit-position values under each transform."""
    cb = {}
    for c, tforms in cell_table.items():
        cb[c] = tuple(1 << (rt * bit_stride + ct) for (rt, ct) in tforms)
    return cb


def _init_transform_tables(rows, cols, n, cache_mb=150):
    """Build and set module-level transform tables. Called once in main process."""
    global _N_KINDS, _CELL_TABLE, _POS_TABLE, _BIT_STRIDE, _CELL_BITS
    _N_KINDS, _CELL_TABLE, _POS_TABLE = build_transform_tables(rows, cols, n)
    _BIT_STRIDE = cols
    _CELL_BITS = _build_cell_bits(_CELL_TABLE, _BIT_STRIDE)

    from src import bfs as _bfs

    _bfs.configure_caches_for_grid(rows, cols, n, target_mb=cache_mb)
    print(
        f"Cache sizing (budget={cache_mb} MB/worker): "
        f"parent_map={_bfs._PARENT_MAP_CACHE.maxsize}  "
        f"usable={_bfs._USABLE_CACHE.maxsize}  "
        f"valid_pos={_bfs._VALID_POS_CACHE.maxsize}"
    )


def _set_transform_tables(
    n_kinds,
    cell_table,
    pos_table,
    bit_stride,
    grid_rows=None,
    grid_cols=None,
    grid_n=None,
    cache_mb=150,
):
    """Assign pre-built transform tables in worker processes (no recomputation).
    Also sizes the per-worker bfs caches for the current grid dimensions so
    per-entry memory scales sanely from 4x4 to 30x30+."""
    global _N_KINDS, _CELL_TABLE, _POS_TABLE, _BIT_STRIDE, _CELL_BITS
    _N_KINDS = n_kinds
    _CELL_TABLE = cell_table
    _POS_TABLE = pos_table
    _BIT_STRIDE = bit_stride
    _CELL_BITS = _build_cell_bits(cell_table, bit_stride)
    if grid_rows is not None and grid_cols is not None and grid_n is not None:
        from src.bfs import configure_caches_for_grid

        configure_caches_for_grid(grid_rows, grid_cols, grid_n, target_mb=cache_mb)


def _canonical_key(tf, seconds, thirds):
    """Canonical key from a precomputed transforms_free tuple and per-transform
    tiebreakers (seconds[k] = min(pos_a_t[k], pos_b_t[k]), thirds[k] = max).
    O(n_kinds) per call — incremental-friendly."""
    best = (tf[0], seconds[0], thirds[0])
    for k in range(1, _N_KINDS):  # type: ignore
        cand = (tf[k], seconds[k], thirds[k])
        if cand < best:
            best = cand
    return best


# ---------------------------------------------------------------------------
# Dig strategies
# ---------------------------------------------------------------------------
#
# A dig strategy decides what cell-set to dig in one BFS step.
# It receives the current state and yields candidate cell-sets (frozensets).
# Each yielded set is treated as one atomic dig (one BFS depth increment).
#
# The default strategy yields one cell at a time (the current behavior).
# Future strategies (e.g., n-cell strips for n*n robots) can drop in by
# swapping the function — the BFS itself doesn't care how many cells per dig.
# ---------------------------------------------------------------------------


def _dig_options_single_cell(free_cells, frontier, valid, rows, cols, n):
    for cell in frontier:
        yield frozenset({cell})


def _dig_options_n_strip(free_cells, frontier, valid, rows, cols, n):
    """Yield 1×n or n×1 strips that extend the valid region by one robot step.

    For each valid position, look in 4 directions. If the adjacent position
    isn't yet valid, the n cells the robot would newly occupy form a strip.
    Dig the wall cells in that strip.

    For n=1 this produces the same candidates as _dig_options_single_cell.
    """
    seen = set()
    for r, c in valid:
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if not (0 <= nr <= rows - n and 0 <= nc <= cols - n):
                continue
            if (nr, nc) in valid:
                continue
            # The n cells the robot newly occupies when stepping this direction
            if dr != 0:  # vertical move → horizontal strip
                strip_r = r + n if dr == 1 else r - 1
                cells = frozenset((strip_r, c + i) for i in range(n))
            else:  # horizontal move → vertical strip
                strip_c = c + n if dc == 1 else c - 1
                cells = frozenset((r + i, strip_c) for i in range(n))
            to_dig = cells - free_cells
            if not to_dig or to_dig in seen:
                continue
            seen.add(to_dig)
            yield to_dig


# ---------------------------------------------------------------------------
# Dig search
# ---------------------------------------------------------------------------


def dig_search(
    rows,
    cols,
    n,
    pos_a,
    pos_b,
    max_depth_past_first,
    logs,
    dig_options=_dig_options_single_cell,
    solver_pool=None,
    cache_stats_out=None,
):
    goal_a, goal_b = pos_b, pos_a

    block_a = _robot_block(pos_a, n)
    block_b = _robot_block(pos_b, n)

    init_free = block_a | block_b
    init_frontier = _initial_frontier(rows, cols, init_free)
    init_valid = _valid_block_positions(rows, cols, init_free, n)
    init_key = frozenset(init_free)

    # Valid positions (top-lefts where an n x n block fits) live in a
    # (rows-n+1) x (cols-n+1) grid. Use `pack_cells_mask` with this stride
    # as the cache key — same uniqueness as frozenset(valid), ~300x less
    # memory per entry, O(1) int hashing.
    valid_col_span = cols - n + 1

    # Monotonicity shortcut: if both robots can already reach their goals at
    # init_free (e.g. edge-adjacent placements), they can reach them at every
    # future state (valid set only grows as cells are dug). We can skip the
    # reach-check inside the hot loop entirely.
    reach_always_ok = robot_can_reach_goal_ignoring_other(
        init_valid, pos_a, goal_a
    ) and robot_can_reach_goal_ignoring_other(init_valid, pos_b, goal_b)

    # Per-placement tiebreakers: pos_a and pos_b don't change within one
    # dig_search call, so the (a_t, b_t) / (b_t, a_t) tiebreaker pairs are
    # constant per transform. Precompute once.
    seconds = tuple(
        min(_POS_TABLE[pos_a][k], _POS_TABLE[pos_b][k])  # type: ignore
        for k in range(_N_KINDS)  # type: ignore
    )
    thirds = tuple(
        max(_POS_TABLE[pos_a][k], _POS_TABLE[pos_b][k])  # type: ignore
        for k in range(_N_KINDS)  # type: ignore
    )

    # Initial transforms_free tuple (one bitmap per transform).
    init_tf_list = [0] * _N_KINDS  # type: ignore
    for c in init_free:
        bits = _CELL_BITS[c]  # type: ignore
        for k in range(_N_KINDS):  # type: ignore
            init_tf_list[k] |= bits[k]
    init_tf = tuple(init_tf_list)

    visited = set()
    # Min-heap priority queue: (depth, |valid|, seq, state_payload).
    # Primary key depth  -> preserves layered-BFS ordering.
    # Secondary |valid| -> within a layer, explore tighter puzzles (fewer
    #                       robot positions) first.
    # seq counter       -> breaks ties so Python never compares payloads.
    queue: list = []
    seq = 0
    heapq.heappush(
        queue,
        (0, len(init_valid), seq, (init_key, init_frontier, init_valid, init_tf, 0)),
    )
    seq += 1

    shared_ws = _build_workspace(rows, cols, set(init_free), pos_a, pos_b, n)
    shared_tiles = shared_ws.grid.tiles
    current_free_set = set(init_free)

    def sync_tiles_to(target_free):
        for r, c in target_free - current_free_set:
            shared_tiles[r][c] = 0
        for r, c in current_free_set - target_free:
            shared_tiles[r][c] = 1
        current_free_set.clear()
        current_free_set.update(target_free)
        shared_ws._free_key = pack_cells_mask(target_free, cols)  # type: ignore

    best_switches = -1
    best_free_max, best_free_min = None, None
    min_free_at_max = 999
    first_solvable_depth = None

    t_canon = 0.0
    t_precheck = 0.0
    t_sync = 0.0
    t_solver = 0.0
    t_frontier = 0.0
    nodes_visited = 0
    solver_calls = 0
    expansions_total = 0
    canon_dupes_skipped = 0
    bypass_rejects = 0  # valid-graph topology (no branch/cycle/room) rejected the workspace
    solvable_prunes = 0  # how many solvable nodes we skipped expanding
    solvable_prune_children_skipped = 0  # immediate children that would have been enqueued
    # Solver / precheck caches are keyed by frozenset(valid). In practice the
    # outer canonical dedup on free_cells already eliminates most would-be
    # cache hits before we reach this lookup, so real-world hit rates are ~0%
    # on n>=2 grids too. Kept at a small LRU cap purely to catch the rare
    # stepping-stone states where two different canonical free_cells do yield
    # the same valid set — without wasting ~100 MB/worker on dead weight.
    solver_cache: LRUCache = LRUCache(maxsize=256)
    solver_cache_hits = 0
    precheck_cache: LRUCache = LRUCache(maxsize=256)
    precheck_cache_hits = 0
    t_start = time.perf_counter()

    # Per-depth chunked processing. We process nodes at the current depth in
    # batches to keep memory usage stable even when the BFS layer is very wide.
    MAX_BATCH_SIZE = 5000

    while queue:
        current_depth = queue[0][0]
        if (
            first_solvable_depth is not None
            and current_depth > first_solvable_depth + max_depth_past_first
        ):
            # Drain remaining queue past the cap without doing any work.
            while queue and queue[0][0] == current_depth:
                heapq.heappop(queue)
            continue

        while queue and queue[0][0] == current_depth:
            # Process the current depth in chunks to avoid memory spikes
            batch = []
            for _ in range(MAX_BATCH_SIZE):
                if not queue or queue[0][0] != current_depth:
                    break
                batch.append(heapq.heappop(queue))

            # Phase 1: precheck batch; collect the ones needing solver.
            layer_records = []
            need_solve_payloads = []
            need_solve_indices = []
            for item in batch:
                _pd, _pv, _pseq, (free_key, frontier, valid, tf, depth) = item
                nodes_visited += 1
                if nodes_visited % 20000 == 0:
                    elapsed = time.perf_counter() - t_start
                    qsize = len(queue) + len(layer_records)
                    rate = nodes_visited / elapsed if elapsed > 0 else 0
                    eta = qsize / rate if rate > 0 else 0
                    print(
                        f"    [{pos_a}-{pos_b}] nodes={nodes_visited} depth={depth} "
                        f"best={best_switches} queue={qsize} elapsed={elapsed:.1f}s "
                        f"eta={eta:.0f}s ({rate:.0f} nodes/s)",
                        flush=True,
                    )
                free_cells = set(free_key)
                valid_key = pack_cells_mask(valid, valid_col_span)

                pc_cached = precheck_cache.get(valid_key)
                if pc_cached is not None:
                    precheck_cache_hits += 1
                    precheck_ok = pc_cached
                else:
                    t0 = time.perf_counter()
                    if reach_always_ok:
                        reach_ok = True
                    else:
                        reach_ok = robot_can_reach_goal_ignoring_other(
                            valid, pos_a, goal_a
                        ) and robot_can_reach_goal_ignoring_other(valid, pos_b, goal_b)
                    if reach_ok:
                        bypass_ok = valid_has_bypass(valid, pos_a, n)
                        if not bypass_ok:
                            bypass_rejects += 1
                        precheck_ok = bypass_ok
                    else:
                        precheck_ok = False
                    t_precheck += time.perf_counter() - t0
                    precheck_cache[valid_key] = precheck_ok

                solve_result = None
                if precheck_ok:
                    cached = solver_cache.get(valid_key)
                    if cached is not None:
                        solver_cache_hits += 1
                        solve_result = cached
                    else:
                        need_solve_payloads.append(
                            (rows, cols, n, free_key, pos_a, pos_b, goal_a, goal_b)
                        )
                        need_solve_indices.append(len(layer_records))

                layer_records.append(
                    {
                        "free_cells": free_cells,
                        "free_key": free_key,
                        "frontier": frontier,
                        "valid": valid,
                        "valid_key": valid_key,
                        "tf": tf,
                        "depth": depth,
                        "precheck_ok": precheck_ok,
                        "solve": solve_result,
                    }
                )

            # Phase 2: batch-solve
            if need_solve_payloads:
                t0 = time.perf_counter()
                if solver_pool is not None and len(need_solve_payloads) > 1:
                    batch_results = list(solver_pool.map(_solve_payload, need_solve_payloads))
                else:
                    batch_results = []
                    for p in need_solve_payloads:
                        _rows, _cols, _n, fk, _pa, _pb, _ga, _gb = p
                        sync_tiles_to(set(fk))
                        result = Solver(shared_ws, goal_a, goal_b).solve()
                        batch_results.append((result.solvable, result.switches))
                t_solver += time.perf_counter() - t0
                solver_calls += len(need_solve_payloads)
                for idx, res in zip(need_solve_indices, batch_results):
                    rec = layer_records[idx]
                    solver_cache[rec["valid_key"]] = res
                    rec["solve"] = res

            # Phase 3: expand
            for rec in layer_records:
                depth = rec["depth"]
                free_cells = rec["free_cells"]
                free_key = rec["free_key"]
                frontier = rec["frontier"]
                valid = rec["valid"]
                tf = rec["tf"]

                if rec["precheck_ok"] and rec["solve"] is not None:
                    solvable, res_switches = rec["solve"]
                    if solvable:
                        if first_solvable_depth is None:
                            first_solvable_depth = depth
                            logs.append(f"    first solvable @ depth={depth}")
                        if res_switches is not None and res_switches > best_switches:
                            best_switches = res_switches
                            best_free_max = free_key
                            best_free_min = free_key
                            min_free_at_max = len(free_cells)
                            logs.append(
                                f"    NEW MAX: {res_switches} (D:{depth}, F:{len(free_cells)})"
                            )
                        elif (
                            res_switches is not None
                            and res_switches == best_switches
                            and len(free_cells) < min_free_at_max
                        ):
                            min_free_at_max = len(free_cells)
                            best_free_min = free_key
                            logs.append(
                                f"    MIN-FREE witness: {len(free_cells)} (S:{res_switches})"
                            )
                        n_children = len(frontier)
                        if n_children > 0:
                            solvable_prunes += 1
                            solvable_prune_children_skipped += n_children
                        continue

                if (
                    first_solvable_depth is not None
                    and (depth + 1) > first_solvable_depth + max_depth_past_first
                ):
                    continue

                for cells_to_dig in dig_options(free_cells, frontier, valid, rows, cols, n):
                    expansions_total += 1
                    new_free_set = free_cells | cells_to_dig
                    new_key = frozenset(new_free_set)

                    t0 = time.perf_counter()
                    new_tf_list = list(tf)
                    for c in cells_to_dig:
                        bits = _CELL_BITS[c]  # type: ignore
                        for k in range(_N_KINDS):  # type: ignore
                            new_tf_list[k] |= bits[k]
                    new_tf = tuple(new_tf_list)
                    new_canon = _canonical_key(new_tf, seconds, thirds)
                    t_canon += time.perf_counter() - t0

                    if new_canon in visited:
                        canon_dupes_skipped += 1
                        continue
                    visited.add(new_canon)

                    t0 = time.perf_counter()
                    new_frontier = frontier
                    for cell in cells_to_dig:
                        new_frontier = _extend_frontier(
                            new_frontier, cell, new_free_set, rows, cols
                        )
                    t_frontier += time.perf_counter() - t0

                    new_valid = valid
                    for cell in cells_to_dig:
                        new_valid = _extend_valid(new_valid, cell, new_free_set, rows, cols, n)

                    heapq.heappush(
                        queue,
                        (
                            depth + 1,
                            len(new_valid),
                            seq,
                            (new_key, new_frontier, new_valid, new_tf, depth + 1),
                        ),
                    )
                    seq += 1

    t_total = time.perf_counter() - t_start
    unique_enqueued = expansions_total - canon_dupes_skipped
    dedup_pct = (100.0 * canon_dupes_skipped / expansions_total) if expansions_total else 0.0
    logs.append(
        f"    timings: total={t_total:.2f}s  solver={t_solver:.2f}s  "
        f"canon={t_canon:.2f}s  precheck={t_precheck:.2f}s  "
        f"sync={t_sync:.2f}s  frontier={t_frontier:.2f}s  "
        f"nodes={nodes_visited}  solves={solver_calls}"
    )
    bypass_pct = (100.0 * bypass_rejects / nodes_visited) if nodes_visited else 0.0
    logs.append(f"    bypass:  rejected={bypass_rejects}/{nodes_visited} ({bypass_pct:.1f}%)")
    logs.append(
        f"    dedup:   expansions={expansions_total}  unique={unique_enqueued}  "
        f"symmetric_dropped={canon_dupes_skipped}  ({dedup_pct:.1f}% pruned)"
    )
    logs.append(
        f"    prune:   solvable_nodes_pruned={solvable_prunes}  "
        f"immediate_children_skipped>={solvable_prune_children_skipped}"
    )
    total_solver_asks = solver_calls + solver_cache_hits
    solver_hit_pct = (100.0 * solver_cache_hits / total_solver_asks) if total_solver_asks else 0.0
    total_pc_asks = nodes_visited  # one precheck ask per popped node
    pc_hit_pct = (100.0 * precheck_cache_hits / total_pc_asks) if total_pc_asks else 0.0
    logs.append(
        f"    cache:   solver_hits={solver_cache_hits}"
        f" runs={solver_calls} ({solver_hit_pct:.1f}%)"
        f" precheck_hits={precheck_cache_hits}"
        f" runs={total_pc_asks - precheck_cache_hits} ({pc_hit_pct:.1f}%)"
    )
    logs.append(
        f"    lru:     solver[{solver_cache.stats()}]  " f"precheck[{precheck_cache.stats()}]"
    )

    if cache_stats_out is not None:
        cache_stats_out["solver"] = _lru_snapshot(solver_cache)
        cache_stats_out["precheck"] = _lru_snapshot(precheck_cache)

    if best_free_max is None or best_free_min is None:
        return None
    return {
        "switches": best_switches,
        "ws_max": _build_workspace(rows, cols, set(best_free_max), pos_a, pos_b, n),
        "free_max_count": len(best_free_max),
        "ws_min": _build_workspace(rows, cols, set(best_free_min), pos_a, pos_b, n),
        "free_min_count": len(best_free_min),
        "goals": (goal_a, goal_b),
    }


# ---------------------------------------------------------------------------
# Worker + placement dedup + orchestrator
# ---------------------------------------------------------------------------


DIG_STRATEGIES = {
    "single": _dig_options_single_cell,
    "strip": _dig_options_n_strip,
}


def _lru_snapshot(cache: LRUCache) -> dict:
    return {
        "size": len(cache),
        "maxsize": cache.maxsize,
        "hits": cache.hits,
        "misses": cache.misses,
        "evictions": cache.evictions,
    }


def _worker(args, solver_pool=None):
    rows, cols, n, pos_a, pos_b, max_depth_past_first, placement_dir, dig_options = args
    logs = []
    cache_stats: dict = {}
    res = dig_search(
        rows,
        cols,
        n,
        pos_a,
        pos_b,
        max_depth_past_first,
        logs,
        dig_options=dig_options,
        solver_pool=solver_pool,
        cache_stats_out=cache_stats,
    )

    # Capture bfs-level LRU snapshots (populated by all solver calls this
    # worker made). Imported lazily so the module-level import order stays
    # clean for the multiprocessing spawn path.
    from src.bfs import _PARENT_MAP_CACHE, _USABLE_CACHE

    cache_stats["usable"] = _lru_snapshot(_USABLE_CACHE)
    cache_stats["parent_map"] = _lru_snapshot(_PARENT_MAP_CACHE)

    out = {
        "pos_a": pos_a,
        "pos_b": pos_b,
        "logs": logs,
        "error": None,
        "switches": None,
        "max_proof_dir": None,
        "min_proof_dir": None,
        "ws_max_template": None,
        "ws_min_template": None,
        "goals": None,
        "free_max": None,
        "free_min": None,
        "cache_stats": cache_stats,
    }

    if res is None:
        out["error"] = "no solvable workspace"
        return out

    sw = res["switches"]
    goals = res["goals"]

    max_dir = os.path.join(placement_dir, f"max_switches_S{sw:02d}_F{res['free_max_count']:02d}")
    ok, info = _plot_proof(res["ws_max"], goals, max_dir)
    if not ok:
        out["error"] = f"PROOF FAILED (max): {info}"
        return out

    min_dir = os.path.join(placement_dir, f"min_free_S{sw:02d}_F{res['free_min_count']:02d}")
    ok, info = _plot_proof(res["ws_min"], goals, min_dir)
    if not ok:
        out["error"] = f"PROOF FAILED (min): {info}"
        return out

    out["switches"] = sw
    out["max_proof_dir"] = max_dir
    out["min_proof_dir"] = min_dir
    out["free_max"] = res["free_max_count"]
    out["free_min"] = res["free_min_count"]
    out["ws_max_template"] = (rows, cols, _free_set(res["ws_max"]), pos_a, pos_b, n)
    out["ws_min_template"] = (rows, cols, _free_set(res["ws_min"]), pos_a, pos_b, n)
    out["goals"] = goals
    return out


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


def _pick_central_placements(keepers, rows, cols, n):
    """
    From the canonical-deduped keepers, return ONE representative per adjacency
    orientation (horizontal vs vertical), picking whichever placement is
    closest to the grid center.

    Rationale: any workspace reachable from a non-central placement is also
    reachable from a central placement (just leave the corresponding cells
    undug to replicate the other placement's grid-boundary walls). So running
    only the central representative(s) suffices for MAX and MIN-FREE.
    """
    center_r = (rows - 1) / 2.0
    center_c = (cols - 1) / 2.0

    def orient(pa, pb):
        # Key by |dr|, |dc| so that placements related by reflection/rotation
        # collapse to the same orientation class. Covers full-edge, partial
        # edge, and corner touching.
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


def _placement_canonical_key(rows, cols, pos_a, pos_b, n):
    if _CELL_TABLE is None or _POS_TABLE is None:
        _init_transform_tables(rows, cols, n)
    block_a = _robot_block(pos_a, n)
    block_b = _robot_block(pos_b, n)
    init_free = block_a | block_b
    # Placement dedup is a cold path — do a one-shot full canonicalization.
    return canonical_key(
        frozenset(init_free),
        pos_a,
        pos_b,
        _N_KINDS,
        _CELL_TABLE,
        _POS_TABLE,
        _BIT_STRIDE,  # type: ignore
    )


def _dedup_placements(rows, cols, n, placements):
    seen = {}
    merged = {}

    for placement in placements:
        pos_a, pos_b = placement
        key = _placement_canonical_key(rows, cols, pos_a, pos_b, n)
        if key in seen:
            rep = seen[key]
            merged[rep].append(placement)
        else:
            seen[key] = placement
            merged[placement] = [placement]
    keepers = list(seen.values())
    return keepers, merged


def find_hardest(
    rows,
    cols,
    n,
    max_depth_past_first,
    verbose=True,
    processes=None,
    strategy="strip",
    central_only=False,
    touching="edge",
    cache_mb=150,
):
    run_dir = os.path.join(get_plots_dir(), "hardest", f"run_{rows}x{cols}_n{n}")
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(run_dir, exist_ok=True)

    dig_options = DIG_STRATEGIES[strategy]

    summary = [
        f"Run: {rows}x{cols}, n={n}, depth_past_first={max_depth_past_first}, "
        f"strategy={strategy}, touching={touching}",
        "",
    ]

    _init_transform_tables(rows, cols, n, cache_mb=cache_mb)
    placement_gen = all_touching_placements if touching == "all" else all_adjacent_placements
    all_placements = list(placement_gen(rows, cols, n))
    keepers, merged = _dedup_placements(rows, cols, n, all_placements)

    # Optional: reduce further to just the most-central representative per
    # adjacency orientation. Valid because any non-central placement's
    # workspace can be replicated from a central one by leaving cells undug.
    if central_only:
        central_keepers = _pick_central_placements(keepers, rows, cols, n)
        if verbose:
            print(
                f"Placements: {len(all_placements)} total, {len(keepers)} after symmetry, "
                f"{len(central_keepers)} after central-only filter"
            )
        summary.append(
            f"Placements: {len(all_placements)} total, {len(keepers)} unique after dedup, "
            f"{len(central_keepers)} after central-only filter"
        )
        keepers = central_keepers
    elif verbose:
        print(
            f"Placements: {len(all_placements)} total, {len(keepers)} unique after symmetry dedup"
        )
    if not central_only:
        summary.append(
            f"Placements: {len(all_placements)} total, {len(keepers)} unique after dedup"
        )
    for rep, equiv_list in merged.items():
        if len(equiv_list) > 1:
            others = [p for p in equiv_list if p != rep]
            summary.append(f"  {rep} represents: {others}")
    summary.append("")

    jobs = []
    for pos_a, pos_b in keepers:
        tag = f"placement_A{pos_a[0]}{pos_a[1]}_B{pos_b[0]}{pos_b[1]}"
        placement_dir = os.path.join(run_dir, tag)
        os.makedirs(placement_dir, exist_ok=True)
        jobs.append((rows, cols, n, pos_a, pos_b, max_depth_past_first, placement_dir, dig_options))

    if verbose:
        print(f"Dispatching {len(jobs)} placements across worker pool...")

    nproc = processes or min(8, mp.cpu_count())
    results = []

    # Shared stdin kill-switch registration helper — installed for both the
    # placement-pool and central-only code paths.
    def _install_stdin_killer(pool_to_terminate):
        if not verbose:
            return
        print("Kill switch: type 'stop' (or 'q') + Enter in this terminal to abort.")

        def _stdin_watcher():
            try:
                while True:
                    line = input()
                    if line.strip().lower() in ("q", "quit", "stop", "kill", "exit"):
                        print("\n⚠  Kill requested — terminating workers.", flush=True)
                        try:
                            pool_to_terminate.terminate()
                        except Exception:
                            pass
                        os._exit(130)
            except (EOFError, OSError):
                pass

        threading.Thread(target=_stdin_watcher, daemon=True).start()

    # ────────────────────────────────────────────────────────────────────
    # central-only fast path: few jobs (1-2), many idle cores.
    # Run each placement sequentially in main, but give dig_search a fat
    # inner solver pool so cache-miss solver calls parallelize.
    # ────────────────────────────────────────────────────────────────────
    if central_only and len(jobs) <= 2 and nproc >= 2:
        # _set_transform_tables needs to run in each solver-pool worker
        # so _build_workspace / Solver in them have valid module-level tables.
        with mp.get_context("spawn").Pool(
            processes=nproc,
            initializer=_set_transform_tables,
            initargs=(_N_KINDS, _CELL_TABLE, _POS_TABLE, _BIT_STRIDE, rows, cols, n, cache_mb),
        ) as solver_pool:
            _install_stdin_killer(solver_pool)
            for job in jobs:
                out = _worker(job, solver_pool=solver_pool)
                results.append(out)
                tag = (
                    f"placement_A{out['pos_a'][0]}{out['pos_a'][1]}"
                    f"_B{out['pos_b'][0]}{out['pos_b'][1]}"
                )
                if verbose:
                    print(f"\n{tag}")
                    for line in out["logs"]:
                        print(line)
                    if out["error"]:
                        print(f"    {out['error']}")
                    else:
                        print(
                            f"    DONE: {out['switches']} switches  "
                            f"max-free={out['free_max']} min-free={out['free_min']}\n"
                        )
    else:
        with mp.get_context("spawn").Pool(
            processes=nproc,
            initializer=_set_transform_tables,
            initargs=(_N_KINDS, _CELL_TABLE, _POS_TABLE, _BIT_STRIDE, rows, cols, n, cache_mb),
        ) as pool:
            _install_stdin_killer(pool)

            for out in pool.imap_unordered(_worker, jobs):
                results.append(out)
                tag = (
                    f"placement_A{out['pos_a'][0]}{out['pos_a'][1]}"
                    f"_B{out['pos_b'][0]}{out['pos_b'][1]}"
                )
                if verbose:
                    print(f"\n{tag}")
                    for line in out["logs"]:
                        print(line)
                    if out["error"]:
                        print(f"    {out['error']}")
                    else:
                        print(
                            f"    DONE: {out['switches']} switches  "
                            f"max-free={out['free_max']} min-free={out['free_min']}\n"
                        )

    global_max_sw = -1
    global_max = None
    for out in results:
        if out["error"]:
            continue
        if out["switches"] > global_max_sw:
            global_max_sw = out["switches"]
            global_max = (
                out["ws_max_template"],
                out["goals"],
                (out["pos_a"], out["pos_b"]),
                out["free_max"],
            )

    # Tightest witness among placements tied at global max switches
    global_min = None
    for out in results:
        if out["error"] or out["switches"] != global_max_sw:
            continue
        if global_min is None or out["free_min"] < global_min[3]:
            global_min = (
                out["ws_min_template"],
                out["goals"],
                (out["pos_a"], out["pos_b"]),
                out["free_min"],
            )

    for out in results:
        tag = f"placement_A{out['pos_a'][0]}{out['pos_a'][1]}_B{out['pos_b'][0]}{out['pos_b'][1]}"
        if out["error"]:
            summary.append(f"{tag}: {out['error']}")
        else:
            summary.append(
                f"{tag}: switches={out['switches']}  "
                f"max-free={out['free_max']} -> {out['max_proof_dir']}  |  "
                f"min-free={out['free_min']} -> {out['min_proof_dir']}"
            )

    total_cells = rows * cols

    # --- Tightest workspace (min-free at global max switches) --- reported FIRST
    if global_min is not None:
        ws_t, goals_t, placement_t, fcount = global_min
        rows_, cols_, free_, pa_, pb_, n_ = ws_t
        ws_g = _build_workspace(rows_, cols_, free_, pa_, pb_, n_)
        tight_pct = 100.0 * fcount / total_cells
        gdir = os.path.join(run_dir, f"GLOBAL_TIGHTEST_S{global_max_sw:02d}_F{fcount:02d}")
        _plot_proof(ws_g, goals_t, gdir)
        summary = [
            f"TIGHTEST WORKSPACE: {global_max_sw} switches in {fcount} free cells "
            f"({tight_pct:.1f}% of {total_cells}-cell grid)",
            f"  placement: A={placement_t[0]} B={placement_t[1]}",
            f"  proof:     {gdir}",
            "",
        ] + summary

    if global_max is not None:
        ws_t, goals_t, placement_t, fcount = global_max
        rows_, cols_, free_, pa_, pb_, n_ = ws_t
        ws_g = _build_workspace(rows_, cols_, free_, pa_, pb_, n_)
        max_pct = 100.0 * fcount / total_cells
        gdir = os.path.join(run_dir, f"GLOBAL_MAX_SWITCHES_S{global_max_sw:02d}_F{fcount:02d}")
        _plot_proof(ws_g, goals_t, gdir)
        summary += [
            "",
            f"GLOBAL MAX SWITCHES: {global_max_sw} switches, {fcount} free cells "
            f"({max_pct:.1f}% of {total_cells}-cell grid)",
            f"  placement: A={placement_t[0]} B={placement_t[1]}",
            f"  proof:     {gdir}",
        ]

    # Aggregate LRU cache stats across all workers.
    agg: dict = {}
    for out in results:
        stats_per_cache = out.get("cache_stats") or {}
        for cache_name, s in stats_per_cache.items():
            a = agg.setdefault(
                cache_name,
                {"hits": 0, "misses": 0, "evictions": 0, "peak_size": 0, "maxsize": s["maxsize"]},
            )
            a["hits"] += s["hits"]
            a["misses"] += s["misses"]
            a["evictions"] += s["evictions"]
            a["peak_size"] = max(a["peak_size"], s["size"])
            a["maxsize"] = s["maxsize"]

    if agg:
        summary.append("")
        summary.append("CACHE USAGE (aggregated across all placements)")
        for cache_name in ("solver", "precheck", "usable", "parent_map"):
            a = agg.get(cache_name)
            if a is None:
                continue
            total = a["hits"] + a["misses"]
            rate = (100.0 * a["hits"] / total) if total else 0.0
            limit_hit = "  HIT LIMIT" if a["evictions"] > 0 else ""
            fill_pct = (100.0 * a["peak_size"] / a["maxsize"]) if a["maxsize"] else 0.0
            summary.append(
                f"  {cache_name:<11} peak_size={a['peak_size']}/{a['maxsize']} "
                f"({fill_pct:.0f}%)  hits={a['hits']}  misses={a['misses']}  "
                f"hit_rate={rate:.1f}%  evictions={a['evictions']}{limit_hit}"
            )
        if verbose:
            for line in summary[-(len(agg) + 2) :]:
                print(line)

    summary_path = os.path.join(run_dir, "summary.txt")
    with open(summary_path, "w") as f:
        f.write("\n".join(summary) + "\n")
    if verbose:
        print(f"\nSummary -> {summary_path}")
    return (global_max_sw, global_max, global_min), run_dir


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=int, default=3)
    p.add_argument("--cols", type=int, default=3)
    p.add_argument("--n", type=int, default=1)
    p.add_argument("--depth", type=int, default=4)
    p.add_argument("--processes", type=int, default=4)
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--strategy", choices=list(DIG_STRATEGIES.keys()), default="single")
    p.add_argument(
        "--central-only",
        action="store_true",
        help="Run only the most-central representative per adjacency orientation "
        "(1-2 placements total). Valid because any other placement's workspaces "
        "can be replicated from a central placement.",
    )
    p.add_argument(
        "--touching",
        choices=("edge", "all"),
        default="edge",
        help="'edge' (default) = only full-edge-adjacent robot pairs. "
        "'all' = also include corner-adjacent and partial-edge-offset pairs.",
    )
    p.add_argument(
        "--cache-mb",
        type=int,
        default=150,
        help="Per-worker memory budget for bfs flood caches. Cap counts "
        "auto-scale with grid area so memory stays near this target. "
        "Raise for very large grids (e.g. 500 for 30x30, 1000+ for 100x100) "
        "if you have the RAM, or lower --processes.",
    )
    args = p.parse_args()

    result, run_dir = find_hardest(
        args.rows,
        args.cols,
        args.n,
        args.depth,
        verbose=not args.quiet,
        processes=args.processes,
        strategy=args.strategy,
        central_only=args.central_only,
        touching=args.touching,
        cache_mb=args.cache_mb,
    )
    sw, gmax, gmin = result
    total_cells = args.rows * args.cols
    print("\n" + "=" * 50)
    if gmax is None:
        print("No solvable workspace found.")
    else:
        if gmin is not None:
            tight_pct = 100.0 * gmin[3] / total_cells
            print(
                f"TIGHTEST WORKSPACE: {sw} switches in {gmin[3]} free cells "
                f"({tight_pct:.1f}% of {total_cells}-cell grid)"
            )
            print(f"  placement: A={gmin[2][0]} B={gmin[2][1]}")
        if gmax is not None:
            max_pct = 100.0 * gmax[3] / total_cells
            print(
                f"GLOBAL MAX SWITCHES: {sw} switches, {gmax[3]} free cells "
                f"({max_pct:.1f}% of {total_cells}-cell grid)"
            )
            print(f"  placement: A={gmax[2][0]} B={gmax[2][1]}")
        print(f"Run dir: {run_dir}")
