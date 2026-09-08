"""
benchmark.py
------------
Measure the three BFS searches against each other on the real test cases, and
render the comparison as a self-contained HTML page.

The three searches in `bfs.py` answer the same question by different routes:

    unidirectional   one forward tree, expanded all the way to depth D
    bidirectional    a forward and a backward tree, each to depth D/2
    mirror           one forward tree to depth D/2; the backward half is that
                     same tree read through the A<->B relabelling

Because they are all exact, their switch counts *must* agree — so the numbers
here are two things at once: a performance comparison and a correctness check.
A disagreement in `switches`, or a path the validator rejects, is a defect in
whichever search stands alone.

Each measurement runs in its own spawned process. That buys three things at
once: the flood caches start empty, so whichever search runs second is not
handed the first one's work; `tracemalloc` sees only that search's
allocations; and a search that runs away can be killed on a timeout instead of
stalling the whole comparison.

Written by `benchmark_bfs.py`, which drives this module and nothing else.
Outputs land in ``plots/benchmark/``: ``benchmark.json`` is the record, and
``index.html`` is rendered from it — the same generated-from-JSON rule the test
reports follow, so the page is never hand-authored.
"""

from __future__ import annotations

import inspect
import json
import math
import multiprocessing as mp
import os
import queue
import statistics
import sys
import time
import tracemalloc
from datetime import datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.directories import get_plots_dir, get_testcases_dir
from src.report import TEMPLATE_DIR

#: Bumped when the shape of benchmark.json changes incompatibly, so a stale
#: file fails loudly instead of rendering a subtly wrong page.
SCHEMA_VERSION = 1

BENCHMARK_FILENAME = "benchmark.json"
REPORT_FILENAME = "index.html"
BENCHMARK_DIRNAME = "benchmark"

#: Order matters: it is the row order in every table and chart, and `mirror`
#: leads because it is the search under test.
VARIANTS = ("mirror", "bidirectional", "unidirectional")

#: The variant the ratio columns are measured against. Bidirectional is the
#: search mirror replaced, so "how much did this save" is the useful question.
BASELINE = "bidirectional"

VARIANT_BLURB = {
    "mirror": "one forward tree; the backward half is that tree relabelled",
    "bidirectional": "forward and backward trees, each to half depth",
    "unidirectional": "one forward tree, expanded the whole way to the goal",
}

