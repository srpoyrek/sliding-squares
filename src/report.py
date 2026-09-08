"""
report.py
---------
Emits the browsable record of a solved test: `run.json` plus the HTML views
built from it.

Data flows one way. The solver produces `run.json` — the encoded truth about a
run — and every other view is derived from it, never hand-written:

    solver + validator  ->  run.json  ->  index.html   (this test)
                                      ->  ../index.html (all tests)
                                      ->  render_run.py (PNGs, offline)

Where the output lands, all under the plots directory::

    plots/tests/index.html              every run, one table -- the entry point
    plots/tests/<name>/run.json         the encoded record for one run
    plots/tests/<name>/index.html       that run's report
    plots/tests/<name>/png_from_json/   only when render_run.py is invoked

``<name>`` is the test's name with spaces replaced by underscores, matching the
folder ``run_tests.py`` already writes its other artifacts into.

Two properties make this work as a replacement for a folder of images:

* **Text, not pixels.** A grid is a wall bitstring plus two robot positions per
  frame, so a whole run is kilobytes where the PNGs were megabytes, it diffs in
  git, and `repomix`/`graphify` can actually read it.
* **Self-contained HTML.** Browsers refuse `fetch()` over `file://`, so the JSON
  is inlined into the page rather than loaded beside it. The report opens by
  double-click, with no server.

The markup itself lives in ``src/templates/*.html.j2`` and is rendered with
Jinja2 — see :data:`TEMPLATE_DIR`.
"""

from __future__ import annotations

import glob
import json
import os
import statistics
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

#: Bumped when the shape of run.json changes incompatibly. Readers (the HTML
#: template, render_run.py, the global index) check it before trusting a file,
#: so a stale run.json left over from an older version fails loudly instead of
#: rendering a subtly wrong picture.
SCHEMA_VERSION = 1

RUN_FILENAME = "run.json"
REPORT_FILENAME = "index.html"

#: Sub-tree of plots/ holding the BFS comparison. Named here rather than in
#: `benchmark.py` so the landing page can look for it without importing that
#: module, which imports this one.
BENCHMARK_DIRNAME = "benchmark"

#: The markup lives in real ``.html.j2`` files rather than Python strings, so an
#: editor highlights and lints the HTML, CSS and JS, and Jinja's autoescaping
#: covers every interpolation instead of each call site remembering to escape.
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

_ENV = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(default_for_string=True, default=True),
    trim_blocks=True,
    lstrip_blocks=True,
)


def fmt_change(ratio) -> str:
    """A ratio against a reference as a signed percent change: ``−43%`` is 43%
    less than the reference, ``+35%`` is 35% more, ``±0%`` is unchanged.

    The single convention for every comparison on every page -- walls, solve
    time, states -- chosen to match the wall-reduction column that already read
    ``−84%``. Negative is always better, and the same number never appears as a
    multiple in one place and a percentage in another.
    """
    if ratio is None:
        return "—"
    pct = (ratio - 1.0) * 100.0
    if abs(pct) < 0.5:
        return "±0%"
    return f"{'−' if pct < 0 else '+'}{abs(pct):.0f}%"


_ENV.filters["change"] = fmt_change


def fmt_seconds(value) -> str:
    """Elapsed seconds with an explicit unit -- the same convention run_tests
    prints and the per-run page renders, so every surface reads alike."""
    if value is None:
        return "—"
    if value < 1e-3:
        return f"{value * 1e6:.1f}us"
    if value < 1:
        return f"{value * 1e3:.1f}ms"
    return f"{value:.2f}s"


def fmt_thousands(value) -> str:
    return "—" if value is None else f"{value:,}"


# ── encoding ────────────────────────────────────────────────────────────


def encode_grid(grid) -> dict:
    """A grid as ``{rows, cols, walls}`` with walls row-major, '1' = obstacle.

    A bitstring rather than a nested list: it is a fifth of the JSON bytes and
    indexes directly as ``walls[r * cols + c]`` in both Python and JavaScript,
    so the renderer needs no unpacking step.
    """
    return {
        "rows": grid.rows,
        "cols": grid.cols,
        "walls": "".join(
            "1" if grid.tiles[r][c] != 0 else "0"
            for r in range(grid.rows)
            for c in range(grid.cols)
        ),
    }


