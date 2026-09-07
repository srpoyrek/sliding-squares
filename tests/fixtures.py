"""
fixtures.py
-----------
Small worked layouts, each showing one thing the simplification recipes do.

Every case states **where the robots are and how one of them slides**. The walls
they touch are then computed by `simplify._aggregate_wall_counts` — the same
function the real pipeline uses — rather than declared here, so a fixture cannot
claim a contact the code would not produce. Declaring them by hand also risks
an empty set, which does not mean "touched nothing" but "unspecified", and would
silently make every wall look untouched.

Grids are written as pictures so the shape is visible in the source:

    "#" wall     "." free

A case is a *scenario*, not a solvable puzzle: robot B is parked, robot A slides
along a run of positions, and that is enough to produce honest contact data. The
recipes act on walls, and this isolates that from the solver.
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
    """One scenario: a layout, a robot size, where the robots are, and why."""

    name: str
    n: int
    rows: list[str]
    #: What this case demonstrates. Written to match what the code does, not
    #: what it might be assumed to do.
    why: str
    #: Successive top-left positions of robot A. One entry is a static
    #: placement; several describe a slide, and every step contributes contacts.
    path_a: list[tuple[int, int]] = field(default_factory=list)
    #: Robot B's top-left position. Parked; it still braces against walls, and
    #: those contacts count exactly as they do in a real solve.
    pos_b: tuple[int, int] = (0, 0)
    #: Expected result of `_prune_uncrossable` alone, as a picture. Set only
    #: where the answer is provable by inspection.
    uncrossable_expect: list[str] | None = None

    @property
    def tiles(self) -> list[list[int]]:
        return parse(self.rows)

    def grid(self) -> Grid:
        return Grid([row[:] for row in self.tiles])

    def snapshots(self) -> list[list[Robot]]:
        """The [A, B] pairs for each step, in the shape the aggregator wants."""
        return [
            [Robot("A", self.n, *pos), Robot("B", self.n, *self.pos_b)]
            for pos in (self.path_a or [self.pos_b])
        ]

    def workspace(self) -> Workspace:
        start = self.path_a[0] if self.path_a else self.pos_b
        return Workspace(self.grid(), Robot("A", self.n, *start), Robot("B", self.n, *self.pos_b))

    def contacts(self) -> tuple[dict, dict]:
        """(counts, face_counts) computed from the real placements.

        Imported here rather than at module scope so importing fixtures stays
        cheap and free of import-order concerns.
        """
        from src.simplify import _aggregate_wall_counts

        return _aggregate_wall_counts(self.grid(), self.snapshots())


# ── The cases ───────────────────────────────────────────────────────────
#
# Each pairs a shape with a movement, so the contact rule and the geometry rule
# act on different walls and the recipes visibly diverge.

CASES: list[Case] = [
    Case(
        name="slide_over_block",
        n=2,
        why="A 2x2 robot slides left-to-right across the top of a solid block. "
        "Only the block's top row is ever pressed, so the contact rule strips "
        "the 12 interior walls and keeps those 4 — while the geometry rule, "
        "which never looks at contact, hollows the block from the inside.",
        rows=[
            "........",
            "........",
            ".####...",
            ".####...",
            ".####...",
            ".####...",
            "........",
            "........",
        ],
        path_a=[(0, 1), (0, 2), (0, 3)],
        pos_b=(6, 6),
    ),
    Case(
        name="slide_half_a_line",
        n=2,
        why="The robot travels along only the left half of a long wall. The "
        "right half is never touched, so the contact rule deletes it outright "
        "while the geometry rule treats both halves identically — the clearest "
        "case of the two rules disagreeing.",
        rows=[
            "..........",
            "..........",
            "##########",
            "..........",
            "..........",
        ],
        path_a=[(0, 0), (0, 1), (0, 2)],
        pos_b=(3, 7),
    ),
    Case(
        name="slide_along_line",
        n=2,
        why="The same wall, but the robot traverses its whole length, so every "
        "cell is touched and the contact rule can remove none of it. Only the "
        "spacing rule thins it here, down to a picket an n x n robot still "
        "cannot cross.",
        rows=[
            "..........",
            "..........",
            "##########",
            "..........",
            "..........",
        ],
        path_a=[(0, c) for c in range(9)],
        pos_b=(3, 0),
    ),
    Case(
        name="corner_pocket",
        n=2,
        why="A wall in the grid corner with the robot pressed against it. The "
        "geometry rule KEEPS it, which is correct and easy to get wrong: "
        "freeing that one cell would complete the 2x2 placement at (0,0), so "
        "it is not redundant even though the boundary is already beside it.",
        rows=[
            "#.....",
            "......",
            "......",
            "......",
            "......",
            "......",
        ],
        path_a=[(0, 1), (1, 1)],
        pos_b=(4, 4),
    ),
    Case(
        name="l_junction",
        n=2,
        why="Two runs meeting at a right angle, the robot sliding down the "
        "inside. The corner cell belongs to both runs, which is where a "
        "per-run spacing rule and a per-placement rule can reach different "
        "answers about the same wall.",
        rows=[
            "#.......",
            "#.......",
            "#.......",
            "#.......",
            "#####...",
            "........",
            "........",
        ],
        path_a=[(0, 1), (1, 1), (2, 1)],
        pos_b=(5, 6),
    ),
    Case(
        name="t_junction",
        n=2,
        why="A branch point. The stem's first cell sits against the crossbar, "
        "so the geometry rule may free it only while the crossbar still blocks "
        "every placement through it.",
        rows=[
            "........",
            "########",
            "...##...",
            "...##...",
            "...##...",
            "........",
        ],
        path_a=[(2, 0), (2, 1)],
        pos_b=(2, 6),
    ),
    Case(
        name="n1_degenerate",
        n=1,
        why="With a 1x1 robot the geometry rule can never remove anything: the "
        "only placement overlapping a wall is that cell itself, so freeing it "
        "always opens exactly one new placement. Whatever disappears here was "
        "taken by the contact rule, never by the geometry rule.",
        rows=[
            ".....",
            ".###.",
            ".###.",
            ".###.",
            ".....",
        ],
        path_a=[(0, 1), (0, 2), (0, 3)],
        pos_b=(4, 4),
        uncrossable_expect=[
            ".....",
            ".###.",
            ".###.",
            ".###.",
            ".....",
        ],
    ),
    Case(
        name="walled_border",
        n=1,
        why="A fully walled border is redundant — the grid edge bounds the "
        "robot identically — so cropping peels it away and records the offset. "
        "Nothing is 'removed' here in the sense the other columns mean; the "
        "grid simply gets smaller.",
        rows=[
            "#####",
            "#...#",
            "#...#",
            "#...#",
            "#####",
        ],
        path_a=[(1, 1), (1, 2)],
        pos_b=(3, 3),
    ),
]

CASES_BY_NAME = {case.name: case for case in CASES}
