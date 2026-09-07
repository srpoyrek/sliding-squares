"""
simplify.py
-----------
Reusable workspace-simplification pass.

Given a solved workspace and its validated solution, this strips the workspace
down to the walls that actually matter while preserving the minimum control-
switch count: it removes all untouched ("black") walls, optionally thins the
touched ("orange") walls, optionally frees every wall the robot could never
cross, crops all-wall borders, and re-solves to verify the switch count is
unchanged.

Each recipe writes into its own <plot_dir>/simplified/<mode>/ folder — see
`mode_name` — so strategies can be compared side by side instead of
overwriting each other.

Moved out of run_tests.py so both the test runner and the hardest-workspace
generator can reuse it. Public entry point: `run_simplification`.
"""

from __future__ import annotations

import os

from src.grid import Grid
from src.robot import Robot
from src.solver import Solver
from src.validator import Validator
from src.visualizer import (
    _compute_contact_at,
    draw_sequence,
    draw_summary,
)
from src.workspace import Workspace


def _aggregate_wall_counts(grid, snapshots):
    """Count wall contact at every step, for both robots — including the
    initial placement and the stationary robot's bracing at each step.

    Returns (counts, face_counts):
      counts      : (row, col) -> total contacts (the heatmap number)
      face_counts : (row, col, wall_face) -> contacts on that single face
    """
    opposite = {"N": "S", "S": "N", "E": "W", "W": "E"}
    counts: dict = {}
    face_counts: dict = {}

    def _tally(robot, other):
        _, face_walls = _compute_contact_at(grid, robot.row, robot.col, robot.n, other)
        for robot_side, walls in face_walls.items():
            wall_side = opposite[robot_side]
            for wc in walls:
                counts[wc] = counts.get(wc, 0) + 1
                fkey = (wc[0], wc[1], wall_side)
                face_counts[fkey] = face_counts.get(fkey, 0) + 1

    for a, b in snapshots:
        _tally(a, b)
        _tally(b, a)

    return counts, face_counts


def _count_walls(grid):
    return sum(1 for r in range(grid.rows) for c in range(grid.cols) if grid.tiles[r][c] != 0)


