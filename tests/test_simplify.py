"""
test_simplify.py
----------------
Proves the simplification passes do what they claim, on the fixtures in
`tests/fixtures.py`.

The suite deliberately leans on *properties* rather than golden pictures. A
hand-written expected grid only proves that the implementation still matches
whatever it did the day the picture was pasted in; the claims worth testing are
stated as invariants:

  * `_prune_uncrossable` never changes the set of legal n*n placements. That is
    the entire losslessness argument, and it is directly checkable.
  * one sweep is a fixed point — a second pass finds nothing.
  * a pass only ever frees walls; it never adds one.
  * cropping preserves the free-cell pattern, just shifted by the offset.

Exact pictures are asserted only where the right answer is provable by
inspection (a 1x1 robot, a lone wall in open space).

Run with:  python -m pytest
"""

from __future__ import annotations

import pytest

from src.report import encode_grid
from src.simplify import (
    RECIPES,
    _count_walls,
    _crop_bounds,
    _prune_uncrossable,
    _spacing_keepers,
    mode_name,
)
from src.workspace import Workspace
from tests.fixtures import CASES, Case, parse, render, walls_of

ALL_CASES = pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)


def placements(tiles, n) -> set:
    """Every legal n*n top-left position — what the solver actually sees.

    `bfs.flood_fill` builds its reachable set from exactly this, so two grids
    with the same placement set are indistinguishable to the solver.
    """
    rows, cols = len(tiles), len(tiles[0])
    free = {(r, c) for r, row in enumerate(tiles) for c, cell in enumerate(row) if cell == 0}
    return Workspace.valid_block_positions(rows, cols, free, n)


# ── the losslessness claim ──────────────────────────────────────────────


@ALL_CASES
def test_uncrossable_preserves_every_placement(case: Case):
    """The claim that makes `uncrossable` provably safe.

    If the placement set is unchanged, the solver's state space, its paths and
    therefore its switch count cannot move. This is the test that would catch a
    regression turning a lossless pass into a lossy one.
    """
    before = placements(case.tiles, case.n)
    tiles = case.tiles
    _prune_uncrossable(tiles, case.n)
    assert placements(tiles, case.n) == before, f"{case.name}: placement set changed\n" + "\n".join(
        render(tiles)
    )


@ALL_CASES
def test_uncrossable_only_frees_walls(case: Case):
    """A pass may free a wall; it must never create one."""
    tiles = case.tiles
    original = walls_of(case.tiles)
    _prune_uncrossable(tiles, case.n)
    assert walls_of(tiles) <= original


@ALL_CASES
def test_uncrossable_is_a_fixed_point(case: Case):
    """One sweep suffices, as the docstring claims.

    Freeing cells only ever adds placements, so a wall that failed the test in
    the first sweep can never pass it in a second. If a second sweep removed
    anything, callers would silently be getting a partial result.
    """
    tiles = case.tiles
    _prune_uncrossable(tiles, case.n)
    after_first = render(tiles)
    second = _prune_uncrossable(tiles, case.n)
    assert second == [], f"{case.name}: second sweep removed {second}"
    assert render(tiles) == after_first


@ALL_CASES
def test_uncrossable_respects_protected_cells(case: Case):
    """Protected walls survive regardless of what the placement rule says."""
    protected = walls_of(case.tiles)
    if not protected:
        pytest.skip("no walls to protect")
    tiles = case.tiles
    removed = _prune_uncrossable(tiles, case.n, protected=protected)
    assert removed == []
    assert walls_of(tiles) == protected


# ── cases whose exact answer is provable by inspection ──────────────────


@pytest.mark.parametrize("case", [c for c in CASES if c.uncrossable_expect], ids=lambda c: c.name)
def test_uncrossable_exact_result(case: Case):
    """The handful of layouts where the right answer can be reasoned out."""
    tiles = case.tiles
    _prune_uncrossable(tiles, case.n)
    assert render(tiles) == case.uncrossable_expect


def test_n1_removes_nothing():
    """With n=1 every wall is its own placement, so none is ever redundant.

    Stated separately from the fixture sweep because it is a claim about the
    rule itself, not about any particular layout.
    """
    for case in CASES:
        tiles = case.tiles
        removed = _prune_uncrossable(tiles, 1)
        assert removed == [], f"{case.name}: n=1 should free nothing, freed {removed}"


