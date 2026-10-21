"""
render_solvability.py
---------------------
Builds the interactive solvability pages — one per test case, plus an index.

For each case this records what every pass of `SwapSolvability`'s build did,
solves the case once with `bfs_mirror` so the two verdicts sit side by side, and
writes `solvability.json` plus the page rendered from it.

The page replays the build in the browser: it runs the same union-find over the
same flood regions the record carries, so what it shows is the algorithm rather
than a picture of it, and the counts it arrives at are displayed against the
ones Python recorded. A disagreement is therefore visible on the page.

    python render_solvability.py              # every test case
    python render_solvability.py 3x3          # only cases whose name matches

Output, under the plots directory::

    plots/solvability/index.html                  every case, one table
    plots/solvability/<name>/solvability.json     the record for one case
    plots/solvability/<name>/index.html           that case's page
"""

from __future__ import annotations

import argparse
import json
import os
import time

from jinja2 import Environment, FileSystemLoader, select_autoescape

from run_tests import discover_test_cases
from src.bfs import _make_mirror, _make_packers, bfs_mirror, configure_caches_for_grid
from src.directories import get_plots_dir
from src.report import REPORT_FILENAME, encode_grid, fmt_seconds, fmt_thousands, palette
from src.solvability import SwapSolvability, _pieces

#: Bumped when the shape of solvability.json changes incompatibly, so a stale
#: file fails loudly rather than rendering a subtly wrong page.
SCHEMA_VERSION = 2

RECORD_FILENAME = "solvability.json"

#: Sub-tree of plots/ these pages live in.
SOLVABILITY_DIRNAME = "solvability"

_ENV = Environment(
    loader=FileSystemLoader(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "templates")
    ),
    autoescape=select_autoescape(default_for_string=True, default=True),
    trim_blocks=True,
    lstrip_blocks=True,
)
_ENV.filters["seconds"] = fmt_seconds
_ENV.filters["thousands"] = fmt_thousands


def _holes_bitstring(grid) -> str:
    """Which obstacles are interior holes, row-major, '1' = hole.

    `encode_grid` collapses every obstacle into one wall bitstring, which is all
    a solved-sequence player needs. These pages draw holes and boundary walls
    differently, so the distinction travels as a second string rather than by
    re-deriving it from a tile grid in the browser.
    """
    return "".join(
        "1" if (r, c) in grid.holes else "0" for r in range(grid.rows) for c in range(grid.cols)
    )


def _build_trace(sol: SwapSolvability) -> list[dict]:
    """What every pass of the build loop did, as one entry per parked position.

    Each entry carries the parked placement and its flood regions, both as
    placement indices — exactly the two things the loop derives before it starts
    joining cliques, so the page can redo the joining itself.

    The regions are recomputed here rather than reported by the class, so the
    totals are checked against the class's own counters before they are
    shipped: if the build ever stops matching this, the run fails instead of
    publishing a trace that no longer describes it.
    """
    valid, n, col_span = sol.valid, sol.n, sol.valid.cols
    steps = []
    states = floods = 0
    for parked in valid.indices():
        r, c = divmod(parked, col_span)
        usable = valid - valid.rect(r - n + 1, c - n + 1, 2 * n - 1, 2 * n - 1)
        regions = [list(piece.indices()) for piece in _pieces(usable)]
        states += usable.count()
        floods += len(regions)
        steps.append({"parked": parked, "regions": regions})
    if (states, floods) != (sol.states, sol.floods):
        raise AssertionError(
            "the recorded trace no longer matches the build it describes: "
            f"trace says {states} states / {floods} floods, "
            f"the map says {sol.states} / {sol.floods}"
        )
    return steps


def _midway(ws, out: dict, n: int) -> list[list[int]]:
    """The placements halfway along a minimum-switch swap, as [a, b, d] with d
    the switches from the start to that picture (the exchange is then the
    remaining minimum − d away).

    Read off the search's own layer map: a state whose distance from the start
    plus its relabelling's distance equals the minimum sits at the middle of a
    shortest solution, which is where `bfs_mirror` joins its two halves. Which
    robot moved last is dropped, so a placement pair counts once, keeping the
    smallest qualifying distance.
    """
    _pack, unpack = _make_packers(ws, n)
    mirror = _make_mirror(ws, n)
    layers = out["visited"]
    col_span = ws.grid.cols - n + 1
    found: dict = {}
    for sid, layer in layers.items():
        twin = layers.get(mirror(sid))
        if twin is not None and layer + twin == out["switches"]:
            pos_a, pos_b, _ctrl = unpack(sid)
            key = (pos_a[0] * col_span + pos_a[1], pos_b[0] * col_span + pos_b[1])
            if key not in found or layer < found[key]:
                found[key] = layer
    return [[a, b, d] for (a, b), d in sorted(found.items())]


