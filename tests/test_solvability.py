"""
Proves `SwapSolvability` against the things it must agree with.

The raw move graph first: on random grids every state's component is built the
slow way — one robot, one step, checking the square fits and the robots do not
overlap — and the clique construction must reproduce it exactly, start by
start. Then the solver: `bfs_mirror` must find a swap precisely where the map
says one exists, on random grids and on every shipped case in testcases/, so
the two notions of "solvable" are one. Around those, the shapes where the
answer is provable on paper — a corridor never swaps, a corridor with one side
pocket always does, a ring always does — and the swap-combination listing is
what the components force it to be: the whole component for a solvable start,
empty for an unsolvable one.
"""

from __future__ import annotations

import random
import time
from collections import deque

import pytest

from run_tests import _fmt_time, discover_test_cases
from src.bfs import (
    _make_mirror,
    _make_packers,
    bfs_bidirectional,
    bfs_mirror,
    configure_caches_for_grid,
)
from src.bitgrid import BitGrid
from src.canonical import blocks_overlap, robot_block
from src.solvability import SwapSolvability
from src.workspace import Workspace

SHAPES = [(1, 4), (2, 2), (2, 5), (3, 3), (3, 4), (4, 4)]


def _random_free(rng, rows, cols, density):
    return {(r, c) for r in range(rows) for c in range(cols) if rng.random() < density}


def _brute_components(rows, cols, free, n):
    """(states, component id per state) by queue BFS over single-step moves."""
    placements = [
        (r, c)
        for r in range(rows - n + 1)
        for c in range(cols - n + 1)
        if robot_block((r, c), n) <= free
    ]
    states = [(a, b) for a in placements for b in placements if not blocks_overlap(a, b, n)]
    state_set = set(states)
    comp = {}
    for start in states:
        if start in comp:
            continue
        comp[start] = start
        queue = deque([start])
        while queue:
            a, b = queue.popleft()
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                for nxt in (((a[0] + dr, a[1] + dc), b), (a, (b[0] + dr, b[1] + dc))):
                    if nxt in state_set and nxt not in comp:
                        comp[nxt] = start
                        queue.append(nxt)
    return states, comp


def _states_of(sol):
    placements = list(sol.valid.cells())
    return [(a, b) for a in placements for b in placements if not blocks_overlap(a, b, sol.n)]


@pytest.mark.parametrize("rows,cols", SHAPES)
@pytest.mark.parametrize("n", [1, 2])
def test_matches_the_raw_move_graph(rows, cols, n):
    rng = random.Random(rows * 31 + cols * 7 + n)
    for _ in range(8):
        free = _random_free(rng, rows, cols, density=0.75)
        states, comp = _brute_components(rows, cols, free, n)
        sol = SwapSolvability(rows, cols, free, n)
        assert sol.states == len(states)
        for a, b in states:
            expect = comp[(a, b)] == comp[(b, a)]
            assert sol.solvable(a, b) == expect, (sorted(free), a, b)
            # The rest of the component, never the start against itself.
            same = [s for s in states if comp[s] == comp[(a, b)] and s != (a, b)]
            expect_combos = sorted(same) if expect else []
            assert sorted(sol.swap_combinations(a, b)) == expect_combos, (sorted(free), a, b)


@pytest.mark.parametrize("rows,cols", SHAPES)
@pytest.mark.parametrize("n", [1, 2])
def test_agrees_with_the_solver(rows, cols, n):
    rng = random.Random(rows * 13 + cols * 5 + n)
    for _ in range(4):
        free = _random_free(rng, rows, cols, density=0.75)
        sol = SwapSolvability(rows, cols, free, n)
        starts = set(sol.solvable_starts())
        for a, b in _states_of(sol):
            ws = Workspace.from_free_cells(rows, cols, free, a, b, n)
            found = bfs_mirror(ws, b, a, need_path=False) is not None
            assert sol.solvable(a, b) == found, (sorted(free), a, b)
            assert ((a, b) in starts) == found