#: What the page explains about each search. Written here rather than in the
#: template because it is content about the code, and the template's job is
#: layout — and because the same text then reaches anyone reading the module.
#: `depth` is how far the search expands before it can answer; `trees` is how
#: many state sets it holds at once. Those two numbers are the whole story:
#: everything the benchmark measures follows from them.
VARIANT_DOCS = {
    "unidirectional": {
        "depth": "D",
        "trees": "1",
        "why": (
            "The direct approach: the cheapest solution is the one with the fewest "
            "control switches, so build every position reachable in 0 switches, then "
            "1, then 2, and stop the moment the goal shows up. Because the layers "
            "are built in switch order, the first goal found is the minimum — no "
            "search of alternatives is needed to prove it."
        ),
        "steps": [
            "Layer 0: pick a robot to move first, and flood it from its start "
            "position with the other robot standing still as an obstacle. Every "
            "square it can reach is one state. Do this for both robots, because "
            "either may be the first to move.",
            "Layer k to layer k+1: for every state in layer k, hand control to the "
            "other robot and flood it from where it stands. Every square it reaches "
            "is a new state one switch deeper.",
            "After finishing a layer, check it for the goal — robot A on B's "
            "starting square and B on A's. The first layer that contains it gives "
            "the answer, and no later layer can beat it.",
            "Walk the parent pointers back from that goal state to recover the "
            "move-by-move command string.",
        ],
        "cost": (
            "It has to build every state within D switches of the start. Each layer "
            "is larger than the one before it, so almost all the work is in the last "
            "one — which is why it is the slowest of the three on every case here, "
            "and why the gap widens as the grids grow."
        ),
    },
    "bidirectional": {
        "depth": "D/2",
        "trees": "2",
        "why": (
            "Going the full depth from one end is wasteful, because the layers grow "
            "as you go. Two searches of half the depth — one from each end — cover "
            "the same answer while each stays in the small, early layers. Meeting in "
            "the middle is the entire idea."
        ),
        "steps": [
            "Build the same forward layer 0 from the start, seeding both possible " "first movers.",
            "Build a backward layer 0 at the goal, and expand it with the moves run "
            "in reverse, so it grows towards the start.",
            "Grow whichever of the two frontiers is currently smaller, one layer at "
            "a time, so neither side runs ahead of the other.",
            "After each expansion, check whether any newly reached state is already "
            "in the other side's map. If it is, the two searches have met, and the "
            "answer is the forward depth plus the backward depth.",
            "Stitch the two halves: follow the forward parent pointers into the "
            "meeting state, then the backward pointers out of it with every move "
            "inverted, since that half was walked in reverse.",
        ],
        "cost": (
            "Two half-depth searches are far smaller than one full-depth search, "
            "which is the win over the one-way version. But it holds two trees at "
            "once, and for this problem the second one is a copy of the first with "
            "the robots relabelled — so roughly half the states it stores are states "
            "it already had."
        ),
    },
    "mirror": {
        "depth": "D/2",
        "trees": "1",
        "why": (
            "The backward tree above is not new information. The two robots are "
            "identical squares, and the goal is exactly the start with them swapped. "
            "So take any state and swap the robots — swap their positions and swap "
            "which one holds control. The state you get is as far from the goal as "
            "the original is from the start. Every backward answer is therefore "
            "already sitting in the forward tree under a swapped label, and building "
            "the second tree is doing the same work twice. Build one, and read the "
            "backward distances out of it."
        ),
        "steps": [
            "Build the forward tree exactly as the one-way search does, seeding both "
            "possible first movers in layer 0.",
            "For each state reached, work out its swapped twin — the same picture "
            "with the two robots exchanged — and look that twin up in the map being "
            "filled. It is one piece of arithmetic and one lookup.",
            "If the twin is already there, the two halves have met. This state is h "
            "switches from the start; the twin's recorded depth l says this state is "
            "l switches from the goal. The answer is h + l.",
            "Finish scanning the whole layer before returning, and take the smallest "
            "total found in it. A layer can expose two different totals at once, and "
            "returning the first one seen can report a larger answer than the "
            "smallest available.",
            "Stitch the two halves: the route to this state, then the route to its "
            "twin played backwards with each direction flipped — U for D, L for R. "
            "Commands name no robot, so swapping the robots leaves the string "
            "itself untouched.",
        ],
        "cost": (
            "Same half depth as the bidirectional search, but one tree instead of "
            "two, so it holds the fewest states on every case here. The saving is "
            "structural rather than lucky — the tree it skips is a copy. What it "
            "pays instead is a little arithmetic on every state to find the twin, "
            "which on the small cases costs more than the states it saves; that is "
            "why it can lose on the clock there while still winning on states. Peak "
            "RAM moves far less than the state count, because most of that memory "
            "is the flood cache all three searches share."
        ),
    },
}

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── test-case loading ───────────────────────────────────────────────────


def _ensure_paths() -> str:
    """Put the repo root and testcases/ on sys.path; return the latter.

    A measurement runs in a spawned process, which starts from a bare import
    and inherits none of the parent's sys.path edits, so this has to run there
    as well as here.
    """
    testcases_dir = get_testcases_dir()
    for path in (_REPO_ROOT, testcases_dir):
        if path not in sys.path:
            sys.path.insert(0, path)
    return testcases_dir


def _case_classes():
    """Every TestCase subclass under testcases/, sorted by class name.

    Discovery is duplicated from run_tests.py rather than imported: that module
    is a ``__main__`` script whose import edits sys.path as a side effect, and
    importing a script from a library module inverts the dependency.
    """
    from src.test_case import TestCase

    testcases_dir = _ensure_paths()
    found = []
    for fname in sorted(os.listdir(testcases_dir)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        module = __import__(fname[:-3])
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, TestCase) and obj is not TestCase:
                found.append(obj)
    return sorted(set(found), key=lambda c: c.__name__)


def discover_cases(name_filter: str | None = None) -> list[tuple[str, str]]:
    """(class name, display name) for every test case, optionally filtered by
    a case-insensitive substring of the display name."""
    cases = [(cls.__name__, cls().name) for cls in _case_classes()]
    if name_filter:
        needle = name_filter.lower()
        cases = [c for c in cases if needle in c[1].lower()]
    return cases