def _frames(snapshots, titles) -> list[dict]:
    """One entry per validator step: both robot positions and what moved.

    Kept at full step resolution rather than collapsed to turns, because the
    report animates individual moves; `_turns` covers the coarser view.
    """
    out = []
    for i, ((a, b), title) in enumerate(zip(snapshots, titles)):
        moved = None
        if i:
            prev_a, prev_b = snapshots[i - 1]
            if (a.row, a.col) != (prev_a.row, prev_a.col):
                moved = a.label
            elif (b.row, b.col) != (prev_b.row, prev_b.col):
                moved = b.label
        out.append(
            {
                "i": i,
                "title": title,
                "a": [a.row, a.col],
                "b": [b.row, b.col],
                "moved": moved,
            }
        )
    return out


def _moves(waypoints) -> str:
    """The turn's command letters, read off consecutive waypoint centers.

    Derived from geometry rather than parsed out of the compact path notation:
    the positions are already exact, so this cannot disagree with what the board
    actually shows. Rows grow downward, hence +y is ``D``.
    """
    letters = []
    for (x0, y0), (x1, y1) in zip(waypoints, waypoints[1:]):
        if x1 > x0:
            letters.append("R" * round(x1 - x0))
        elif x1 < x0:
            letters.append("L" * round(x0 - x1))
        elif y1 > y0:
            letters.append("D" * round(y1 - y0))
        elif y1 < y0:
            letters.append("U" * round(y0 - y1))
    return "".join(letters)


def _turns(grid, snapshots, titles) -> list[dict]:
    """The per-switch segments, as the transition strip and chart show them.

    Delegates to the visualizer's extractor instead of re-deriving the
    segmentation: two implementations of "where does a turn end" would drift,
    and this one already defines what the PNGs mean. It touches no matplotlib,
    so importing it stays cheap.

    ``waypoints`` are the moving robot's successive centers, in cell units. They
    are what lets the report trace the route actually taken; keeping only the
    endpoints would draw every turn as a straight line from start to finish,
    which is wrong the moment a turn goes round a corner.
    """
    from src.visualizer import _contact_along_turn, _extract_turns

    out = []
    for turn in _extract_turns(snapshots, titles):
        start, end = turn["moving_start"], turn["moving_end"]
        waypoints = turn["waypoints"]
        # Walls contacted at any point during this turn, not just at its end --
        # the same per-turn highlight the PNG panels shade orange.
        wall_hits, _faces = _contact_along_turn(grid, turn)
        out.append(
            {
                "layer": turn["layer"],
                "label": end.label,
                "from": [start.row, start.col],
                "to": [end.row, end.col],
                "stationary": [turn["stationary"].row, turn["stationary"].col],
                "stationary_label": turn["stationary"].label,
                "waypoints": [[round(x, 3), round(y, 3)] for x, y in waypoints],
                "moves": _moves(waypoints),
                "steps": max(0, len(waypoints) - 1),
                "hits": [[r, c, n] for (r, c), n in sorted(wall_hits.items())],
            }
        )
    return out


def control_turns(switches: int) -> int:
    """The reported control count for a solve of ``switches`` switches.

    Control is counted from the first assignment: whichever robot moves first is
    A, that is turn 0, and each switch adds one. So a solve the search reports as
    N switches is N+1 control turns, and the layers the validator produces run
    0..N to match.

    Every number a report shows passes through here, so the search's internal
    count and the published one cannot drift apart. Comparisons stay on the raw
    value — shifting both sides by one leaves PRESERVED/FAILED unchanged.
    """
    return switches + 1


def palette() -> dict:
    """The board colours, taken from ``visualizer`` so page and PNG cannot drift.

    ``visualizer`` holds the single definition; the template emits these as CSS
    custom properties. Declaring them again in CSS would mean two sources for
    every colour, and the two renderers would diverge.

    Imported lazily to match ``_turns`` -- and because ``visualizer`` defers
    matplotlib, this costs nothing in a solver worker.
    """
    from src import visualizer as viz

    return {
        "wall": viz.COLOR_OBSTACLE,
        "free": viz.COLOR_FREE,
        "grid": viz.COLOR_GRID_LINE,
        "a": viz.COLOR_ROBOT_A,
        "b": viz.COLOR_ROBOT_B,
        "arrow_a": viz.COLOR_ARROW_A,
        "arrow_b": viz.COLOR_ARROW_B,
        "hot": viz.COLOR_BLOCKER_WALL,
        "label": viz.COLOR_LABEL,
    }