@pytest.mark.parametrize("case", discover_test_cases(), ids=lambda case: case.name)
def test_agrees_with_the_solver_on_the_shipped_cases(case):
    # Every case in testcases/, through the start the solver is given, checked
    # against the solver's own answer rather than assumed. The flood caches
    # are capped to the grid first, exactly as run_tests.py caps them.
    ws, goal_a, goal_b = case().setup()
    start_a, start_b = ws.robot_a.position(), ws.robot_b.position()
    assert (goal_a, goal_b) == (start_b, start_a)
    configure_caches_for_grid(ws.grid.rows, ws.grid.cols, ws.robot_a.n)
    t0 = time.perf_counter()
    out = bfs_mirror(ws, goal_a, goal_b, need_path=False)
    cold = time.perf_counter() - t0
    t0 = time.perf_counter()
    bfs_mirror(ws, goal_a, goal_b, need_path=False)
    warm = time.perf_counter() - t0
    t0 = time.perf_counter()
    sol = SwapSolvability.for_workspace(ws)
    built = time.perf_counter() - t0
    found = out is not None
    says = sol.solvable(start_a, start_b)
    # One block per case, shown under `pytest -s`: both verdicts, the times —
    # the solve cold (caches just reset) and warm (run again on the same
    # caches), the map built once — the size of what the map covered, and how
    # many of its starts can swap.
    n = ws.robot_a.n
    solvable_n = sum(1 for _ in sol.solvable_starts())
    combos_n = len(sol.swap_combinations(start_a, start_b))
    # Where a shortest swap can turn: the placements of both robots as many
    # switches from the start as from the goal (one apart when the minimum is
    # odd). `bfs_mirror` joins its two halves at such a state, and its visited
    # map carries every state out to that layer with its layer, so the whole
    # set is read off one solve: a state and its twin whose layers add up to
    # the minimum.
    midpoint = set()
    if found:
        full = bfs_mirror(ws, goal_a, goal_b, need_path=True)
        _pack, unpack = _make_packers(ws, n)
        mirror = _make_mirror(ws, n)
        layers = full["visited"]
        for sid, layer in layers.items():
            twin_layer = layers.get(mirror(sid))
            if twin_layer is not None and layer + twin_layer == full["switches"]:
                midpoint.add(unpack(sid)[:2])
    if found:
        solver_verdict = f"swap possible, minimum {out['switches']} control switches"
    else:
        solver_verdict = "swap impossible"
    map_verdict = "swap possible" if says else "swap impossible"
    lines = [
        f"{case.name}  ({ws.grid.rows} x {ws.grid.cols} grid, {n} x {n} robots)",
        f"  existing solver, bfs_mirror         : {solver_verdict}",
        f"      time taken                      : {_fmt_time(cold)} from empty caches, "
        f"{_fmt_time(warm)} run again on warm caches",
        f"  new check, SwapSolvability          : {map_verdict}",
        f"      time taken                      : {_fmt_time(built)} to build the whole map, "
        f"using {sol.floods} flood fills",
        f"  positions one robot fits in         : {sol.valid.count()}",
        f"  ways to place both robots           : {sol.states} "
        "(robot A and robot B on different, non-overlapping positions)",
        f"  starts from which they can swap     : {solvable_n} of {sol.states}",
        f"  swap combinations for this start    : {combos_n} "
        "(every other placement of both robots reachable from this start; "
        "a swap can pass through any one of them)",
        f"  midway swap combinations            : {len(midpoint)} "
        "(placements of both robots halfway along a minimum-switch swap, "
        "where the two halves of a best solution meet)",
    ]
    print("\n" + "\n".join("  " + line for line in lines))
    assert says == found
    assert sol.is_swap_combination((start_a, start_b), (start_b, start_a)) == found
    if found:
        # The clique-graph minimum must reproduce the solver's exact count.
        assert sol.min_switches((start_a, start_b), (start_b, start_a)) == out["switches"]


@pytest.mark.parametrize("case", discover_test_cases(), ids=lambda case: case.name)
def test_solver_routes_between_random_pictures_as_the_islands_predict(case):
    # Independent of the class: on each shipped workspace, random pairs of
    # pictures are handed to the solver, which must route the robots from the
    # first to the second under its own blocking rules. A route must exist
    # exactly when the class puts the two pictures on one island — so a robot
    # that blocks the only corridor is respected on both sides, and a picture
    # the class calls reachable is one the solver can actually reach.
    ws, _goal_a, _goal_b = case().setup()
    rows, cols, n = ws.grid.rows, ws.grid.cols, ws.robot_a.n
    configure_caches_for_grid(rows, cols, n)
    sol = SwapSolvability.for_workspace(ws)
    placements = list(sol.valid.cells())
    rng = random.Random(case.name)
    tried = routed = 0
    while tried < 10:
        a1, b1 = rng.sample(placements, 2)
        a2, b2 = rng.sample(placements, 2)
        if blocks_overlap(a1, b1, n) or blocks_overlap(a2, b2, n):
            continue
        start = Workspace.from_free_cells(rows, cols, ws.grid.free, a1, b1, n)
        route = bfs_bidirectional(start, a2, b2, need_path=False) is not None
        same_island = sol._find(sol._state(a1, b1)) == sol._find(sol._state(a2, b2))
        assert route == same_island, (a1, b1, a2, b2)
        tried += 1
        routed += route
    print(
        f"\n  {case.name}: the solver routed {routed} of {tried} random picture pairs, "
        "and the islands predicted every one"
    )