def _load_case(cls_name: str):
    """Instantiate one test case by class name, in whichever process asks."""
    for cls in _case_classes():
        if cls.__name__ == cls_name:
            return cls()
    raise LookupError(f"no test case class named {cls_name!r}")


# ── measurement ─────────────────────────────────────────────────────────


def _solve(variant: str, ws, goal_a, goal_b):
    """Run one search by name. Imported inside so a spawned worker pays the
    import once, in the child, rather than through the pickled payload."""
    from src.bfs import bfs, bfs_bidirectional, bfs_mirror

    if variant == "mirror":
        return bfs_mirror(ws, goal_a, goal_b)
    if variant == "bidirectional":
        return bfs_bidirectional(ws, goal_a, goal_b)
    if variant == "unidirectional":
        return bfs(ws, goal_a, goal_b)
    raise ValueError(f"unknown variant {variant!r}")


def _measure_worker(payload, out_q) -> None:
    """Child-process entry point: measure one (test case, variant) pair.

    Puts exactly one record on `out_q`. Every failure is reported as a record
    too — a worker that raised without answering would be indistinguishable
    from one that hung.
    """
    cls_name, variant, repeat = payload
    record: dict = {"variant": variant, "status": "error", "error": None}
    try:
        tc = _load_case(cls_name)
        ws, goal_a, goal_b = tc.setup()

        # Cold: fresh process, so the flood caches are empty and tracemalloc
        # sees this search's allocations and nothing else.
        tracemalloc.start()
        try:
            started = time.perf_counter()
            out = _solve(variant, ws, goal_a, goal_b)
            cold = time.perf_counter() - started
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        if out is None:
            record.update(status="unsolvable", cold_seconds=cold, peak_bytes=peak)
            out_q.put(record)
            return

        # Warm: the caches are now primed, so what is left is the BFS's own
        # bookkeeping — which is where the searches actually differ, since all
        # three share the same flood fills.
        warm = []
        for _ in range(max(1, repeat)):
            started = time.perf_counter()
            _solve(variant, ws, goal_a, goal_b)
            warm.append(time.perf_counter() - started)

        # The validator walks the path and mutates the robots, so it gets its
        # own workspace. Checking the path matters more than checking the
        # count: a wrong count is a number, a wrong path is a wrong answer.
        #
        # Control at step 0 comes from the search, not from the workspace's
        # default: commands name no robot, so replaying a path that opens with
        # a switch under the wrong controller fails on a path that is correct.
        from src.validator import Validator

        ws2, goal_a2, goal_b2 = tc.setup()
        mover = out.get("initial_mover")
        first_mover = mover.label if mover is not None else None
        if first_mover is not None:
            ws2._control = ws2.robot_a if first_mover == ws2.robot_a.label else ws2.robot_b
        vr = Validator(ws2, goal_a2, goal_b2).run(out["path"], plot=False)

        record.update(
            status="ok",
            error=None,
            switches=out["switches"],
            first_mover=first_mover,
            steps=len(out["path"]),
            states=len(out["visited"]),
            valid=bool(vr.valid),
            invalid_reason=None if vr.valid else str(vr.failed_reason),
            cold_seconds=cold,
            warm_min=min(warm),
            warm_median=statistics.median(warm),
            peak_bytes=peak,
        )
    except Exception as exc:  # noqa: BLE001 — reported, not swallowed
        record["error"] = f"{type(exc).__name__}: {exc}"
    out_q.put(record)


def _blank_record(variant: str, status: str, error: str | None = None) -> dict:
    return {"variant": variant, "status": status, "error": error}


def measure(cls_name: str, variant: str, repeat: int, timeout: float) -> dict:
    """Measure one (test case, variant) pair in a spawned process.

    Returns the worker's record, or a `timeout` / `crashed` record. The
    unidirectional search expands to depth D rather than D/2, so on the larger
    cases it can run for a very long time; the timeout is what lets it sit in
    the default variant set without risking a stalled run.
    """
    ctx = mp.get_context("spawn")
    out_q = ctx.Queue()
    proc = ctx.Process(target=_measure_worker, args=((cls_name, variant, repeat), out_q))
    proc.start()
    try:
        record = out_q.get(timeout=timeout)
    except queue.Empty:
        # Nothing arrived. A live process overran the budget; a dead one died
        # without answering (most likely the OS reclaiming it under memory
        # pressure), and the two want different labels.
        record = _blank_record(variant, "timeout" if proc.is_alive() else "crashed")
    finally:
        if proc.is_alive():
            proc.terminate()
        proc.join(5)
    return record


