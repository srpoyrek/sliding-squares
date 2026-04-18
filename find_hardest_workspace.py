"""
find_hardest_workspace.py
-------------------------
Self-contained, optimized candidate generator for hardest workspaces.
Uses enqueue-time depth filtering and a sound symmetric connectivity pre-check.
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import shutil
import time
from collections import deque

from src.directories import get_plots_dir
from src.grid import Grid
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
    return Workspace(grid, a, b)


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


def _init_transform_tables(rows, cols, n):
    """Build and set module-level transform tables. Called once in main process."""
    global _N_KINDS, _CELL_TABLE, _POS_TABLE, _BIT_STRIDE
    _N_KINDS, _CELL_TABLE, _POS_TABLE = build_transform_tables(rows, cols, n)
    _BIT_STRIDE = cols


def _set_transform_tables(n_kinds, cell_table, pos_table, bit_stride):
    """Assign pre-built transform tables in worker processes (no recomputation)."""
    global _N_KINDS, _CELL_TABLE, _POS_TABLE, _BIT_STRIDE
    _N_KINDS = n_kinds
    _CELL_TABLE = cell_table
    _POS_TABLE = pos_table
    _BIT_STRIDE = bit_stride


def _canonical_key(free_set, pos_a, pos_b):
    """Canonical key using module-level transform tables."""
    if _N_KINDS is None or _CELL_TABLE is None or _POS_TABLE is None or _BIT_STRIDE is None:
        raise RuntimeError("Transform tables not initialized. Call _init_transform_tables first.")
    return canonical_key(free_set, pos_a, pos_b, _N_KINDS, _CELL_TABLE, _POS_TABLE, _BIT_STRIDE)


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
    rows, cols, n, pos_a, pos_b, max_depth_past_first, logs, dig_options=_dig_options_single_cell
):
    goal_a, goal_b = pos_b, pos_a

    block_a = _robot_block(pos_a, n)
    block_b = _robot_block(pos_b, n)

    init_free = block_a | block_b
    init_frontier = _initial_frontier(rows, cols, init_free)
    init_valid = _valid_block_positions(rows, cols, init_free, n)
    init_key = frozenset(init_free)

    visited = set()
    queue = deque([(init_key, init_frontier, init_valid, 0)])

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
    t_start = time.perf_counter()

    while queue:
        free_key, frontier, valid, depth = queue.popleft()
        if first_solvable_depth is not None and depth > first_solvable_depth + max_depth_past_first:
            continue

        nodes_visited += 1
        if nodes_visited % 20000 == 0:
            elapsed = time.perf_counter() - t_start
            qsize = len(queue)
            rate = nodes_visited / elapsed if elapsed > 0 else 0
            eta = qsize / rate if rate > 0 else 0
            print(
                f"    [{pos_a}-{pos_b}] nodes={nodes_visited} depth={depth} "
                f"best={best_switches} queue={qsize} elapsed={elapsed:.1f}s "
                f"eta={eta:.0f}s ({rate:.0f} nodes/s)",
                flush=True,
            )
        free_cells = set(free_key)

        t0 = time.perf_counter()
        precheck_ok = robot_can_reach_goal_ignoring_other(
            valid, pos_a, goal_a
        ) and robot_can_reach_goal_ignoring_other(valid, pos_b, goal_b)
        t_precheck += time.perf_counter() - t0

        if precheck_ok:
            t0 = time.perf_counter()
            sync_tiles_to(free_cells)
            t_sync += time.perf_counter() - t0

            t0 = time.perf_counter()
            result = Solver(shared_ws, goal_a, goal_b).solve()
            t_solver += time.perf_counter() - t0
            solver_calls += 1

            if result.solvable:
                if first_solvable_depth is None:
                    first_solvable_depth = depth
                    logs.append(f"    first solvable @ depth={depth}")

                if result.switches is not None and result.switches > best_switches:
                    best_switches = result.switches
                    best_free_max = free_key
                    best_free_min = free_key
                    min_free_at_max = len(free_cells)
                    logs.append(f"    NEW MAX: {result.switches} (D:{depth}, F:{len(free_cells)})")
                elif (
                    result.switches is not None
                    and result.switches == best_switches
                    and len(free_cells) < min_free_at_max
                ):
                    min_free_at_max = len(free_cells)
                    best_free_min = free_key
                    logs.append(f"    MIN-FREE witness: {len(free_cells)} (S:{result.switches})")

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
            new_canon = _canonical_key(new_key, pos_a, pos_b)
            t_canon += time.perf_counter() - t0

            if new_canon in visited:
                canon_dupes_skipped += 1
                continue
            visited.add(new_canon)

            t0 = time.perf_counter()
            new_frontier = frontier
            for cell in cells_to_dig:
                new_frontier = _extend_frontier(new_frontier, cell, new_free_set, rows, cols)
            t_frontier += time.perf_counter() - t0

            new_valid = valid
            for cell in cells_to_dig:
                new_valid = _extend_valid(new_valid, cell, new_free_set, rows, cols, n)

            queue.append((new_key, new_frontier, new_valid, depth + 1))

    t_total = time.perf_counter() - t_start
    unique_enqueued = expansions_total - canon_dupes_skipped
    dedup_pct = (100.0 * canon_dupes_skipped / expansions_total) if expansions_total else 0.0
    logs.append(
        f"    timings: total={t_total:.2f}s  solver={t_solver:.2f}s  "
        f"canon={t_canon:.2f}s  precheck={t_precheck:.2f}s  "
        f"sync={t_sync:.2f}s  frontier={t_frontier:.2f}s  "
        f"nodes={nodes_visited}  solves={solver_calls}"
    )
    logs.append(
        f"    dedup:   expansions={expansions_total}  unique={unique_enqueued}  "
        f"symmetric_dropped={canon_dupes_skipped}  ({dedup_pct:.1f}% pruned)"
    )

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


def _worker(args):
    rows, cols, n, pos_a, pos_b, max_depth_past_first, placement_dir, dig_options = args
    logs = []
    res = dig_search(
        rows, cols, n, pos_a, pos_b, max_depth_past_first, logs, dig_options=dig_options
    )

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
    for r in range(rows - n + 1):
        for c in range(cols - 2 * n + 1):
            yield ((r, c), (r, c + n))
    for r in range(rows - 2 * n + 1):
        for c in range(cols - n + 1):
            yield ((r, c), (r + n, c))
    return


def _placement_canonical_key(rows, cols, pos_a, pos_b, n):
    if _CELL_TABLE is None or _POS_TABLE is None:
        _init_transform_tables(rows, cols, n)
    block_a = _robot_block(pos_a, n)
    block_b = _robot_block(pos_b, n)
    init_free = block_a | block_b
    return _canonical_key(frozenset(init_free), pos_a, pos_b)


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
    rows, cols, n, max_depth_past_first, verbose=True, processes=None, strategy="strip"
):
    run_dir = os.path.join(get_plots_dir(), "hardest", f"run_{rows}x{cols}_n{n}")
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
    os.makedirs(run_dir, exist_ok=True)

    dig_options = DIG_STRATEGIES[strategy]

    summary = [
        f"Run: {rows}x{cols}, n={n}, depth_past_first={max_depth_past_first}, strategy={strategy}",
        "",
    ]

    _init_transform_tables(rows, cols, n)
    all_placements = list(all_adjacent_placements(rows, cols, n))
    keepers, merged = _dedup_placements(rows, cols, n, all_placements)

    if verbose:
        print(
            f"Placements: {len(all_placements)} total, {len(keepers)} unique after symmetry dedup"
        )
    summary.append(f"Placements: {len(all_placements)} total, {len(keepers)} unique after dedup")
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
    with mp.get_context("spawn").Pool(
        processes=nproc,
        initializer=_set_transform_tables,
        initargs=(_N_KINDS, _CELL_TABLE, _POS_TABLE, _BIT_STRIDE),
    ) as pool:
        for out in pool.imap_unordered(_worker, jobs):
            results.append(out)
            tag = (
                f"placement_A{out['pos_a'][0]}{out['pos_a'][1]}_B{out['pos_b'][0]}{out['pos_b'][1]}"
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
                        f"max-free={out['free_max']} min-free={out['free_min']}"
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
    p.add_argument("--processes", type=int, default=None)
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--strategy", choices=list(DIG_STRATEGIES.keys()), default="single")
    args = p.parse_args()

    result, run_dir = find_hardest(
        args.rows,
        args.cols,
        args.n,
        args.depth,
        verbose=not args.quiet,
        processes=args.processes,
        strategy=args.strategy,
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