def _heat(grid, snapshots) -> dict:
    """Wall-contact counts across the whole solve — the blocker heatmap's data.

    ``{max, cells: [[row, col, hits]], faces: [[row, col, side, hits]]}``, where
    ``side`` is the N/S/E/W face of the wall that met a robot. Only touched walls
    are listed: a heatmap is sparse, so sending the whole grid would be mostly
    zeros. This separates load-bearing walls from scenery, and is the input every
    simplification recipe thins.

    Imported lazily because ``simplify`` imports this module at module level;
    deferring to call time keeps that from being a cycle.
    """
    from src.simplify import _aggregate_wall_counts

    counts, faces = _aggregate_wall_counts(grid, snapshots)
    cells = [[r, c, hits] for (r, c), hits in sorted(counts.items())]
    return {
        "max": max((hits for _, _, hits in cells), default=0),
        "cells": cells,
        "faces": [[r, c, side, hits] for (r, c, side), hits in sorted(faces.items())],
    }


def encode_sequence(grid, snapshots, titles) -> dict:
    """A validated path as ``{frames, turns, heat}`` — all a player needs.

    Shared by the main solve and by each simplification recipe, so a recipe's
    solution is browsable exactly like the original and the two can be stepped
    side by side. The heatmap is included here rather than computed separately
    so a recipe carries its own, making the comparison meaningful.
    """
    return {
        "frames": _frames(snapshots, titles),
        "turns": _turns(grid, snapshots, titles),
        "heat": _heat(grid, snapshots),
    }


def build_run(
    *,
    name,
    grid,
    robot_a,
    robot_b,
    goal_a,
    goal_b,
    snapshots,
    titles,
    switches,
    path,
    solver_seconds=None,
    solver_states=None,
    recipes=None,
) -> dict:
    """Assemble the run record. Pure: it reads state, writes nothing.

    ``solver_seconds`` is elapsed solve time in **seconds**, as a float. The
    record stores the raw number rather than a display string so its unit is
    unambiguous and it stays comparable across runs; the report picks µs / ms /
    s when rendering. ``solver_states`` is the size of the search's visited map
    -- its memory cost in states, exact and machine-independent. Each recipe
    carries the same two numbers for its own re-solve, so the report can show
    what a simplification did to the cost of solving, not only to the walls.
    """
    return {
        "schema": SCHEMA_VERSION,
        "meta": {
            "name": name,
            "rows": grid.rows,
            "cols": grid.cols,
            "n": robot_a.n,
            "switches": control_turns(switches),
            "solver_seconds": solver_seconds,
            "solver_states": solver_states,
            "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "grid": encode_grid(grid),
        "labels": {"a": robot_a.label, "b": robot_b.label},
        "start": {"a": [robot_a.row, robot_a.col], "b": [robot_b.row, robot_b.col]},
        "goal": {"a": list(goal_a), "b": list(goal_b)},
        # Normalised to one string. The solver returns a list of single-command
        # strings; leaving it a list made the record's own type depend on the
        # caller, and any consumer doing string work on it broke.
        "path": "".join(path) if isinstance(path, (list, tuple)) else (path or ""),
        # One call, so a run and a recipe are encoded by exactly the same code
        # and the comparison view can treat them interchangeably.
        **encode_sequence(grid, snapshots, titles),
        "recipes": recipes or [],
    }


def write_run(run: dict, out_dir: str) -> str:
    """Write ``run.json``. This is the artifact everything else derives from."""
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, RUN_FILENAME)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(run, fh, separators=(",", ":"))
    return dest


def load_run(run_path: str) -> dict:
    """Read a run.json, refusing one written by an incompatible schema."""
    with open(run_path, encoding="utf-8") as fh:
        run = json.load(fh)
    got = run.get("schema")
    if got != SCHEMA_VERSION:
        raise ValueError(
            f"{run_path}: schema {got!r}, expected {SCHEMA_VERSION}. "
            "Re-run the test to regenerate it."
        )
    return run


# ── HTML ────────────────────────────────────────────────────────────────


def write_local_report(run: dict, out_dir: str, parent_href: str | None = None) -> str:
    """Write the self-contained per-test ``index.html`` beside its run.json.

    ``parent_href`` is the page's "back" link. It defaults to the sibling index
    one level up, which is right for a test folder; a recipe report sits one
    level deeper and passes its own.
    """
    os.makedirs(out_dir, exist_ok=True)
    page = _ENV.get_template("report.html.j2").render(
        title=run["meta"]["name"],
        parent_href=parent_href or f"../{REPORT_FILENAME}",
        report_filename=REPORT_FILENAME,
        palette=palette(),
        # Already JSON, so autoescaping must not touch it -- but a literal
        # "</script>" inside a string value would close the host block early,
        # which is what the "</" substitution prevents.
        run_json=json.dumps(run, separators=(",", ":")).replace("</", "<\\/"),
    )
    dest = os.path.join(out_dir, REPORT_FILENAME)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(page)
    return dest


