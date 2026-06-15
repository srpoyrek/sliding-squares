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

from src.bfs import pack_cells_mask
from src.canonical import (
    Canonicalizer,
    all_adjacent_placements,
    all_touching_placements,
    build_transform_tables,
    pick_central_placements,
)
from src.canonical import (
    robot_block as _robot_block,
)
from src.directories import get_plots_dir
from src.frontier import initial_frontier as _initial_frontier
from src.lru import LRUCache
from src.memory import MB, MemoryGuard, SpillableSet, plan_budget, rss_bytes, tree_rss_bytes
from src.solver import Solver
from src.visualizer import plot_proof as _plot_proof
from src.workspace import Workspace

# Per-process absolute RSS ceiling (bytes) for the memory guard. Set in the main
# process by _init_transform_tables and seeded into every worker by
# _set_transform_tables, so each process keeps itself under its share of the
# global --max-mb budget. None disables the guard.
_MEM_BUDGET_BYTES = None

# `visited` dedup-set RAM control. The in-RAM buffer holds up to `ram_cap`
# canonical keys, then spills to disk. ram_cap = max(floor, budget_share / key
# bytes): a fixed floor so tiny searches never spill (they fit in RAM and stay
# fast), or a slice of the per-process budget for big searches. A search whose
# total unique-key count never exceeds ram_cap never opens the disk file.
_VISITED_KEY_BYTES = 200  # rough resident bytes per canonical key
_VISITED_BUDGET_SHARE = 0.40  # fraction of the per-process budget for visited
_VISITED_RAM_FLOOR = 100_000  # never spill below this many keys

# The dig-search calls these helpers by their old private names; bind the moved
# implementations (now on Workspace) so all call sites and the hot loop stay
# unchanged.
_build_workspace = Workspace.from_free_cells
_free_set = Workspace.free_cells
_valid_block_positions = Workspace.valid_block_positions


def _solve_payload(payload):
    """Worker function: rebuild workspace and run solver.
    Used by the batch-parallel solver pool in dig_search.
    Payload: (rows, cols, n, free_cells, pos_a, pos_b, goal_a, goal_b)
    Returns: (solvable, switches)
    """
    rows, cols, n, free_cells, pos_a, pos_b, goal_a, goal_b = payload
    ws = _build_workspace(rows, cols, set(free_cells), pos_a, pos_b, n)
    res = Solver(ws, goal_a, goal_b).solve(need_path=False)
    return res.solvable, res.switches


# ---------------------------------------------------------------------------
# find_hardest-private transform-table glue (NOT the reusable API).
#
# The reusable canonical primitives live in src/canonical.py. What stays here is
# the optimization layer the dig-BFS needs and cannot share:
#   - the tables cached as module globals for hot-loop speed (no per-call attr
#     lookups),
#   - _set_transform_tables: seeds those globals into each worker process,
#   - _build_cell_bits + _canonical_key: the O(n_kinds) incremental key called
#     once per BFS expansion (Canonicalizer.key is O(n_kinds*|free|) — too slow
#     for the hot loop),
#   - _init_transform_tables also sizes the bfs LRU caches.
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


def _init_transform_tables(rows, cols, n, cache_mb=150, mem_budget_mb=None):
    """Build and set module-level transform tables. Called once in main process."""
    global _N_KINDS, _CELL_TABLE, _POS_TABLE, _BIT_STRIDE, _CELL_BITS, _MEM_BUDGET_BYTES
    _N_KINDS, _CELL_TABLE, _POS_TABLE = build_transform_tables(rows, cols, n)
    _BIT_STRIDE = cols
    _CELL_BITS = _build_cell_bits(_CELL_TABLE, _BIT_STRIDE)
    if mem_budget_mb is not None:
        _MEM_BUDGET_BYTES = int(mem_budget_mb * MB)

    from src import bfs as _bfs

    _bfs.configure_caches_for_grid(rows, cols, n, target_mb=cache_mb)
    print(
        f"Cache sizing (budget={cache_mb:.0f} MB/worker): "
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
    mem_budget_mb=None,
):
    """Assign pre-built transform tables in worker processes (no recomputation).
    Also sizes the per-worker bfs caches for the current grid dimensions so
    per-entry memory scales sanely from 4x4 to 30x30+, and seeds the per-process
    memory-guard ceiling so each worker keeps itself under its budget share."""
    global _N_KINDS, _CELL_TABLE, _POS_TABLE, _BIT_STRIDE, _CELL_BITS, _MEM_BUDGET_BYTES
    _N_KINDS = n_kinds
    _CELL_TABLE = cell_table
    _POS_TABLE = pos_table
    _BIT_STRIDE = bit_stride
    _CELL_BITS = _build_cell_bits(cell_table, bit_stride)
    if mem_budget_mb is not None:
        _MEM_BUDGET_BYTES = int(mem_budget_mb * MB)
    if grid_rows is not None and grid_cols is not None and grid_n is not None:
        from src.bfs import configure_caches_for_grid

        configure_caches_for_grid(grid_rows, grid_cols, grid_n, target_mb=cache_mb)