def _orange_peak_keepers(face_counts):
    """Touched-wall cells to KEEP when thinning each side down to its peak.

    Split the touched walls into per-face straight edges: a cell pressed on
    its E/W face belongs to a vertical edge (group by column, consecutive
    rows); on its N/S face, a horizontal edge (group by row, consecutive
    cols). On each edge the cells tied for the highest per-face contact count
    form one blocking surface; since a single wall in the robot's path is
    enough to stop it, keep only the CENTER of that tie and drop the rest. A
    cell touched on two faces belongs to two edges and survives if it is the
    kept center of either.

    `face_counts` maps (row, col, wall_face) -> contacts on that one face.
    """
    edges: dict = {}
    for (r, c, face), cnt in face_counts.items():
        if face in ("E", "W"):  # vertical wall: cells share a column
            edges.setdefault((face, c), []).append((r, r, c, cnt))
        else:  # "N"/"S" horizontal wall: cells share a row
            edges.setdefault((face, r), []).append((c, r, c, cnt))

    def _keep_run(run, out):
        # The cells tied at this run's peak contact are one blocking surface;
        # the robot hits it at the center of its side, so keep only the center
        # of the tie (one wall is enough to block) and drop the rest.
        peak = max(item[3] for item in run)
        tied = [item for item in run if item[3] == peak]
        center = tied[len(tied) // 2]
        out.append((center[1], center[2]))

    keepers: list = []
    for cells in edges.values():
        cells.sort()
        run = [cells[0]]
        for prev, cur in zip(cells, cells[1:]):
            if cur[0] == prev[0] + 1:
                run.append(cur)
            else:
                _keep_run(run, keepers)
                run = [cur]
        _keep_run(run, keepers)
    return keepers


def _orange_relative_keepers(face_counts, n):
    """Like the peak keeper, but on each per-face edge also keep enough cells
    that no gap exceeds n-1 (an n×n robot can't cross). Walk the edge keeping
    every local-max plateau's center, and force-keep a cell whenever n-1 have
    been dropped since the last kept one (the counter resets on every kept
    cell). Keeping only the plateau center collapses a run of same-hit walls
    to one central wall, while the gap rule still backfills enough walls that a
    big robot can't cross.
    """
    edges: dict = {}
    for (r, c, face), cnt in face_counts.items():
        if face in ("E", "W"):
            edges.setdefault((face, c), []).append((r, r, c, cnt))
        else:
            edges.setdefault((face, r), []).append((c, r, c, cnt))

    def _is_peak(counts, i):
        # A local maximum, but on a flat plateau of equal counts (one blocking
        # surface) only the plateau's center qualifies — so a same-hit run
        # collapses to a single central wall rather than keeping every cell.
        left = right = i
        while left > 0 and counts[left - 1] == counts[i]:
            left -= 1
        while right < len(counts) - 1 and counts[right + 1] == counts[i]:
            right += 1
        rises_left = left == 0 or counts[left - 1] < counts[i]
        rises_right = right == len(counts) - 1 or counts[right + 1] < counts[i]
        return rises_left and rises_right and i == (left + right) // 2

    def _keep_run(run, out):
        counts = [it[3] for it in run]
        since = 0
        for i, it in enumerate(run):
            if _is_peak(counts, i) or since >= n - 1:
                out.append((it[1], it[2]))
                since = 0
            else:
                since += 1

    keepers: list = []
    for cells in edges.values():
        cells.sort()
        run = [cells[0]]
        for prev, cur in zip(cells, cells[1:]):
            if cur[0] == prev[0] + 1:
                run.append(cur)
            else:
                _keep_run(run, keepers)
                run = [cur]
        _keep_run(run, keepers)
    return keepers


def _prune_uncrossable(tiles, n, protected: set | frozenset = frozenset()):
    """Free every wall the robot can never cross. Mutates `tiles`.

    The solver sees the grid only through the set of legal n*n placements
    (bfs.flood_fill builds `valid_positions` from the tiles; nothing downstream
    re-reads them). So a wall whose removal opens no new placement is invisible
    to the solver — freeing it leaves the state space, the path and the switch
    count bit-identical. Lossless by construction, no re-solve needed.

    That is what thins a line of walls down to the ones that matter: with n=2,
    freeing an interior wall still leaves its neighbours blocking every 2x2
    footprint covering it, so it goes; freeing the next one WOULD open a 2x2,
    so it stays. What survives is a picket at spacing n, plus the corners where
    the robot could round the end. The spacing is derived from n, not assumed —
    a 1x1 robot keeps every wall, a 5x5 robot keeps every fifth.

    One sweep is a fixed point: freeing cells only ever ADDS placements, so a
    wall that fails the test now can never pass it later.
    """
    rows, cols = len(tiles), len(tiles[0])
    removed = []
    for wr in range(rows):
        for wc in range(cols):
            if tiles[wr][wc] == 0 or (wr, wc) in protected:
                continue
            if not any(
                all(
                    (r, c) == (wr, wc) or tiles[r][c] == 0
                    for r in range(tr, tr + n)
                    for c in range(tc, tc + n)
                )
                for tr in range(max(0, wr - n + 1), min(wr, rows - n) + 1)
                for tc in range(max(0, wc - n + 1), min(wc, cols - n) + 1)
            ):
                tiles[wr][wc] = 0
                removed.append((wr, wc))
    return removed


def mode_name(
    remove_black=True,
    remove_alternate_orange=False,
    keep_orange_peaks=False,
    keep_relative_robot_size=False,
    prune_uncrossable=False,
):
    """Folder name for one simplification recipe, e.g. "black_peaks_uncrossable".

    Each recipe writes into its own <plot_dir>/simplified/<mode>/ so runs with
    different strategies sit side by side instead of overwriting each other.
    """
    parts = []
    if remove_black:
        parts.append("black")
    if keep_orange_peaks:
        parts.append("peaks")
    elif keep_relative_robot_size:
        parts.append("relative")
    elif remove_alternate_orange:
        parts.append("alternate")
    if prune_uncrossable:
        parts.append("uncrossable")
    return "_".join(parts) or "crop_only"


# Every simplification recipe worth running, keyed by the folder it writes to
# (the key is exactly what `mode_name` returns for its kwargs). `run_tests.py
# --simplified` runs the whole set by default so the strategies can be compared
# on the same test; pass names to run a subset. `doc` is what gets printed by
# --list-recipes and written into each run's simplification.txt and summary.png,
# so a folder is never an unexplained name.
RECIPES: dict[str, dict] = {
    "black": {
        "doc": "Baseline. Drop only the walls the solution never touched; keep "
        "every touched wall as-is.",
        "kwargs": {},
    },
    "black_alternate": {
        "doc": "Baseline + drop every other touched wall in row-major order. "
        "Crude control: thins without looking at where contact happened.",
        "kwargs": {"remove_alternate_orange": True},
    },
    "black_peaks": {
        "doc": "Baseline + on each straight run of touched wall, keep only the "
        "cell the robot pressed hardest. Most aggressive heuristic.",
        "kwargs": {"keep_orange_peaks": True},
    },
    "black_relative": {
        "doc": "Baseline + keep contact peaks plus enough extra cells that no "
        "gap along a run exceeds n-1, so an n x n robot still cannot slip past.",
        "kwargs": {"keep_relative_robot_size": True},
    },
    "black_uncrossable": {
        "doc": "Baseline + exact pass: free every remaining wall whose removal "
        "opens no new n x n robot placement. Thins lines to a picket at spacing "
        "n without guessing.",
        "kwargs": {"prune_uncrossable": True},
    },
    "black_peaks_uncrossable": {
        "doc": "black_peaks, then the exact pass on whatever survived. The "
        "smallest wall set of the set, but inherits the peak heuristic's risk.",
        "kwargs": {"keep_orange_peaks": True, "prune_uncrossable": True},
    },
    "black_relative_uncrossable": {
        "doc": "black_relative, then the exact pass. The spacing rule and the "
        "placement rule agree on straight runs, so this mostly shows what the "
        "exact pass finds that the gap heuristic misses at corners.",
        "kwargs": {"keep_relative_robot_size": True, "prune_uncrossable": True},
    },
    "uncrossable": {
        "doc": "The only PROVABLY lossless recipe: nothing is removed but walls "
        "the robot could never cross, so the state space — and therefore the "
        "switch count — cannot move. Always reports PRESERVED.",
        "kwargs": {"remove_black": False, "prune_uncrossable": True},
    },
}


def describe_recipes():
    """Human-readable listing of RECIPES, for --list-recipes."""
    width = max(len(k) for k in RECIPES)
    lines = ["Simplification recipes (folder name -> what it does):", ""]
    for name, spec in RECIPES.items():
        doc = spec["doc"].split()
        line, out = f"  {name.ljust(width)}  ", []
        for word in doc:  # wrap the doc under a hanging indent
            if len(line) + len(word) + 1 > 96:
                out.append(line)
                line = " " * (width + 4)
            line += word + " "
        out.append(line)
        lines.extend(s.rstrip() for s in out)
        lines.append("")
    return "\n".join(lines)


def _crop_bounds(tiles):
    """Fully-wall rows/cols to peel from each side: (top, bottom, left, right).
    The grid edge bounds the robot like a wall, so an all-wall border is
    redundant and can be cropped away losslessly.
    """
    rows, cols = len(tiles), len(tiles[0])
    top = bottom = left = right = 0
    changed = True
    while changed:
        changed = False
        if top < rows - bottom and all(tiles[top][c] != 0 for c in range(left, cols - right)):
            top += 1
            changed = True
        if bottom < rows - top and all(
            tiles[rows - 1 - bottom][c] != 0 for c in range(left, cols - right)
        ):
            bottom += 1
            changed = True
        if left < cols - right and all(tiles[r][left] != 0 for r in range(top, rows - bottom)):
            left += 1
            changed = True
        if right < cols - left and all(
            tiles[r][cols - 1 - right] != 0 for r in range(top, rows - bottom)
        ):
            right += 1
            changed = True
    return top, bottom, left, right


def simplify_workspace(
    ws,
    contact_counts,
    face_counts=None,
    remove_alternate_orange=False,
    keep_orange_peaks=False,
    keep_relative_robot_size=False,
    prune_uncrossable=False,
    protected=None,
    remove_black=True,
):
    """Wall-removal simplification driven by the contact heatmap.

    All black walls (contact count == 0) are removed. Touched "orange" walls
    (contact count > 0) are thinned, by at most one strategy:

      - `keep_orange_peaks`: split the touched walls into per-face straight
        edges and, on each, keep only the center of the cells tied for that
        edge's highest per-face contact count (one wall is enough to block the
        robot), removing the rest (needs `face_counts`).
      - `remove_alternate_orange`: remove every other orange wall in
        row-major order (the first cell, then skip every second).

    If both are set, `keep_orange_peaks` wins; with neither, orange is kept.

    `prune_uncrossable` then runs the exact pass on whatever survived: every
    wall the n*n robot can never cross is freed, which the solver provably
    cannot notice. It composes with any of the above, or stands alone as the
    only lossless recipe (`remove_black=False`, no orange strategy).

    Cells in `protected` are exempt from all removal (e.g. walls the robots
    rest against at their start/goal positions).

    Returns (simplified_ws, removed_black, removed_orange, removed_uncrossable,
    (crop_top, crop_left)).
    """
    rows, cols = ws.grid.rows, ws.grid.cols
    new_tiles = [row[:] for row in ws.grid.tiles]

    orange_cells = [
        (r, c)
        for r in range(rows)
        for c in range(cols)
        if new_tiles[r][c] != 0 and contact_counts.get((r, c), 0) > 0
    ]

    removed_orange = []
    if keep_orange_peaks:
        keepers = set(_orange_peak_keepers(face_counts or {}))
        removed_orange = [cell for cell in orange_cells if cell not in keepers]
    elif keep_relative_robot_size:
        keepers = set(_orange_relative_keepers(face_counts or {}, ws.robot_a.n))
        removed_orange = [cell for cell in orange_cells if cell not in keepers]
    elif remove_alternate_orange:
        orange_cells.sort()
        removed_orange = orange_cells[::2]

    # Remove black (zero-contact) walls — unless asked to keep them — plus the
    # thinned orange. On a maximally-hard workspace every untouched wall is still
    # load-bearing (it blocks a shortcut), so remove_black=False + crop is the
    # only lossless pass there.
    protected = protected or set()
    removed_black = (
        [
            (r, c)
            for r in range(rows)
            for c in range(cols)
            if new_tiles[r][c] != 0
            and contact_counts.get((r, c), 0) == 0
            and (r, c) not in protected
        ]
        if remove_black
        else []
    )
    removed_orange = [cell for cell in removed_orange if cell not in protected]

    for r, c in removed_black:
        new_tiles[r][c] = 0
    for r, c in removed_orange:
        new_tiles[r][c] = 0

    # Crop fully-wall outer borders, shifting the robots into the smaller grid.
    top, bottom, left, right = _crop_bounds(ws.grid.tiles)
    cropped = [row[left : cols - right] for row in new_tiles[top : rows - bottom]]

    # Exact pass, last: whatever walls are left, free the ones the robot could
    # never cross anyway. Runs after the heuristic removals (freeing a cell can
    # only ever make a neighbouring wall matter MORE, so this stays sound
    # whatever ran before it) and after the crop, so the grid edge — which
    # bounds the robot exactly like a wall — is already doing its job instead of
    # this thinning a border that is about to be sliced off. Coordinates come
    # back in cropped space, so map them to the original grid for the report.
    n = ws.robot_a.n
    removed_uncrossable = []
    if prune_uncrossable:
        shifted = {(r - top, c - left) for r, c in protected}
        removed_uncrossable = [
            (r + top, c + left) for r, c in _prune_uncrossable(cropped, n, shifted)
        ]

    cropped_ws = Workspace(
        Grid(cropped),
        Robot(ws.robot_a.label, n, ws.robot_a.row - top, ws.robot_a.col - left),
        Robot(ws.robot_b.label, n, ws.robot_b.row - top, ws.robot_b.col - left),
    )
    return cropped_ws, removed_black, removed_orange, removed_uncrossable, (top, left)


def run_simplification(
    ws,
    goal_a,
    goal_b,
    vr,
    plot_dir,
    target_switches,
    test_name,
    remove_alternate_orange=False,
    keep_orange_peaks=False,
    keep_relative_robot_size=False,
    prune_uncrossable=False,
    remove_black=True,
):
    """Run one simplification recipe; save results into
    <plot_dir>/simplified/<mode>/, where <mode> names the recipe (see
    `mode_name`) so different strategies sit side by side.

    Returns a status dict for the result summary.
    """
    counts, face_counts = _aggregate_wall_counts(ws.grid, vr.snapshots)
    walls_before = _count_walls(ws.grid)
    mode = mode_name(
        remove_black=remove_black,
        remove_alternate_orange=remove_alternate_orange,
        keep_orange_peaks=keep_orange_peaks,
        keep_relative_robot_size=keep_relative_robot_size,
        prune_uncrossable=prune_uncrossable,
    )
    recipe_doc = RECIPES.get(mode, {}).get("doc", "")

    (
        simplified,
        removed_black,
        removed_orange,
        removed_uncrossable,
        (off_r, off_c),
    ) = simplify_workspace(
        ws,
        counts,
        face_counts=face_counts,
        remove_alternate_orange=remove_alternate_orange,
        keep_orange_peaks=keep_orange_peaks,
        keep_relative_robot_size=keep_relative_robot_size,
        prune_uncrossable=prune_uncrossable,
        remove_black=remove_black,
    )
    goal_a = (goal_a[0] - off_r, goal_a[1] - off_c)
    goal_b = (goal_b[0] - off_r, goal_b[1] - off_c)
    walls_after = _count_walls(simplified.grid)
    removed_total = len(removed_black) + len(removed_orange) + len(removed_uncrossable)

    status: dict = {
        "mode": mode,
        "doc": recipe_doc,
        "removed": removed_total,
        "removed_black": len(removed_black),
        "removed_orange": len(removed_orange),
        "removed_uncrossable": len(removed_uncrossable),
        "walls_before": walls_before,
        "walls_after": walls_after,
        "target_switches": target_switches,
    }

    # Only skip plotting when nothing changed at all. Cropping shrinks the grid
    # (walls_after < walls_before) without tagging any wall for removal, so that
    # still counts as a real simplification worth plotting.
    if removed_total == 0 and walls_after == walls_before:
        status["note"] = "no walls eligible for removal"
        status["preserved"] = True
        status["new_switches"] = target_switches
        return status

    # Verify the simplification with one solver call.
    res = Solver(simplified, goal_a, goal_b).solve()
    status["new_switches"] = res.switches if res.solvable else None
    status["preserved"] = res.solvable and res.switches == target_switches
    if not res.solvable:
        status["note"] = "simplified workspace is unsolvable"
    elif not status["preserved"]:
        status["note"] = (
            f"switches changed from {target_switches} to {res.switches} "
            "(removed walls were not all redundant)"
        )

    # Always save the attempted simplification — success or failure — so the
    # user can inspect what was removed and why.
    sub_dir = os.path.join(plot_dir, "simplified", mode)
    os.makedirs(sub_dir, exist_ok=True)

    # Capture starting positions before validator mutates the workspace.
    start_a = (simplified.robot_a.row, simplified.robot_a.col)
    start_b = (simplified.robot_b.row, simplified.robot_b.col)

    if res.solvable:
        vr2 = Validator(simplified, goal_a, goal_b).run(res.path, plot=False)
        snapshots = [[a, b] for a, b in vr2.snapshots]
        draw_sequence(
            simplified.grid,
            snapshots,
            titles=vr2.titles,
            save_dir=sub_dir,
            robot_size=ws.robot_a.n,
        )

    if status["preserved"]:
        outcome = f"PRESERVED — switches stayed at {target_switches}"
    elif res.solvable:
        outcome = f"FAILED — switches changed from {target_switches} to {res.switches}"
    else:
        outcome = "FAILED — simplified workspace is unsolvable"

    with open(os.path.join(sub_dir, "simplification.txt"), "w") as f:
        f.write(
            f"Status: {outcome}\n"
            f"Recipe: {mode}\n"
            f"  {recipe_doc}\n"
            f"Walls before: {walls_before}\n"
            f"Walls after:  {walls_after}\n"
            f"Black walls removed ({len(removed_black)}): {removed_black}\n"
            f"Orange walls removed ({len(removed_orange)}): {removed_orange}\n"
            f"Uncrossable walls removed ({len(removed_uncrossable)}): "
            f"{removed_uncrossable}\n"
        )

    # Comparison summary image: original | simplified | stats.
    pct = 100.0 * removed_total / walls_before if walls_before else 0.0
    stats = [
        ("test", test_name),
        ("recipe", mode),
        ("status", outcome),
        ("grid", f"{ws.grid.rows} x {ws.grid.cols}"),
        ("robot size", f"{ws.robot_a.n} x {ws.robot_a.n}"),
        ("original switches", target_switches),
        (
            "simplified switches",
            res.switches if res.solvable else "unsolvable",
        ),
        ("walls before", walls_before),
        ("walls after", walls_after),
        ("removed black", len(removed_black)),
        ("removed orange", len(removed_orange)),
        ("removed uncrossable", len(removed_uncrossable)),
        ("total removed", f"{removed_total} ({pct:.1f}%)"),
    ]
    summary_a = Robot(simplified.robot_a.label, simplified.robot_a.n, *start_a)
    summary_b = Robot(simplified.robot_b.label, simplified.robot_b.n, *start_b)
    panels = [
        (ws.grid, [ws.robot_a, ws.robot_b], "original"),
        (simplified.grid, [summary_a, summary_b], "simplified"),
    ]
    draw_summary(
        panels,
        stats,
        os.path.join(sub_dir, "summary.png"),
        title=f"{test_name} · {mode}  —  {outcome}",
    )

    status["plot_dir"] = sub_dir
    return status