def _rank(recipe: dict) -> tuple:
    """Sort key for "best recipe": lower is better. Only ever applied to
    recipes that preserved the switch count — a failed one leaves fewer walls
    precisely because it changed the problem, so it cannot compete.

    1. **Fewest walls left.** The point of the exercise.
    2. **Most provable removals.** Recipes frequently tie on wall count, and the
       tie was previously broken by dict insertion order, which is arbitrary.
       Between two results of the same size, the one that reached it with more
       walls freed by the placement rule is the more trustworthy: those are
       lossless by construction, while contact-driven removals only happen to
       have survived this workspace's re-solve.
    3. **Name**, so equal results still order deterministically across runs.
    """
    return (
        recipe.get("walls_after", 10**9),
        -recipe.get("removed_uncrossable", 0),
        recipe.get("mode", ""),
    )


def _index_row(run_path: str) -> dict:
    """One table row for the global index, or an error row if unreadable."""
    folder = os.path.basename(os.path.dirname(run_path))
    try:
        run = load_run(run_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"folder": folder, "error": f"{type(exc).__name__}: {exc}"}
    meta, recipes = run["meta"], run.get("recipes", [])
    survivors = [r for r in recipes if r.get("preserved") and not r.get("error")]
    best = min(survivors, key=_rank, default=None)
    # The original solve's cost, which every recipe's re-solve is measured
    # against. Older run.json files predate these fields; a missing baseline
    # simply leaves the ratios empty rather than failing the row.
    base_seconds = meta.get("solver_seconds")
    base_states = meta.get("solver_states")

    def _ratio(value, base):
        return (value / base) if value and base else None

    row = {
        "folder": folder,
        "error": None,
        "name": meta["name"],
        "rows": meta["rows"],
        "cols": meta["cols"],
        "n": meta["n"],
        "switches": meta["switches"],
        "steps": len(run["frames"]),
        "solver_seconds": base_seconds,
        "solver_states": base_states,
        "recipe_total": len(recipes),
        "recipe_kept": len(survivors),
        "generated": meta["generated"],
        "best": None,
        # Kept per row so the page can rank recipes across every test, not just
        # name a winner per test.
        "detail": [
            {
                "mode": r.get("mode", "?"),
                "preserved": bool(r.get("preserved")) and not r.get("error"),
                "walls_before": r.get("walls_before", 0),
                "walls_after": r.get("walls_after", 0),
                "provable": r.get("removed_uncrossable", 0),
                "solve_seconds": r.get("solve_seconds"),
                "solve_states": r.get("solve_states"),
                "time_ratio": _ratio(r.get("solve_seconds"), base_seconds),
                "states_ratio": _ratio(r.get("solve_states"), base_states),
            }
            for r in recipes
        ],
    }

    if best:
        before, after = best.get("walls_before", 0), best.get("walls_after", 0)
        # Every recipe that reached the winning wall count, not just the one the
        # tie-break happened to pick. Recipes tie often, and showing a single
        # name implies a decisiveness the numbers do not have. Ordered by the
        # same rank, so the most provable result reads first.
        winners = sorted((r for r in survivors if r.get("walls_after") == after), key=_rank)
        row["best"] = {
            "walls_before": before,
            "walls_after": after,
            "pct": round(100.0 * (before - after) / before, 1) if before else 0.0,
            "recipes": [
                {
                    "mode": r.get("mode", "?"),
                    "href": r.get("report_href"),
                    "provable": r.get("removed_uncrossable", 0),
                }
                for r in winners
            ],
        }
    return row


