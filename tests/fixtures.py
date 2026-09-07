"""
fixtures.py
-----------
Hand-built wall layouts, one per behaviour the simplification recipes claim.

Each case is small enough that the correct answer can be worked out on paper,
which is the point: a test that only re-runs the implementation proves nothing.
Every fixture therefore carries the expectation alongside the grid, and
`tests/test_simplify.py` asserts against it while `make_gallery.py` renders the
same set as a page.

Grids are written as strings so the shape is visible in the source:

    "#" wall     "." free

`contacts` names the walls a solution is pretended to have touched. The recipes
that thin "orange" walls are driven by contact counts, so supplying them
directly isolates the wall transform from the solver — a fixture does not need
to be a solvable puzzle to prove what a recipe does to a shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.grid import Grid
from src.robot import Robot
from src.workspace import Workspace


def parse(rows: list[str]) -> list[list[int]]:
    """A picture into tiles: 1 = wall, 0 = free."""
    return [[1 if ch == "#" else 0 for ch in row] for row in rows]


def render(tiles: list[list[int]]) -> list[str]:
    """Tiles back into a picture, for readable assertion failures."""
    return ["".join("#" if cell else "." for cell in row) for row in tiles]


def walls_of(tiles) -> set[tuple[int, int]]:
    """Every wall coordinate in a tile grid."""
    return {(r, c) for r, row in enumerate(tiles) for c, cell in enumerate(row) if cell != 0}


@dataclass
class Case:
    """One fixture: a layout, a robot size, and what the recipes should do to it."""

    name: str
    n: int
    rows: list[str]
    #: What this case is here to demonstrate. Shown in the gallery.
    why: str
    #: Walls a solution is pretended to have touched, as (row, col).
    contacts: set[tuple[int, int]] = field(default_factory=set)
    #: Per-face contact counts: (row, col, face) -> hits. Needed by the
    #: spacing recipe, which reasons per wall face rather than per cell.
    face_contacts: dict = field(default_factory=dict)
    #: Expected result of `_prune_uncrossable` alone, as a picture. None when
    #: the case is not about that pass.
    uncrossable_expect: list[str] | None = None

    @property
    def tiles(self) -> list[list[int]]:
        return parse(self.rows)

    def workspace(self) -> Workspace:
        """A Workspace over this layout, robots parked in the top-left free run.

        The robots are placed only so the type is well-formed; every fixture
        here exercises the wall transform, which never reads their positions.
        """
        tiles = self.tiles
        free = sorted(
            (r, c) for r, row in enumerate(tiles) for c, cell in enumerate(row) if cell == 0
        )
        spot = free[0] if free else (0, 0)
        return Workspace(
            Grid([row[:] for row in tiles]),
            Robot("A", self.n, *spot),
            Robot("B", self.n, *spot),
        )

    def counts(self) -> dict:
        """`contacts` as the {(row, col): hits} mapping the recipes consume."""
        return {cell: 1 for cell in self.contacts}


def _edges(cells, face):
    """Shorthand: give every named cell one contact on the same face."""
    return {(r, c, face): 1 for r, c in cells}


# ── The cases ───────────────────────────────────────────────────────────
#
# Ordered from the simplest claim to the ones where two rules disagree.

CASES: list[Case] = [
    Case(
        name="n1_degenerate",
        n=1,
        why="With a 1x1 robot the uncrossable pass can never remove anything: "
        "the only placement overlapping a wall is that cell itself, so freeing "
        "it always opens exactly one new placement.",
        rows=[
            ".....",
            ".###.",
            ".###.",
            ".###.",
            ".....",
        ],
        # Identical to the input — nothing is uncrossable for n=1.
        uncrossable_expect=[
            ".....",
            ".###.",
            ".###.",
            ".###.",
            ".....",
        ],
    ),
    Case(
        name="thick_block",
        n=2,
        why="A solid mass is hollowed out: interior walls open no new 2x2 "
        "placement on their own, so they are freed, and the sweep leaves a "
        "picket rather than clearing the whole block.",
        rows=[
            "......",
            ".####.",
            ".####.",
            ".####.",
            ".####.",
            "......",
        ],
    ),
    Case(
        name="thin_line_h",
        n=2,
        why="A one-thick horizontal line thins to a picket at spacing n: the "
        "sweep frees a cell, which makes its neighbour load-bearing, so the "
        "neighbour survives.",
        rows=[
            "......",
            "......",
            "######",
            "......",
            "......",
        ],
    ),
    Case(
        name="thin_line_v",
        n=2,
        why="The same rule on a vertical line — the pass is orientation-"
        "agnostic, which a horizontal-only test would not catch.",
        rows=[
            "..#..",
            "..#..",
            "..#..",
            "..#..",
            "..#..",
        ],
    ),
    Case(
        name="corner_wall",
        n=2,
        why="A wall tucked in the grid corner. The boundary already blocks the "
        "robot there, so the wall adds nothing a placement could use.",
        rows=[
            "#....",
            ".....",
            ".....",
            ".....",
            ".....",
        ],
    ),
    Case(
        name="edge_wall",
        n=2,
        why="A single wall against the border, the case most likely to be "
        "mishandled by an off-by-one in the placement window.",
        rows=[
            ".....",
            "#....",
            ".....",
            ".....",
            ".....",
        ],
    ),
    Case(
        name="isolated_wall",
        n=2,
        why="One wall in open space is genuinely load-bearing: freeing it "
        "completes four different 2x2 placements, so it must survive.",
        rows=[
            ".....",
            ".....",
            "..#..",
            ".....",
            ".....",
        ],
        uncrossable_expect=[
            ".....",
            ".....",
            "..#..",
            ".....",
            ".....",
        ],
    ),
    Case(
        name="l_junction",
        n=2,
        why="Two lines meeting at a right angle. The corner cell belongs to "
        "both runs, so it is where a per-run rule and a per-placement rule can "
        "disagree.",
        rows=[
            "#.....",
            "#.....",
            "#.....",
            "######",
            "......",
        ],
    ),
    Case(
        name="t_junction",
        n=2,
        why="A branch point: the stem's first cell is adjacent to the crossbar, "
        "so it can be freed only if the crossbar still blocks every placement.",
        rows=[
            "......",
            "######",
            "..#...",
            "..#...",
            "..#...",
        ],
    ),
    Case(
        name="all_wall_border",
        n=1,
        why="A fully walled border is redundant — the grid edge bounds the "
        "robot identically — so cropping peels it and reports the offset.",
        rows=[
            "#####",
            "#...#",
            "#...#",
            "#...#",
            "#####",
        ],
    ),
    Case(
        name="untouched_mass",
        n=2,
        why="Contact drives the black pass, not geometry. Nothing here is "
        "touched, so the black pass takes all of it while the uncrossable pass "
        "judges the same walls purely on placements.",
        rows=[
            "......",
            ".####.",
            ".####.",
            "......",
        ],
        contacts=set(),
    ),
    Case(
        name="touched_line",
        n=2,
        why="Every wall of this line was touched, so the black pass keeps all "
        "of it and only the spacing recipe thins it — the case that separates "
        "the two strategies.",
        rows=[
            "......",
            "######",
            "......",
        ],
        contacts={(1, c) for c in range(6)},
        face_contacts=_edges([(1, c) for c in range(6)], "N"),
    ),
]

CASES_BY_NAME = {case.name: case for case in CASES}