def run_benchmark(cases, variants, repeat: int, timeout: float, progress=None) -> dict:
    """Measure every (case, variant) pair and assemble the benchmark record.

    `cases` is the (class name, display name) list from `discover_cases`.
    `progress` is called with one status line per measurement.
    """
    entries = []
    for cls_name, display in cases:
        tc = _load_case(cls_name)
        ws, _, _ = tc.setup()
        entry = {
            "name": display,
            "rows": ws.grid.rows,
            "cols": ws.grid.cols,
            "n": ws.robot_a.n,
            "variants": [],
        }
        for variant in variants:
            record = measure(cls_name, variant, repeat, timeout)
            entry["variants"].append(record)
            if progress:
                progress(_progress_line(display, record))
        entries.append(_annotate_case(entry))

    return {
        "schema": SCHEMA_VERSION,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repeat": repeat,
        "timeout": timeout,
        "variants": list(variants),
        "baseline": BASELINE,
        "cases": entries,
        "summary": _summarise(entries, variants),
    }


def _progress_line(display: str, record: dict) -> str:
    variant = record["variant"]
    if record["status"] != "ok":
        detail = record.get("error") or record["status"]
        return f"  {display:<22} {variant:<15} {record['status'].upper()}: {detail}"
    flag = "" if record["valid"] else "  PATH INVALID"
    return (
        f"  {display:<22} {variant:<15} "
        f"turns={record['switches'] + 1:<4} states={record['states']:<9,} "
        f"time={fmt_seconds(record['warm_min']):>9} "
        f"ram={fmt_bytes(record['peak_bytes']):>9}{flag}"
    )


# ── derived numbers ─────────────────────────────────────────────────────


def _annotate_case(entry: dict) -> dict:
    """Add per-case agreement flags and ratios against the baseline variant."""
    ok = [r for r in entry["variants"] if r["status"] == "ok"]
    counts = {r["switches"] for r in ok}
    entry["switches"] = next(iter(counts)) if len(counts) == 1 else None
    entry["agree"] = len(counts) <= 1
    entry["all_valid"] = all(r["valid"] for r in ok)
    entry["healthy"] = entry["agree"] and entry["all_valid"] and len(ok) == len(entry["variants"])

    base = next((r for r in ok if r["variant"] == BASELINE), None)
    for metric in ("states", "warm_min", "peak_bytes"):
        values = [r[metric] for r in ok if r.get(metric)]
        # Which search won this metric on this case. Marked in the table so the
        # comparison can be read down a column instead of by mental arithmetic.
        best = min(values) if values else None
        for record in entry["variants"]:
            ratio = None
            if base and record["status"] == "ok":
                divisor = base.get(metric)
                if divisor:
                    ratio = record[metric] / divisor
            record[f"{metric}_ratio"] = ratio
            record[f"{metric}_best"] = (
                best is not None and record["status"] == "ok" and record.get(metric) == best
            )
    return entry