def _chart_points(rows: list[dict]) -> list[dict]:
    """One point per test for the charts: robot size against difficulty.

    ``holes`` is read from the test name — the fixtures are named
    ``<n>x<n>_robot_holes`` / ``..._no_holes``, and whether a workspace has
    interior obstacles is the variable those pairs exist to isolate.

    ``walls_after`` is the best *preserving* recipe's result, i.e. the fewest
    obstacles the workspace has been shown to need while still costing the same
    number of switches.
    """
    points = []
    for row in rows:
        if row.get("error"):
            continue
        name = row["name"]
        best = row.get("best") or {}
        point = {
            "name": name,
            "n": row["n"],
            "holes": "no_holes" not in name and "holes" in name,
            "switches": row["switches"],
            "walls_before": best.get("walls_before"),
            "walls_after": best.get("walls_after"),
            # Absolute solve cost per series, keyed ``<metric>__<series>``, so
            # the size charts can overlay one line-pair per recipe on the same
            # axes as the original. Held recipes only: a failed one solved an
            # easier problem, and its cost on that test is not this recipe's.
            "time__original": row.get("solver_seconds"),
            "states__original": row.get("solver_states"),
        }
        for d in row.get("detail", []):
            if d["preserved"]:
                point[f"time__{d['mode']}"] = d.get("solve_seconds")
                point[f"states__{d['mode']}"] = d.get("solve_states")
        points.append(point)
    return sorted(points, key=lambda p: (p["holes"], p["n"]))


def _chart_modes(rows: list[dict]) -> list[str]:
    """Every recipe seen across the runs, sorted. The same sorted order assigns
    colours in the per-test chart, so a recipe keeps one colour site-wide."""
    return sorted(
        {d["mode"] for row in rows if not row.get("error") for d in row.get("detail", [])}
    )


#: One colour per recipe, assigned in sorted-name order so a recipe keeps its
#: colour across both charts and across rebuilds. Fixed hues, not theme
#: variables, for the same reason the other index charts keep a light face.
_RECIPE_COLOURS = ("#2f6fd0", "#d9822b", "#2a9d5c", "#8e44ad", "#c0392b", "#7f8c8d", "#16a085")

_CC_W, _CC_LABEL, _CC_BAR = 700, 210, 380
_CC_ROW, _CC_GAP, _CC_HEAD, _CC_GROUP_GAP, _CC_TOP = 14, 2, 18, 12, 24


def _cost_charts(rows: list[dict]) -> list[dict]:
    """Two grouped bar charts for the index: per test, each recipe's re-solve
    cost as a ratio against that test's own original solve -- one chart for
    time, one for states held.

    Per test rather than averaged, because that is where the answer lives: a
    recipe can be a bargain on a loose grid and a tax on a tight one, and a mean
    hides exactly that. Geometry is laid out here so the template only places
    rectangles. A failed recipe is drawn hollow and labelled, since its cheaper
    solve is for an easier problem and must not read as a saving.
    """
    live = [r for r in rows if not r.get("error")]
    modes = sorted({d["mode"] for r in live for d in r.get("detail", [])})
    colour = {m: _RECIPE_COLOURS[i % len(_RECIPE_COLOURS)] for i, m in enumerate(modes)}
    # Each spec: the ratio key, the absolute-value keys on the recipe and on
    # the original, and how to print that absolute -- so every bar reads as
    # both the change and the actual figure, and every heading carries the
    # original's figure the bars are measured against.
    specs = (
        (
            "time_ratio",
            "solve_seconds",
            "solver_seconds",
            fmt_seconds,
            "Solve time after simplification",
            "change vs the original solve, with the re-solve's time",
        ),
        (
            "states_ratio",
            "solve_states",
            "solver_states",
            fmt_thousands,
            "States held after simplification",
            "change vs the original solve, with the re-solve's state count",
        ),
    )
    charts = []
    for key, abs_key, base_key, fmt, title, axis in specs:
        ratios = [d[key] for r in live for d in r.get("detail", []) if d.get(key)]
        if not ratios:
            continue
        top = max(ratios + [1.0])
        scale = lambda v: _CC_BAR * v / top  # noqa: E731 -- tiny, local, and named
        groups = []
        y = _CC_TOP
        for r in live:
            heading_y = y + _CC_HEAD - 5
            y += _CC_HEAD
            bars = []
            for d in r.get("detail", []):
                v = d.get(key)
                label = fmt_change(v)
                if d.get(abs_key) is not None:
                    label += f" · {fmt(d[abs_key])}"
                bars.append(
                    {
                        "mode": d["mode"],
                        "y": y,
                        "w": round(max(2.0, scale(v)), 1) if v else 0.0,
                        "label": label,
                        "held": d["preserved"],
                        "fill": colour[d["mode"]],
                    }
                )
                y += _CC_ROW + _CC_GAP
            heading = r["name"]
            if r.get(base_key) is not None:
                heading += f" · original {fmt(r[base_key])}"
            groups.append({"name": heading, "heading_y": heading_y, "bars": bars})
            y += _CC_GROUP_GAP
        charts.append(
            {
                "title": title,
                "axis": axis,
                "groups": groups,
                "width": _CC_W,
                "height": y + 4,
                "bar_x": _CC_LABEL,
                "bar_h": _CC_ROW - 3,
                "ref_x": round(_CC_LABEL + scale(1.0), 1),
                "legend": [{"mode": m, "fill": colour[m]} for m in modes],
            }
        )
    return charts