def test_a_corridor_never_swaps():
    # One robot's width of room: the robots keep their order whatever the
    # length. The same shape one size up — a 2-wide corridor for a 2x2 robot —
    # is the same graph in placement space.
    for length in range(2, 7):
        for n in (1, 2):
            rows, cols = n, length + n - 1
            sol = SwapSolvability(rows, cols, BitGrid.full(rows, cols), n)
            assert sol.valid.count() == length
            assert list(sol.solvable_starts()) == []


def test_without_a_passing_room_no_start_can_swap():
    # 2x2 robots in a two-wide L-shaped corridor: the robots can never get
    # past each other, so no start is solvable — the class says so and the
    # solver says so on every start. Carve one 2x2 pocket into the corner and
    # every start becomes solvable, again with the solver agreeing.
    rows, cols, n = 6, 6, 2
    corridor = {(r, c) for r in range(6) for c in (0, 1)}
    corridor |= {(r, c) for r in (4, 5) for c in range(6)}
    pocket = {(2, 2), (2, 3), (3, 2), (3, 3)}
    cases = (("L corridor, no room", corridor), ("same corridor + pocket", corridor | pocket))
    outcome = {}
    for label, free in cases:
        sol = SwapSolvability(rows, cols, free, n)
        starts = _states_of(sol)
        by_solver = 0
        for a, b in starts:
            ws = Workspace.from_free_cells(rows, cols, free, a, b, n)
            found = bfs_mirror(ws, b, a, need_path=False) is not None
            assert found == sol.solvable(a, b), (label, a, b)
            by_solver += found
        by_class = sum(1 for _ in sol.solvable_starts())
        outcome[label] = (len(starts), by_solver, by_class)
        print(
            f"\n  {label}: {len(starts)} starts, "
            f"solver says {by_solver} can swap, class says {by_class}"
        )
    assert outcome["L corridor, no room"][1:] == (0, 0)
    total = outcome["same corridor + pocket"][0]
    assert outcome["same corridor + pocket"][1:] == (total, total)


def test_one_side_pocket_is_enough_to_swap():
    # A corridor with a single cell hanging off it: one robot steps aside,
    # the other passes. Every start swaps, the two robots side by side in a
    # dead end included.
    free = {(0, c) for c in range(5)} | {(1, 2)}
    sol = SwapSolvability(2, 5, free, 1)
    assert set(sol.solvable_starts()) == {(a, b) for a in free for b in free if a != b}


@pytest.mark.parametrize(
    "rows,cols,free",
    [
        (2, 2, {(r, c) for r in range(2) for c in range(2)}),
        (3, 3, {(r, c) for r in range(3) for c in range(3)} - {(1, 1)}),
    ],
)
def test_a_ring_swaps(rows, cols, free):
    # The robots walk round the ring and come back in the other order.
    sol = SwapSolvability(rows, cols, free, 1)
    assert set(sol.solvable_starts()) == {(a, b) for a in free for b in free if a != b}


def test_swap_combinations_are_component_wide():
    rng = random.Random(5)
    for _ in range(6):
        free = _random_free(rng, 4, 4, density=0.7)
        sol = SwapSolvability(4, 4, free, 1)
        states = _states_of(sol)
        for p in states:
            combos = set(sol.swap_combinations(*p))
            assert p not in combos
            for q in states:
                if q == p:
                    continue
                assert sol.is_swap_combination(p, q) == (q in combos)
            # A state is never paired with itself; `solvable` is that question.
            with pytest.raises(ValueError):
                sol.is_swap_combination(p, p)