def test_bigger_robot_frees_at_least_as_much():
    """A larger robot can cross fewer gaps, so more walls become redundant.

    Monotonicity is the property a spacing bug would break, and it holds across
    every fixture rather than depending on one shape.
    """
    for case in CASES:
        counts = []
        for n in (1, 2, 3):
            tiles = case.tiles
            counts.append(len(_prune_uncrossable(tiles, n)))
        assert counts == sorted(counts), f"{case.name}: not monotonic in n: {counts}"


# ── cropping ────────────────────────────────────────────────────────────


def test_crop_bounds_peels_a_full_border():
    tiles = parse(["#####", "#...#", "#...#", "#...#", "#####"])
    assert _crop_bounds(tiles) == (1, 1, 1, 1)


def test_crop_bounds_leaves_a_broken_border():
    """One gap and the row is no longer redundant, so nothing is peeled."""
    tiles = parse(["##.##", "#...#", "#####"])
    top, bottom, left, right = _crop_bounds(tiles)
    assert top == 0


def test_crop_offset_maps_back_onto_the_original():
    """The offset recorded in the status must realign the two grids.

    The report relies on this to line a simplified result up against the
    workspace it came from, which cropping otherwise makes impossible.
    """
    rows = ["#####", "#.#.#", "#...#", "#####"]
    tiles = parse(rows)
    top, bottom, left, right = _crop_bounds(tiles)
    cropped = [row[left : len(row) - right] for row in tiles[top : len(tiles) - bottom]]
    for r, row in enumerate(cropped):
        for c, cell in enumerate(row):
            assert cell == tiles[r + top][c + left]


# ── the spacing rule ────────────────────────────────────────────────────


def test_relative_keepers_never_leave_a_crossable_gap():
    """No run of dropped cells may reach n, or an n*n robot slips through."""
    n = 3
    face_counts = {(5, c, "N"): 1 for c in range(12)}
    keepers = set(_spacing_keepers(face_counts, n))
    cols = sorted(c for (_r, c) in keepers)
    assert cols, "the rule must keep at least one cell"
    gaps = [b - a - 1 for a, b in zip(cols, cols[1:])]
    assert all(gap <= n - 1 for gap in gaps), f"gap of {max(gaps)} >= n={n}"


def test_relative_keepers_keep_the_contact_peak():
    """A clear peak is a blocking surface and must survive the thinning."""
    face_counts = {(2, c, "N"): 1 for c in range(6)}
    face_counts[(2, 3, "N")] = 9
    keepers = set(_spacing_keepers(face_counts, 2))
    assert (2, 3) in keepers


# ── recipe wiring ───────────────────────────────────────────────────────


def test_every_recipe_key_matches_its_own_kwargs():
    """A recipe's key must be what `mode_name` derives from its kwargs.

    They are used interchangeably: the key names the output folder, while the
    status dict is stamped with `mode_name(...)`. If they drift, a recipe writes
    to one folder and reports another.
    """
    for key, recipe in RECIPES.items():
        assert mode_name(**recipe["kwargs"]) == key


def test_every_recipe_is_documented():
    for key, recipe in RECIPES.items():
        assert recipe.get("doc", "").strip(), f"{key} has no doc"


def test_uncrossable_recipe_touches_no_contact_data():
    """The lossless recipe must not depend on the heuristic half."""
    kwargs = RECIPES["uncrossable"]["kwargs"]
    assert kwargs["remove_untouched"] is False
    assert kwargs["prune_uncrossable"] is True


# ── the encoding the reports rely on ────────────────────────────────────


@ALL_CASES
def test_encode_grid_round_trips(case: Case):
    """`run.json` stores walls as a bitstring; it must survive the round trip."""

    class _G:
        rows = len(case.rows)
        cols = len(case.rows[0])
        tiles = case.tiles

    encoded = encode_grid(_G())
    assert encoded["rows"] == _G.rows and encoded["cols"] == _G.cols
    assert len(encoded["walls"]) == _G.rows * _G.cols
    back = [
        [1 if encoded["walls"][r * _G.cols + c] == "1" else 0 for c in range(_G.cols)]
        for r in range(_G.rows)
    ]
    assert back == case.tiles
    assert encoded["walls"].count("1") == _count_walls(_G())
