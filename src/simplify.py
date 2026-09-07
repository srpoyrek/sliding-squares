"""
simplify.py
-----------
Reusable workspace-simplification pass.

Given a solved workspace and its validated solution, this strips the workspace
down to the walls that actually matter while preserving the minimum control-
switch count: it removes every wall the solution never touched, optionally thins
the touched ones to a spacing an n*n robot cannot cross, optionally frees every
wall the robot could never cross at all, crops all-wall borders, and re-solves
to verify the switch count is unchanged.

Each recipe writes into its own <plot_dir>/simplified/<mode>/ folder — see
`mode_name` — so strategies can be compared side by side instead of
overwriting each other.

Moved out of run_tests.py so both the test runner and the hardest-workspace
generator can reuse it. Public entry point: `run_simplification`.
"""

from __future__ import annotations

import os

from src.grid import Grid
from src.report import build_run, encode_grid, encode_sequence, write_local_report, write_run
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


def _spacing_keepers(face_counts, n):
    """Touched-wall cells to KEEP when thinning each side to a robot-proof picket.

    Split the touched walls into per-face straight edges: a cell pressed on its
    E/W face belongs to a vertical edge (group by column, consecutive rows); on
    its N/S face, a horizontal edge (group by row, consecutive cols). On each
    edge, keep every local-max plateau's center, and force-keep a cell whenever
    n-1 have been dropped since the last kept one (the counter resets on every
    kept cell). Keeping only the plateau center collapses a run of same-hit
    walls to one central wall, while the gap rule still backfills enough walls
    that an n×n robot cannot cross.

    `face_counts` maps (row, col, wall_face) -> contacts on that one face.
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
    remove_untouched=True,
    keep_robot_spacing=False,
    prune_uncrossable=False,
):
    """Folder name for one recipe, e.g. "untouched_spaced_uncrossable".

    One tag per pass that runs, so the name states what was applied. The tags
    name the rule rather than the colour it is drawn in, which a reader would
    have to already know the palette to decode.

    Each recipe writes into its own <plot_dir>/simplified/<mode>/ so runs with
    different strategies sit side by side instead of overwriting each other.
    """
    parts = []
    if remove_untouched:
        parts.append("untouched")
    if keep_robot_spacing:
        parts.append("spaced")
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
    "untouched_spaced": {
        "doc": "Drop every wall the solution never touched, then thin the "
        "touched runs: keep each contact peak plus enough extra cells that no "
        "gap exceeds n-1, so an n x n robot still cannot slip past. Heuristic "
        "on both counts — it must be verified by re-solving.",
        "kwargs": {"keep_robot_spacing": True},
    },
    "untouched_uncrossable": {
        "doc": "Drop every wall the solution never touched, then free every "
        "remaining wall whose removal opens no new n x n placement. Touched "
        "walls survive unless geometry says they were never in the way.",
        "kwargs": {"prune_uncrossable": True},
    },
    "untouched_spaced_uncrossable": {
        "doc": "Everything: drop untouched walls, thin the touched runs by "
        "spacing, then apply the placement rule to what is left. The spacing "
        "and placement rules agree on straight runs, so what this adds over "
        "untouched_spaced is mostly found at corners.",
        "kwargs": {"keep_robot_spacing": True, "prune_uncrossable": True},
    },
    "uncrossable": {
        "doc": "The only PROVABLY lossless recipe. Contact is ignored entirely; "
        "a wall goes only if freeing it opens no new n x n placement, which "
        "leaves the state space — and therefore the switch count — untouched. "
        "Always reports PRESERVED.",
        "kwargs": {"remove_untouched": False, "prune_uncrossable": True},
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
    keep_robot_spacing=False,
    prune_uncrossable=False,
    protected=None,
    remove_untouched=True,
):
    """Wall-removal simplification driven by the contact heatmap.

    Every untouched wall (contact count == 0) is removed. Touched walls
    (contact count > 0) are thinned only when asked:

      - `keep_robot_spacing`: on each per-face edge keep every contact
        plateau's center, plus enough extra cells that no gap exceeds n-1, so an
        n*n robot still cannot slip past (needs `face_counts`).

    Without it, every touched wall is kept.

    `prune_uncrossable` then runs the exact pass on whatever survived: every wall
    the n*n robot can never cross is freed, which the solver provably cannot
    notice. It must run LAST — its guarantee is relative to the grid it measures,
    and walls that look redundant on the dense grid become load-bearing once the
    removals above have opened it up. It composes with any of the above, or
    stands alone as the only lossless recipe (`remove_untouched=False`, no
    thinning).

    Cells in `protected` are exempt from all removal (e.g. walls the robots
    rest against at their start/goal positions).

    Returns (simplified_ws, removed_untouched, removed_thinned,
    removed_uncrossable, cropped_away, (crop_top, crop_left)), where
    ``cropped_away`` is the number of walls the crop destroyed. Those four
    counts plus the surviving walls account for every wall in the input
    exactly once.
    """
    rows, cols = ws.grid.rows, ws.grid.cols
    new_tiles = [row[:] for row in ws.grid.tiles]
    protected = protected or set()
    n = ws.robot_a.n

    # Crop fully-wall outer borders first. An all-wall border bounds the robot
    # exactly as the grid edge does, so peeling it is lossless — but only while
    # it is still all wall. Any pass that frees a cell inside it has to run
    # after, or the crop would slice away a cell that had become free.
    top, bottom, left, right = _crop_bounds(ws.grid.tiles)
    cropped = [row[left : cols - right] for row in new_tiles[top : rows - bottom]]
    crop_rows = len(cropped)
    crop_cols = len(cropped[0]) if crop_rows else 0

    # Walls destroyed by the crop itself. Counted explicitly because every other
    # tally below is measured on the cropped grid while `walls_before` is
    # measured on the original: without this the two bases differ and the
    # breakdown cannot be reconciled against the final count.
    cropped_away = sum(cell != 0 for row in new_tiles for cell in row) - sum(
        cell != 0 for row in cropped for cell in row
    )

    def _orig(r, c):
        """Cropped coordinate back to the original grid, for reporting."""
        return (r + top, c + left)

    # Contact-driven removals first. On a maximally-hard workspace every
    # untouched wall is still load-bearing (it blocks a shortcut), so
    # remove_untouched=False + crop is the only lossless pass there.
    touched_cells = [
        _orig(r, c)
        for r in range(crop_rows)
        for c in range(crop_cols)
        if cropped[r][c] != 0 and contact_counts.get(_orig(r, c), 0) > 0
    ]

    removed_thinned = []
    if keep_robot_spacing:
        keepers = set(_spacing_keepers(face_counts or {}, n))
        removed_thinned = [cell for cell in touched_cells if cell not in keepers]

    removed_untouched = (
        [
            _orig(r, c)
            for r in range(crop_rows)
            for c in range(crop_cols)
            if cropped[r][c] != 0
            and contact_counts.get(_orig(r, c), 0) == 0
            and _orig(r, c) not in protected
        ]
        if remove_untouched
        else []
    )
    removed_thinned = [cell for cell in removed_thinned if cell not in protected]

    for r, c in removed_untouched + removed_thinned:
        cropped[r - top][c - left] = 0

    # The exact pass runs LAST, and must. Its guarantee — freeing this wall opens
    # no new n*n placement — holds only for the grid it is measured against. On
    # the dense grid it would claim far more walls (124 vs 36 on
    # 3x3_robot_holes), but those extra walls become load-bearing precisely
    # because the removals above opened the grid up. Taking them anyway makes
    # the workspace more permissive, the solver finds a shorter path, and the
    # switch count drops: untouched_spaced_uncrossable fails outright that way.
    # Running last is what makes the guarantee apply to the grid actually
    # shipped. Coordinates come back in cropped space, so map them home.
    removed_uncrossable = []
    if prune_uncrossable:
        shifted = {(r - top, c - left) for r, c in protected}
        removed_uncrossable = [_orig(r, c) for r, c in _prune_uncrossable(cropped, n, shifted)]

    cropped_ws = Workspace(
        Grid(cropped),
        Robot(ws.robot_a.label, n, ws.robot_a.row - top, ws.robot_a.col - left),
        Robot(ws.robot_b.label, n, ws.robot_b.row - top, ws.robot_b.col - left),
    )
    return (
        cropped_ws,
        removed_untouched,
        removed_thinned,
        removed_uncrossable,
        cropped_away,
        (top, left),
    )


def run_simplification(
    ws,
    goal_a,
    goal_b,
    vr,
    plot_dir,
    target_switches,
    test_name,
    keep_robot_spacing=False,
    prune_uncrossable=False,
    remove_untouched=True,
    want_png=False,
):
    """Run one simplification recipe; save results into
    <plot_dir>/simplified/<mode>/, where <mode> names the recipe (see
    `mode_name`) so different strategies sit side by side.

    Returns a status dict for the result summary. The dict always carries the
    recipe's surviving ``grid`` and, when the result is solvable, its own
    ``sequence`` — so the HTML report can play a recipe's solution beside the
    original instead of the recipe being reachable only as images.

    ``want_png`` additionally renders the matplotlib sequence and comparison
    summary. Off by default: those dominate a run's cost and the report already
    shows the same information.
    """
    counts, face_counts = _aggregate_wall_counts(ws.grid, vr.snapshots)
    walls_before = _count_walls(ws.grid)
    mode = mode_name(
        remove_untouched=remove_untouched,
        keep_robot_spacing=keep_robot_spacing,
        prune_uncrossable=prune_uncrossable,
    )
    recipe_doc = RECIPES.get(mode, {}).get("doc", "")

    (
        simplified,
        removed_untouched,
        removed_thinned,
        removed_uncrossable,
        cropped_away,
        (off_r, off_c),
    ) = simplify_workspace(
        ws,
        counts,
        face_counts=face_counts,
        keep_robot_spacing=keep_robot_spacing,
        prune_uncrossable=prune_uncrossable,
        remove_untouched=remove_untouched,
    )
    goal_a = (goal_a[0] - off_r, goal_a[1] - off_c)
    goal_b = (goal_b[0] - off_r, goal_b[1] - off_c)
    walls_after = _count_walls(simplified.grid)
    removed_total = len(removed_untouched) + len(removed_thinned) + len(removed_uncrossable)

    status: dict = {
        "mode": mode,
        "doc": recipe_doc,
        "removed": removed_total,
        "removed_untouched": len(removed_untouched),
        "removed_thinned": len(removed_thinned),
        "removed_uncrossable": len(removed_uncrossable),
        # Walls the crop destroyed. Reported so the breakdown reconciles:
        # walls_before == walls_after + removed + removed_cropped, exactly.
        "removed_cropped": cropped_away,
        # Rows/cols peeled off the top and left. Recorded because a cropped
        # result has different dimensions from the original, so this offset is
        # what maps a simplified coordinate back onto the workspace it came from.
        "crop": [off_r, off_c],
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
        # Encoded unconditionally: this is what makes the recipe's own solution
        # browsable in the parent report. The images below are the optional extra.
        status["sequence"] = encode_sequence(simplified.grid, snapshots, vr2.titles)
        status["path"] = res.path

        # The recipe also gets its own run.json + index.html in its folder, so a
        # recipe can be opened, linked and compared on its own rather than only
        # through the parent page. Robots are rebuilt at their start positions
        # because the validator above left the workspace at the final state.
        start_robot_a = Robot(simplified.robot_a.label, simplified.robot_a.n, *start_a)
        start_robot_b = Robot(simplified.robot_b.label, simplified.robot_b.n, *start_b)
        recipe_run = build_run(
            name=f"{test_name} · {mode}",
            grid=simplified.grid,
            robot_a=start_robot_a,
            robot_b=start_robot_b,
            goal_a=goal_a,
            goal_b=goal_b,
            snapshots=snapshots,
            titles=vr2.titles,
            switches=res.switches,
            path=res.path,
        )
        write_run(recipe_run, sub_dir)
        # The page sits at simplified/<mode>/, so "back" is two levels up at the
        # test's own report. `report_href` is stored relative to the test folder
        # so the parent page can link straight to it.
        write_local_report(recipe_run, sub_dir, parent_href="../../index.html")
        status["report_href"] = f"simplified/{mode}/index.html"

        if want_png:
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
            f"Untouched walls removed ({len(removed_untouched)}): {removed_untouched}\n"
            f"Thinned walls removed ({len(removed_thinned)}): {removed_thinned}\n"
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
        ("removed untouched", len(removed_untouched)),
        ("removed thinned", len(removed_thinned)),
        ("removed uncrossable", len(removed_uncrossable)),
        ("total removed", f"{removed_total} ({pct:.1f}%)"),
    ]
    summary_a = Robot(simplified.robot_a.label, simplified.robot_a.n, *start_a)
    summary_b = Robot(simplified.robot_b.label, simplified.robot_b.n, *start_b)
    panels = [
        (ws.grid, [ws.robot_a, ws.robot_b], "original"),
        (simplified.grid, [summary_a, summary_b], "simplified"),
    ]
    if want_png:
        draw_summary(
            panels,
            stats,
            os.path.join(sub_dir, "summary.png"),
            title=f"{test_name} · {mode}  —  {outcome}",
        )

    status["plot_dir"] = sub_dir
    # The surviving layout, for report.py to draw. Encoded here rather than
    # re-derived later because cropping can change the grid's dimensions, so the
    # simplified walls are only meaningful alongside their own rows/cols.
    status["grid"] = encode_grid(simplified.grid)
    return status