def _summarise(entries, variants) -> list[dict]:
    """One row per search, over the cases both it and the baseline solved.

    States and time are summed, because a total of those means something: the
    states are all built, the seconds are all spent. **Peak memory is not
    summed.** Each case runs in its own process and peaks at its own moment, so
    adding those peaks describes a run that never happened — the headline figure
    would be several times the largest amount of memory ever actually held. It
    is reported as the worst case instead.

    Ratios follow the same logic: a ratio of sums for the two that are summed,
    and the mean of the per-case ratios for peak memory, so every case counts
    once instead of the largest grid deciding the number on its own.
    """
    metrics = ("states", "warm_min", "peak_bytes")
    rows = []
    for variant in variants:
        totals = dict.fromkeys(metrics, 0)
        base_totals = dict.fromkeys(metrics, 0)
        # Per-case ratios kept alongside the totals: a ratio of totals answers
        # "over the whole suite", which the largest grid decides almost by
        # itself, while the average of the per-case ratios answers "on a typical
        # case", where every case counts once. They are different questions and
        # the page asks both.
        #
        # Averaged geometrically, not arithmetically. A ratio's natural centre is
        # multiplicative: +100% and -50% are opposite results and must cancel to
        # ±0%, which the arithmetic mean puts at +25%. Averaging ratios the
        # ordinary way biases every comparison towards "worse".
        per_case = {metric: [] for metric in metrics}
        wins = dict.fromkeys(metrics, 0)
        peak_worst = 0
        solved = 0
        failed = 0
        for entry in entries:
            record = next((r for r in entry["variants"] if r["variant"] == variant), None)
            base = next(
                (r for r in entry["variants"] if r["variant"] == BASELINE and r["status"] == "ok"),
                None,
            )
            if record is None:
                continue
            if record["status"] != "ok":
                failed += 1
                continue
            solved += 1
            peak_worst = max(peak_worst, record["peak_bytes"])
            if base is None:
                continue
            for metric in metrics:
                totals[metric] += record[metric]
                base_totals[metric] += base[metric]
                if base[metric]:
                    per_case[metric].append(record[metric] / base[metric])
                if record.get(f"{metric}_best"):
                    wins[metric] += 1
        row = {
            "variant": variant,
            "blurb": VARIANT_BLURB.get(variant, ""),
            "solved": solved,
            "failed": failed,
            "states": totals["states"],
            "warm_min": totals["warm_min"],
            # Worst single case, never a sum -- see the docstring.
            "peak_bytes": peak_worst,
        }
        for metric in metrics:
            row[f"{metric}_ratio"] = (
                totals[metric] / base_totals[metric] if base_totals[metric] else None
            )
            row[f"{metric}_ratio_avg"] = (
                statistics.geometric_mean(per_case[metric]) if per_case[metric] else None
            )
            row[f"{metric}_wins"] = wins[metric]
        row["cases_compared"] = len(per_case["states"])
        # Peak memory has no meaningful total, so its headline ratio is the
        # per-case average rather than a ratio of sums.
        row["peak_bytes_ratio"] = row["peak_bytes_ratio_avg"]
        rows.append(row)
    return rows


# ── formatting ──────────────────────────────────────────────────────────


def fmt_seconds(value) -> str:
    """Elapsed seconds with an explicit unit — the same convention run_tests
    prints, so the two outputs read alike."""
    if value is None:
        return "—"
    if value < 1e-3:
        return f"{value * 1e6:.1f}us"
    if value < 1:
        return f"{value * 1e3:.1f}ms"
    return f"{value:.2f}s"


def fmt_bytes(value) -> str:
    if value is None:
        return "—"
    if value < 1024:
        return f"{value}B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f}KB"
    return f"{value / (1024 * 1024):.1f}MB"


def fmt_num(value) -> str:
    return "—" if value is None else f"{value:,}"


def fmt_change(ratio) -> str:
    """A ratio against the reference as a signed percent change: ``-43%`` is
    43% less than the reference, ``+35%`` is 35% more, ``±0%`` is unchanged.

    The one convention every page uses for every measurement -- walls, time,
    states, RAM -- so that negative always reads as better and the same number
    never appears as ``0.57x`` in one place and ``-43%`` in another.
    """
    if ratio is None:
        return "—"
    pct = (ratio - 1.0) * 100.0
    if abs(pct) < 0.5:
        return "±0%"
    return f"{'−' if pct < 0 else '+'}{abs(pct):.0f}%"


# ── charts ──────────────────────────────────────────────────────────────
#
# Geometry is computed here rather than in the template so the markup stays
# declarative, and as static SVG rather than JS-drawn so the page prints and
# screenshots the same way it renders.
#
# Every chart uses ONE axis shared by all cases, with gridlines and tick labels,
# so bars are comparable across the whole page rather than only within a case.
# The per-case measurements span four orders of magnitude between a 1x1 grid and
# a 4x4 with holes, so those axes are logarithmic — on a linear axis every small
# case collapses to an invisible sliver and the chart says nothing. The headline
# chart is a ratio against the baseline and stays linear, because ratios are
# what "which is best" actually asks and they all sit near 1.