def _canonical_key(tf, seconds, thirds):
    """Hot-loop canonical key: O(n_kinds) per call from a precomputed
    transforms_free tuple and per-transform tiebreakers
    (seconds[k] = min(pos_a_t[k], pos_b_t[k]), thirds[k] = max). Kept separate
    from canonical.Canonicalizer.key (which is O(n_kinds * |free|)) because the
    BFS dig loop calls it once per expansion and needs the incremental form."""
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


def _decode_free_key(mask, cols):
    """Decode a free-cell bitmask (bit r*cols+c set iff (r, c) is free) back to a
    set of (r, c) cells. O(number of free cells) via lowest-set-bit iteration."""
    cells = set()
    while mask:
        lsb = mask & -mask
        idx = lsb.bit_length() - 1
        cells.add((idx // cols, idx % cols))
        mask ^= lsb
    return cells


def _tf_from_cells(free_cells):
    """Rebuild the per-transform free-cell bitmaps (one int per symmetry) from a
    free-cell set. The dig queue stores only the compact free_key and rebuilds
    this on pop — trading a little CPU for ~100x smaller queue entries."""
    tf_list = [0] * _N_KINDS  # type: ignore
    for cell in free_cells:
        bits = _CELL_BITS[cell]  # type: ignore
        for k in range(_N_KINDS):  # type: ignore
            tf_list[k] |= bits[k]
    return tuple(tf_list)


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
    mem_budget_bytes=None,
):
    goal_a, goal_b = pos_b, pos_a

    # `valid` (all n*n block positions) is consumed only by the strip strategy;
    # the default single-cell strategy reads `frontier` instead. So recompute it
    # per node only when the active strategy actually needs it.
    need_valid = dig_options is _dig_options_n_strip
    budget = mem_budget_bytes if mem_budget_bytes is not None else _MEM_BUDGET_BYTES

    block_a = _robot_block(pos_a, n)
    block_b = _robot_block(pos_b, n)

    init_free = block_a | block_b

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

    # Dedup set with a hard RAM ceiling: it spills to an on-disk sqlite table
    # once its in-RAM buffer fills, so it cannot grow without bound on a large
    # search. See the _VISITED_* constants. Unbounded fallback when no budget.
    if budget:
        visited_cap = max(
            _VISITED_RAM_FLOOR, int(budget * _VISITED_BUDGET_SHARE / _VISITED_KEY_BYTES)
        )
    else:
        visited_cap = 20_000_000
    visited = SpillableSet(ram_cap=visited_cap)

    # Min-heap priority queue of (depth, seq, free_key) entries.
    #   depth    -> primary key; preserves layered-BFS ordering.
    #   seq      -> unique tie-break so Python never compares the int payloads.
    #   free_key -> compact free-cell bitmask (bit r*cols+c set iff free). Only
    #               this int is stored per node; frontier / valid / tf are
    #               rebuilt on pop, so each entry is ~100x smaller than the full
    #               payload and the queue cannot blow the memory budget.
    queue: list = []
    seq = 0
    heapq.heappush(queue, (0, seq, pack_cells_mask(init_free, cols)))
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
    t_solver = 0.0
    nodes_visited = 0
    solver_calls = 0
    expansions_total = 0
    canon_dupes_skipped = 0
    solvable_prunes = 0  # how many solvable nodes we skipped expanding
    solvable_prune_children_skipped = 0  # immediate children that would have been enqueued
    t_start = time.perf_counter()

    # Per-depth chunked processing. We process nodes at the current depth in
    # batches to keep memory usage stable even when the BFS layer is very wide.
    MAX_BATCH_SIZE = 5000

    # Memory guard: poll real RSS in the hot loop and, when this process climbs
    # toward its per-process ceiling, run *lossless* relief — drop and then
    # shrink the bfs flood caches (pure memoization; entries are recomputed on
    # demand). The search frontier itself is never truncated, so the result
    # stays complete. budget falls back to the module-global ceiling seeded by
    # the pool initializer when not passed explicitly.
    from src.bfs import _clear_caches
    from src.bfs import shrink_caches as _shrink_caches

    guard = MemoryGuard(budget, relief=(_clear_caches, _shrink_caches)) if budget else None

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

            # Phase 1: decode each node and collect them all for solving.
            layer_records = []
            need_solve_payloads = []
            need_solve_indices = []
            for item in batch:
                depth, _pseq, free_key_int = item
                nodes_visited += 1
                if guard is not None:
                    guard.tick()
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
                # Rebuild the heavy per-node structures from the compact key;
                # the queue stores only free_key_int to keep memory bounded.
                # `valid` is skipped unless the active strategy needs it.
                free_cells = _decode_free_key(free_key_int, cols)
                frontier = _initial_frontier(rows, cols, free_cells)
                valid = _valid_block_positions(rows, cols, free_cells, n) if need_valid else None
                tf = _tf_from_cells(free_cells)

                # Every node is solved directly. (The old reach-ignoring-the-
                # other-robot precheck was a no-op for edge-adjacent placements
                # and only pruned trivially-unsolvable corner/partial nodes that
                # the solver rejects anyway, so it was removed.)  The solver
                # accepts the plain free-cell set, so no frozenset copy is made.
                need_solve_payloads.append(
                    (rows, cols, n, free_cells, pos_a, pos_b, goal_a, goal_b)
                )
                need_solve_indices.append(len(layer_records))

                layer_records.append(
                    {
                        "free_cells": free_cells,
                        "frontier": frontier,
                        "valid": valid,
                        "tf": tf,
                        "depth": depth,
                        "solve": None,
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
                        result = Solver(shared_ws, goal_a, goal_b).solve(need_path=False)
                        batch_results.append((result.solvable, result.switches))
                t_solver += time.perf_counter() - t0
                solver_calls += len(need_solve_payloads)
                for idx, res in zip(need_solve_indices, batch_results):
                    rec = layer_records[idx]
                    rec["solve"] = res

            # Phase 3: expand
            for rec in layer_records:
                depth = rec["depth"]
                free_cells = rec["free_cells"]
                frontier = rec["frontier"]
                valid = rec["valid"]
                tf = rec["tf"]

                if rec["solve"] is not None:
                    solvable, res_switches = rec["solve"]
                    if solvable:
                        if first_solvable_depth is None:
                            first_solvable_depth = depth
                            logs.append(f"    first solvable @ depth={depth}")
                        if res_switches is not None and res_switches > best_switches:
                            best_switches = res_switches
                            # Immutable snapshot of the winning free set (built
                            # only on the rare best-update, not every node).
                            snapshot = frozenset(free_cells)
                            best_free_max = snapshot
                            best_free_min = snapshot
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
                            best_free_min = frozenset(free_cells)
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
                    if guard is not None:
                        guard.tick()
                    new_free_set = free_cells | cells_to_dig

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

                    # Enqueue only the compact free-cell bitmask; frontier / valid
                    # / tf are rebuilt when this node is popped. This is what keeps
                    # the queue ~100x smaller and the whole search memory-bounded.
                    heapq.heappush(queue, (depth + 1, seq, pack_cells_mask(new_free_set, cols)))
                    seq += 1

    t_total = time.perf_counter() - t_start
    unique_enqueued = expansions_total - canon_dupes_skipped
    dedup_pct = (100.0 * canon_dupes_skipped / expansions_total) if expansions_total else 0.0
    logs.append(
        f"    timings: total={t_total:.2f}s  solver={t_solver:.2f}s  "
        f"canon={t_canon:.2f}s  "
        f"nodes={nodes_visited}  solves={solver_calls}"
    )
    logs.append(
        f"    dedup:   expansions={expansions_total}  unique={unique_enqueued}  "
        f"symmetric_dropped={canon_dupes_skipped}  ({dedup_pct:.1f}% pruned)"
    )
    disk_state = f"yes (spills={visited.spills})" if visited.disk_active else "no (fit in RAM)"
    logs.append(f"    visited: ram_cap={visited_cap} keys  spilled_to_disk={disk_state}")
    logs.append(
        f"    prune:   solvable_nodes_pruned={solvable_prunes}  "
        f"immediate_children_skipped>={solvable_prune_children_skipped}"
    )
    if guard is not None:
        logs.append(
            f"    memory:  peak_rss={guard.peak_rss / MB:.1f}MB / "
            f"{guard.budget / MB:.1f}MB ceiling  cache_relief_runs={guard.relief_runs}  "
            f"hard_breaches={guard.hard_breaches}"
        )
        if cache_stats_out is not None:
            cache_stats_out["mem_guard"] = {
                "peak_rss": guard.peak_rss,
                "budget": guard.budget,
                "relief_runs": guard.relief_runs,
                "hard_breaches": guard.hard_breaches,
            }

    visited.close()  # drop the on-disk dedup table (if one was created)

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


class _MemoryMonitor:
    """Background sampler that prints whole-process-tree RSS against the budget,
    so a run shows live memory usage. It samples from the orchestrator, which
    sees itself plus every worker child — exactly the total that must stay under
    --max-mb. Runs in a daemon thread; `stop()` returns the observed peak."""

    def __init__(self, budget_mb, interval=2.0, verbose=True):
        self.budget_mb = float(budget_mb)
        self.interval = float(interval)
        self.verbose = verbose
        self.peak_mb = 0.0
        self._stop = threading.Event()
        self._thread = None

    def _sample(self):
        cur = tree_rss_bytes() / MB
        if cur > self.peak_mb:
            self.peak_mb = cur
        return cur

    def _run(self):
        while not self._stop.wait(self.interval):
            cur = self._sample()
            if self.verbose:
                pct = (100.0 * cur / self.budget_mb) if self.budget_mb else 0.0
                flag = "  <-- OVER BUDGET" if cur > self.budget_mb else ""
                print(
                    f"  [mem] tree RSS {cur:7.1f} MB / {self.budget_mb:.0f} MB "
                    f"({pct:3.0f}%)  peak {self.peak_mb:7.1f} MB{flag}",
                    flush=True,
                )

    def start(self):
        self._sample()  # prime an initial reading before workers ramp up
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval + 1.0)
        self._sample()  # capture a final reading
        return self.peak_mb


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
    max_mb=500,
    cache_mb=None,
):
    run_dir = os.path.join(get_plots_dir(), "hardest", f"run_{rows}x{cols}_n{n}")
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(run_dir, exist_ok=True)

    dig_options = DIG_STRATEGIES[strategy]

    # ── Memory budget plan ───────────────────────────────────────────────
    # Split the single global ceiling (max_mb) across workers and cap the worker
    # count so each gets baseline + working room — this is what makes the bound
    # hold "no matter how many processes". The measured main-process RSS is a
    # good proxy for each spawned worker's baseline (spawn re-imports the same
    # modules). cache_mb is derived from the per-worker share unless overridden.
    baseline_mb = rss_bytes() / MB
    requested = processes or min(8, mp.cpu_count())
    nproc, per_proc_ceiling_mb, derived_cache_mb = plan_budget(max_mb, requested, baseline_mb)
    cache_mb_eff = cache_mb if cache_mb is not None else derived_cache_mb

    summary = [
        f"Run: {rows}x{cols}, n={n}, depth_past_first={max_depth_past_first}, "
        f"strategy={strategy}, touching={touching}",
        f"Memory: budget={max_mb:.0f} MB total  baseline~{baseline_mb:.0f} MB/proc  "
        f"workers={nproc} (requested {requested})  "
        f"ceiling~{per_proc_ceiling_mb:.0f} MB/worker  cache~{cache_mb_eff:.0f} MB/worker",
        "",
    ]
    if verbose:
        capped = f" (capped from {requested})" if nproc < requested else ""
        print(
            f"Memory plan: total budget {max_mb:.0f} MB | baseline ~{baseline_mb:.0f} MB/proc | "
            f"workers {nproc}{capped} | per-worker ceiling ~{per_proc_ceiling_mb:.0f} MB | "
            f"cache ~{cache_mb_eff:.0f} MB"
        )

    _init_transform_tables(rows, cols, n, cache_mb=cache_mb_eff, mem_budget_mb=per_proc_ceiling_mb)
    placement_gen = all_touching_placements if touching == "all" else all_adjacent_placements
    all_placements = list(placement_gen(rows, cols, n))
    keepers, merged = Canonicalizer(rows, cols, n).dedup_placements(all_placements)

    # Optional: reduce further to just the most-central representative per
    # adjacency orientation. Valid because any non-central placement's
    # workspace can be replicated from a central one by leaving cells undug.
    if central_only:
        central_keepers = pick_central_placements(keepers, rows, cols, n)
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

    # Live memory readout: prints whole-tree RSS vs. budget every couple seconds.
    monitor = _MemoryMonitor(max_mb, verbose=verbose).start()

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
            initargs=(
                _N_KINDS,
                _CELL_TABLE,
                _POS_TABLE,
                _BIT_STRIDE,
                rows,
                cols,
                n,
                cache_mb_eff,
                per_proc_ceiling_mb,
            ),
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
            initargs=(
                _N_KINDS,
                _CELL_TABLE,
                _POS_TABLE,
                _BIT_STRIDE,
                rows,
                cols,
                n,
                cache_mb_eff,
                per_proc_ceiling_mb,
            ),
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

    peak_tree_mb = monitor.stop()
    if verbose:
        over = "  <-- EXCEEDED" if peak_tree_mb > max_mb else ""
        print(f"\nPeak memory (whole tree): {peak_tree_mb:.1f} MB / {max_mb:.0f} MB budget{over}")

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

    # Memory summary: the whole-tree peak is the number that had to stay under
    # max_mb; the per-worker guard readings show how close each got to its share.
    worker_peaks = [
        (out.get("cache_stats") or {}).get("mem_guard", {}).get("peak_rss", 0) for out in results
    ]
    worker_peak_mb = (max(worker_peaks) / MB) if worker_peaks else 0.0
    breaches = sum(
        (out.get("cache_stats") or {}).get("mem_guard", {}).get("hard_breaches", 0)
        for out in results
    )
    summary.append("")
    summary.append(
        f"MEMORY: peak whole-tree RSS {peak_tree_mb:.1f} MB / {max_mb:.0f} MB budget"
        + ("  EXCEEDED" if peak_tree_mb > max_mb else "  (within budget)")
    )
    summary.append(
        f"  workers={nproc}  per-worker ceiling~{per_proc_ceiling_mb:.0f} MB  "
        f"max worker peak={worker_peak_mb:.1f} MB  cache hard_breaches={breaches}"
    )

    # Aggregate LRU cache stats across all workers.
    agg: dict = {}
    for out in results:
        stats_per_cache = out.get("cache_stats") or {}
        for cache_name, s in stats_per_cache.items():
            if cache_name == "mem_guard":  # not an LRU cache; handled above
                continue
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
        "--max-mb",
        type=float,
        default=500.0,
        help="HARD ceiling on total RAM (MB) across the whole process tree — "
        "the main process plus every worker. The run divides this across "
        "workers and caps the worker count so the bound holds no matter how "
        "many --processes you ask for or how big the grid is. Default 500.",
    )
    p.add_argument(
        "--cache-mb",
        type=float,
        default=None,
        help="Optional override of the per-worker bfs flood-cache budget (MB). "
        "By default this is DERIVED from --max-mb and the worker count, so you "
        "normally don't set it. Pass a value only to hand the caches a fixed "
        "per-worker slice instead of the computed share.",
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
        max_mb=args.max_mb,
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