def _assert_trail_legal(sol, segments, start, goal):
    """Every segment really is one robot sliding inside one region around the
    other, and the chain runs from `start` to `goal` without a gap."""
    n = sol.n
    cur = start
    for mover, src, dst, parked in segments:
        moving, still = cur if mover == "A" else (cur[1], cur[0])
        assert moving == src and still == parked
        r, c = parked
        usable = sol.valid - sol.valid.rect(r - n + 1, c - n + 1, 2 * n - 1, 2 * n - 1)
        assert dst in usable.flood(usable.index(*src))
        cur = (dst, cur[1]) if mover == "A" else (cur[0], dst)
    assert cur == goal


def test_trail_is_a_legal_solution_from_start_to_goal():
    rng = random.Random(21)
    for rows, cols, n in [(2, 5, 1), (3, 4, 1), (4, 4, 2)]:
        for _ in range(5):
            free = _random_free(rng, rows, cols, density=0.8)
            sol = SwapSolvability(rows, cols, free, n)
            for a, b in _states_of(sol)[:6]:
                t = sol.trail((a, b), (b, a))
                if not sol.solvable(a, b):
                    assert t is None
                    continue
                _assert_trail_legal(sol, t, (a, b), (b, a))
    # no island, no trail
    sol = SwapSolvability(1, 4, BitGrid.full(1, 4), 1)
    assert sol.trail(((0, 0), (0, 1)), ((0, 1), (0, 0))) is None


def test_shortest_trail_matches_the_solver_and_shortcut_stays_between():
    # The exactness claim, checked against both searches: `min_switches` must
    # equal the solver's minimum on swaps (bfs_mirror) and on arbitrary goals
    # (bfs_bidirectional); the shortcut trail must stay legal, no longer than
    # the raw trail, and never beat the proven minimum.
    rng = random.Random(33)
    for rows, cols, n in [(2, 5, 1), (3, 4, 1), (4, 4, 2), (3, 3, 1)]:
        for _ in range(4):
            free = _random_free(rng, rows, cols, density=0.8)
            sol = SwapSolvability(rows, cols, free, n)
            states = _states_of(sol)
            for a, b in states[:4]:
                ws = Workspace.from_free_cells(rows, cols, free, a, b, n)
                best = bfs_mirror(ws, b, a, need_path=False)
                shortest = sol.shortest_trail((a, b), (b, a))
                minimum = sol.min_switches((a, b), (b, a))
                if best is None:
                    assert shortest is None and minimum is None
                    continue
                _assert_trail_legal(sol, shortest, (a, b), (b, a))
                assert minimum == len(shortest) - 1 == best["switches"]
                raw = sol.trail((a, b), (b, a))
                cut = sol.trail((a, b), (b, a), shortcut=True)
                _assert_trail_legal(sol, cut, (a, b), (b, a))
                assert len(cut) <= len(raw)
                assert len(cut) - 1 >= minimum
            if len(states) >= 2:
                (a, b), (ga, gb) = states[0], states[-1]
                ws = Workspace.from_free_cells(rows, cols, free, a, b, n)
                best = bfs_bidirectional(ws, ga, gb, need_path=False)
                minimum = sol.min_switches((a, b), (ga, gb))
                assert (minimum is None) == (best is None)
                if best is not None:
                    assert minimum == best["switches"]


def test_rejects_anything_that_is_not_a_state():
    sol = SwapSolvability(2, 3, {(0, 0), (0, 1), (0, 2), (1, 1)}, 1)
    with pytest.raises(ValueError):
        sol.solvable((1, 0), (0, 0))  # (1, 0) is a wall
    with pytest.raises(ValueError):
        sol.solvable((0, 1), (0, 1))  # the same square
    sol = SwapSolvability(3, 4, BitGrid.full(3, 4), 2)
    with pytest.raises(ValueError):
        sol.solvable((0, 0), (0, 1))  # 2x2 squares overlapping
    with pytest.raises(ValueError):
        sol.solvable((0, 0), (2, 0))  # runs off the bottom edge


def test_for_workspace_reads_the_grid_and_robot_size():
    free = {(r, c) for r in range(3) for c in range(3)} - {(1, 1)}
    ws = Workspace.from_free_cells(3, 3, free, (0, 0), (0, 1), 1)
    sol = SwapSolvability.for_workspace(ws)
    assert (sol.rows, sol.cols, sol.n) == (3, 3, 1)
    assert sol.solvable(ws.robot_a.position(), ws.robot_b.position())