_CHART_W = 820
_LABEL_W = 150
_RIGHT_PAD = 92
_BAR_W = _CHART_W - _LABEL_W - _RIGHT_PAD
_ROW_H = 16
_ROW_GAP = 2
_HEADING_H = 20
_GROUP_GAP = 10
_AXIS_H = 24

#: Fixed hues, not theme variables: a chart that inverts with the page cannot
#: be compared with one screenshotted from the other theme — the same reason
#: the index chart keeps a light face.
VARIANT_COLORS = {
    "mirror": "#2f6fd0",
    "bidirectional": "#d9822b",
    "unidirectional": "#8a8f98",
}


def _render(title: str, subtitle: str, axis_label: str, groups, gridlines, scale) -> dict:
    """Lay out one grouped horizontal bar chart.

    `groups` is [(group name, [(variant, value, label)])]; `scale` maps a value
    to a bar width in pixels; `gridlines` is [(value, tick label)] on the same
    scale. Rows are placed here so the template only has to emit rectangles.
    """
    laid_out = []
    y = _AXIS_H
    for name, bars_in in groups:
        heading_y = y + _HEADING_H - 6
        y += _HEADING_H
        bars = []
        for variant, value, label in bars_in:
            # 2px floor so a real-but-tiny bar still reads as a bar; a missing
            # measurement draws nothing at all, so the two cannot be confused.
            width = 0.0 if value is None else max(2.0, scale(value))
            bars.append(
                {
                    "variant": variant,
                    "y": y,
                    "width": round(width, 1),
                    "fill": VARIANT_COLORS.get(variant, "#8a8f98"),
                    "label": label,
                    "missing": value is None,
                }
            )
            y += _ROW_H + _ROW_GAP
        laid_out.append({"name": name, "heading_y": heading_y, "bars": bars})
        y += _GROUP_GAP

    height = y + _AXIS_H
    return {
        "title": title,
        "subtitle": subtitle,
        "axis_label": axis_label,
        "groups": laid_out,
        "grid": [
            {"x": round(_LABEL_W + scale(value), 1), "label": label} for value, label in gridlines
        ],
        "width": _CHART_W,
        "height": height,
        "plot_top": _AXIS_H - 6,
        "plot_bottom": height - _AXIS_H + 6,
        # Tick labels on both edges: these charts run several hundred pixels
        # tall, and a scale printed only at the bottom is unreadable against the
        # groups at the top.
        "axis_y_top": _AXIS_H - 12,
        "axis_y": height - _AXIS_H + 18,
        "bar_x": _LABEL_W,
        "bar_h": _ROW_H - 3,
        "text_dy": _ROW_H - 4,
    }


def _log_scale(values):
    """A log10 scale over `values`, snapped out to whole decades.

    Returns (scale, gridlines). Log because the cases span four orders of
    magnitude — a 1x1 grid against a 4x4 with holes — and on a linear axis every
    small case would be an invisible sliver against the largest one.
    """
    usable = [v for v in values if v and v > 0]
    lo = min(usable) if usable else 1.0
    hi = max(usable) if usable else 10.0
    start = math.floor(math.log10(lo))
    end = math.ceil(math.log10(hi))
    if end <= start:
        end = start + 1
    span = end - start

    def scale(value):
        if not value or value <= 0:
            return 0.0
        return (math.log10(value) - start) / span * _BAR_W

    return scale, [10.0**exp for exp in range(start, end + 1)]


def _case_chart(data, metric, title, subtitle, axis_label, fmt) -> dict:
    """One group per test case, one bar per search, on a shared log axis."""
    entries, variants = data["cases"], data["variants"]
    values = [
        r[metric]
        for entry in entries
        for r in entry["variants"]
        if r["status"] == "ok" and r.get(metric)
    ]
    scale, ticks = _log_scale(values)

    groups = []
    for entry in entries:
        bars = []
        for variant in variants:
            record = next((r for r in entry["variants"] if r["variant"] == variant), None)
            usable = record and record["status"] == "ok" and record.get(metric)
            value = record[metric] if usable else None
            label = fmt(value) if usable else (record["status"] if record else "—")
            bars.append((variant, value, label))
        groups.append((entry["name"], bars))

    return _render(title, subtitle, axis_label, groups, [(t, fmt(t)) for t in ticks], scale)