def _leaderboard(rows: list[dict]) -> list[dict]:
    """Every recipe ranked across all tests, strongest reduction first.

    The per-test winner says which recipe suited one workspace; this says which
    is worth reaching for in general. Ranked on mean reduction over the tests
    where the recipe *held* — averaging in a failed run would reward breaking
    the problem, since a broken result is the smallest of all.
    """
    stats: dict[str, dict] = {}
    for row in rows:
        if row.get("error"):
            continue
        winners = {r["mode"] for r in (row.get("best") or {}).get("recipes", [])}
        for entry in row.get("detail", []):
            acc = stats.setdefault(
                entry["mode"],
                {
                    "mode": entry["mode"],
                    "runs": 0,
                    "kept": 0,
                    "wins": 0,
                    "pcts": [],
                    "time_ratios": [],
                    "states_ratios": [],
                },
            )
            acc["runs"] += 1
            if not entry["preserved"]:
                continue
            acc["kept"] += 1
            before, after = entry["walls_before"], entry["walls_after"]
            if before:
                acc["pcts"].append(100.0 * (before - after) / before)
            if entry["mode"] in winners:
                acc["wins"] += 1
            # Solve-cost ratios against the original, over held runs only for
            # the same reason as the reduction: a failed recipe solved an
            # easier problem, and its cheaper solve is not a saving.
            if entry.get("time_ratio"):
                acc["time_ratios"].append(entry["time_ratio"])
            if entry.get("states_ratio"):
                acc["states_ratios"].append(entry["states_ratio"])

    board = []
    for acc in stats.values():
        pcts = acc.pop("pcts")
        acc["avg_pct"] = round(sum(pcts) / len(pcts), 1) if pcts else 0.0
        acc["always_held"] = acc["kept"] == acc["runs"]
        # Geometric means: a ratio's centre is multiplicative, and 2.0x against
        # 0.5x must average to 1.0x, which an arithmetic mean puts at 1.25x.
        for key in ("time_ratios", "states_ratios"):
            values = acc.pop(key)
            acc[key[:-1]] = statistics.geometric_mean(values) if values else None
        board.append(acc)
    # Reduction first; a recipe that never failed breaks a tie over one that did.
    return sorted(board, key=lambda a: (-a["avg_pct"], -a["kept"], a["mode"]))


def write_site_index(plots_dir: str) -> str:
    """Write ``plots/index.html`` — the landing page linking the report trees.

    Lives here rather than in the script that first wrote it because more than
    one build step needs to refresh it, and each links pages the others
    produced. Whichever runs last has to be able to relink, or the landing page
    ends up reflecting the order the scripts happened to be run in instead of
    what is actually on disk — which is how the benchmark card went missing
    when the comparison was built after the gallery.
    """
    os.makedirs(plots_dir, exist_ok=True)
    page = _ENV.get_template("site.html.j2").render(
        generated=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        has_benchmark=os.path.exists(os.path.join(plots_dir, BENCHMARK_DIRNAME, REPORT_FILENAME)),
    )
    dest = os.path.join(plots_dir, REPORT_FILENAME)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(page)
    return dest


def write_global_index(tests_dir: str) -> str | None:
    """Write ``plots/tests/index.html`` over every run.json found beneath it.

    Scans the whole tree rather than only this session's tests, so a filtered
    run still lands on a complete index; each row carries its own generation
    time so a stale entry is visible as stale instead of silently missing.
    Returns None when there is nothing to index.
    """
    runs = sorted(glob.glob(os.path.join(tests_dir, "*", RUN_FILENAME)))
    if not runs:
        return None
    rows = [_index_row(p) for p in runs]
    page = _ENV.get_template("index.html.j2").render(
        rows=rows,
        leaderboard=_leaderboard(rows),
        cost_charts=_cost_charts(rows),
        # Marked safe in the template: it is JSON, not markup.
        chart_json=json.dumps(_chart_points(rows), separators=(",", ":")).replace("</", "<\\/"),
        modes_json=json.dumps(_chart_modes(rows), separators=(",", ":")).replace("</", "<\\/"),
        palette=palette(),
        report_filename=REPORT_FILENAME,
    )
    dest = os.path.join(tests_dir, REPORT_FILENAME)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(page)
    return dest