def build_record(case) -> dict:
    """Assemble one case's record: the board, the build trace, both verdicts.

    The solve is timed twice — once on the caches `configure_caches_for_grid`
    has just sized for this grid, so they are empty, and once more on what that
    solve left behind. The map is built once and has no cache, so its figure is
    always a cold one and the honest comparison is against the first solve.
    """
    ws, goal_a, goal_b = case().setup()
    n = ws.robot_a.n
    start_a, start_b = ws.robot_a.position(), ws.robot_b.position()
    if (goal_a, goal_b) != (start_b, start_a):
        raise ValueError(f"{case.name}: goal is not the start with the robots exchanged")

    configure_caches_for_grid(ws.grid.rows, ws.grid.cols, n)
    t0 = time.perf_counter()
    out = bfs_mirror(ws, goal_a, goal_b, need_path=False)
    cold = time.perf_counter() - t0
    t0 = time.perf_counter()
    bfs_mirror(ws, goal_a, goal_b, need_path=False)
    warm = time.perf_counter() - t0

    t0 = time.perf_counter()
    sol = SwapSolvability.for_workspace(ws)
    built = time.perf_counter() - t0

    midway = []
    if out is not None:
        with_layers = bfs_mirror(ws, goal_a, goal_b, need_path=True)
        midway = _midway(ws, with_layers, n)

    col_span = sol.valid.cols
    return {
        "schema": SCHEMA_VERSION,
        "name": case.name,
        "n": n,
        "grid": encode_grid(ws.grid),
        "holes": _holes_bitstring(ws.grid),
        "placement_rows": sol.valid.rows,
        "placement_cols": col_span,
        "start": {
            "a": start_a[0] * col_span + start_a[1],
            "b": start_b[0] * col_span + start_b[1],
        },
        "valid": list(sol.valid.indices()),
        "steps": _build_trace(sol),
        "midway": midway,
        "solver": {
            "solvable": out is not None,
            "switches": None if out is None else out["switches"],
            "cold_seconds": cold,
            "warm_seconds": warm,
        },
        "map": {
            "solvable": sol.solvable(start_a, start_b),
            "build_seconds": built,
            "placements": sol.valid.count(),
            "states": sol.states,
            "floods": sol.floods,
            "solvable_starts": sum(1 for _ in sol.solvable_starts()),
            "swap_combinations": len(sol.swap_combinations(start_a, start_b)),
        },
        "palette": palette(),
    }


def write_record(record: dict, out_dir: str) -> str:
    """Write solvability.json — the artifact the page is rendered from."""
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, RECORD_FILENAME)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(record, fh, separators=(",", ":"))
    return dest


def write_report(record: dict, out_dir: str) -> str:
    """Write one case's page. The record is inlined, not fetched: browsers
    refuse `fetch()` over `file://`, so the page has to carry its own data to
    open by double-click."""
    os.makedirs(out_dir, exist_ok=True)
    page = _ENV.get_template("solvability.html.j2").render(
        record=record,
        # Marked safe in the template: it is JSON, not markup. The closing-tag
        # sequence is escaped so the payload cannot end its own script element.
        data_json=json.dumps(record, separators=(",", ":")).replace("</", "<\\/"),
    )
    dest = os.path.join(out_dir, REPORT_FILENAME)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(page)
    return dest


def write_index(records: list[dict], root: str) -> str:
    """Write the index over every case rendered in this run."""
    os.makedirs(root, exist_ok=True)
    page = _ENV.get_template("solvability_index.html.j2").render(
        rows=records,
        report_filename=REPORT_FILENAME,
        palette=palette(),
    )
    dest = os.path.join(root, REPORT_FILENAME)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(page)
    return dest


def render_all(name_filter: str | None = None, out_dir: str | None = None) -> list[str]:
    """Build a page per discovered case and the index over them."""
    root = out_dir or os.path.join(get_plots_dir(), SOLVABILITY_DIRNAME)
    classes = discover_test_cases()
    if name_filter:
        wanted = name_filter.lower()
        classes = [cls for cls in classes if wanted in cls.name.lower()]
    if not classes:
        print(f"No test case matching {name_filter!r}" if name_filter else "No test cases found")
        return []

    records, written = [], []
    for cls in sorted(classes, key=lambda c: c.name):
        record = build_record(cls)
        case_dir = os.path.join(root, record["name"].replace(" ", "_"))
        write_record(record, case_dir)
        page = write_report(record, case_dir)
        records.append(record)
        written.append(page)
        verdict = (
            f"solvable in {record['solver']['switches']} switches"
            if record["solver"]["solvable"]
            else "unsolvable"
        )
        agree = "agree" if record["map"]["solvable"] == record["solver"]["solvable"] else "DISAGREE"
        print(
            f"{record['name']:<22} {verdict:<28} "
            f"map built in {fmt_seconds(record['map']['build_seconds'])}  "
            f"({record['map']['states']} states, {record['map']['floods']} floods)  {agree}"
        )

    index = write_index(records, root)
    print(f"\nOpen: {index}")
    return written + [index]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument(
        "name", nargs="?", default=None, help="Substring filter over test-case names"
    )
    parser.add_argument(
        "--out",
        default=None,
        metavar="DIR",
        help=f"Write into DIR instead of plots/{SOLVABILITY_DIRNAME}/.",
    )
    args = parser.parse_args()
    render_all(args.name, args.out)