def _headline_chart(data) -> dict:
    """The one chart that answers "which is best, and by how much".

    Uses the mean of the per-case ratios rather than a ratio of totals: the
    question is how much each search saves on a typical case, and a ratio of
    totals is decided almost entirely by the largest grid in the set.
    """
    summary = {row["variant"]: row for row in data["summary"]}
    metrics = [
        ("states_ratio_avg", "Memory — states held"),
        ("warm_min_ratio_avg", "Execution time"),
        ("peak_bytes_ratio_avg", "Memory — peak RAM"),
    ]
    ratios = [
        summary[v][key]
        for key, _label in metrics
        for v in data["variants"]
        if summary.get(v) and summary[v].get(key)
    ]
    hi = max(ratios + [1.0]) if ratios else 1.0
    hi = math.ceil(hi * 4) / 4  # round up to a quarter, so the axis ends tidily

    def scale(value):
        return (value / hi) * _BAR_W if hi else 0.0

    step = 0.25 if hi <= 2 else 0.5
    ticks = []
    tick = 0.0
    while tick <= hi + 1e-9:
        ticks.append((tick, fmt_change(tick)))
        tick += step

    groups = []
    for key, label in metrics:
        bars = []
        for variant in data["variants"]:
            row = summary.get(variant)
            value = row.get(key) if row else None
            bars.append((variant, value, fmt_change(value)))
        groups.append((label, bars))

    return _render(
        f"Head to head — average per case, against {BASELINE}",
        f"How much each search saves on a typical case: the mean of its per-case "
        f"change against {BASELINE}, over the cases both solved. Negative is "
        f"better; {BASELINE} is ±0% by definition.",
        f"change vs {BASELINE} (±0% = same)",
        groups,
        ticks,
        scale,
    )


def build_charts(data: dict) -> list[dict]:
    """Headline first — which search wins and by how much — then the per-case
    detail behind it: what each search stores, what it costs in time, what it
    costs in memory."""
    return [
        _headline_chart(data),
        _case_chart(
            data,
            "states",
            "States held, per case",
            "Entries in the search's visited map. This is the structural "
            "difference and it is exact: the same numbers on every machine and "
            "every run.",
            "states (log scale)",
            fmt_num,
        ),
        _case_chart(
            data,
            "warm_min",
            "Solve time, per case",
            "Fastest of the timed repeats, with the flood caches already primed "
            "— which isolates each search's own bookkeeping from the flood fills "
            "all three share.",
            "seconds (log scale)",
            fmt_seconds,
        ),
        _case_chart(
            data,
            "peak_bytes",
            "Peak memory, per case",
            "Most memory held at once during the first solve, measured in a "
            "fresh process with empty caches.",
            "bytes (log scale)",
            fmt_bytes,
        ),
    ]


# ── output ──────────────────────────────────────────────────────────────


def benchmark_dir() -> str:
    return os.path.join(get_plots_dir(), BENCHMARK_DIRNAME)


def write_benchmark(data: dict, out_dir: str | None = None) -> str:
    """Write benchmark.json — the record everything else derives from."""
    out_dir = out_dir or benchmark_dir()
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, BENCHMARK_FILENAME)
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, sort_keys=False)
    return dest


def write_benchmark_report(data: dict, out_dir: str | None = None) -> str:
    """Render benchmark.json into a self-contained index.html."""
    out_dir = out_dir or benchmark_dir()
    os.makedirs(out_dir, exist_ok=True)
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(default_for_string=True, default=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # `num`, not `count`: Jinja already defines a `count` filter (an alias for
    # `length`), and shadowing a builtin in a template is a trap for the next
    # person editing it.
    env.filters["seconds"] = fmt_seconds
    env.filters["bytes"] = fmt_bytes
    env.filters["num"] = fmt_num
    env.filters["change"] = fmt_change
    page = env.get_template("benchmark.html.j2").render(
        data=data,
        charts=build_charts(data),
        colors=VARIANT_COLORS,
        blurbs=VARIANT_BLURB,
        docs=VARIANT_DOCS,
        baseline=BASELINE,
        healthy=all(c["healthy"] for c in data["cases"]) if data["cases"] else False,
    )
    dest = os.path.join(out_dir, REPORT_FILENAME)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(page)
    return dest
