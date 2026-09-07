"""
benchmark_bfs.py
----------------
Compare the three BFS searches in `src/bfs.py` on every test case, and publish
the comparison as `plots/benchmark/index.html`.

    unidirectional   one forward tree, expanded all the way to depth D
    bidirectional    a forward and a backward tree, each to depth D/2
    mirror           one forward tree to depth D/2; the backward half is that
                     same tree read through the A<->B relabelling

All three are exact, so their switch counts must agree and every path they
return must validate. The run therefore doubles as a correctness check on the
searches, and says so at the top of the page: a disagreement is a defect, and
no timing below it is worth reading until it is fixed.

Usage::

    python benchmark_bfs.py                       # every case, every search
    python benchmark_bfs.py 3x3                   # only cases matching "3x3"
    python benchmark_bfs.py --variants mirror,bidirectional
    python benchmark_bfs.py --repeat 5 --timeout 300

Each measurement runs in its own spawned process, so the flood caches start
empty, the peak allocation is that search alone, and a search that runs away is
killed on the timeout instead of stalling the comparison.
"""

from __future__ import annotations

import argparse
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.benchmark import (  # noqa: E402 — needs BASE_DIR on the path first
    BASELINE,
    VARIANTS,
    discover_cases,
    fmt_ratio,
    run_benchmark,
    write_benchmark,
    write_benchmark_report,
)
from src.directories import get_plots_dir  # noqa: E402
from src.report import write_site_index  # noqa: E402


def _rel(path: str) -> str:
    """Repo-relative path when the file is inside the repo, else absolute."""
    try:
        return os.path.relpath(path, BASE_DIR)
    except ValueError:
        return path


def _print_summary(data: dict) -> None:
    print("\n" + "=" * 72)
    healthy = all(case["healthy"] for case in data["cases"]) if data["cases"] else False
    if healthy:
        print("AGREE: every search returned the same switch count, every path validated.")
    else:
        print("DISAGREE: a search returned a different count, an invalid path, or no result.")
        for case in data["cases"]:
            if case["healthy"]:
                continue
            counts = {
                r["variant"]: r.get("switches") if r["status"] == "ok" else r["status"]
                for r in case["variants"]
            }
            print(f"  {case['name']}: {counts}")

    print(f"\nTotals across cases each search and {BASELINE} both solved.")
    print(f"Ratios are that search divided by {BASELINE} — lower is better.")
    for row in data["summary"]:
        print(
            f"  {row['variant']:<15} solved={row['solved']:<3} failed={row['failed']:<3} "
            f"states={row['states']:>12,} ({fmt_ratio(row['states_ratio'])})  "
            f"time={row['warm_min']:.3f}s ({fmt_ratio(row['warm_min_ratio'])})  "
            f"ram={row['peak_bytes'] / (1024 * 1024):>7.1f}MB "
            f"({fmt_ratio(row['peak_bytes_ratio'])})"
        )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Compare the BFS searches across the test cases and publish the result."
    )
    parser.add_argument(
        "name",
        nargs="?",
        help="Substring filter — only benchmark cases whose name contains this.",
    )
    parser.add_argument(
        "--variants",
        default=",".join(VARIANTS),
        help="Comma-separated searches to compare, in table order. "
        f"Available: {', '.join(VARIANTS)}. Default: all of them.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=3,
        help="Warm repeats timed after the cold solve; the minimum and median "
        "of these are reported. Default 3.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Seconds allowed per case+search before the measurement is killed "
        "and recorded as a timeout. The unidirectional search expands to depth "
        "D rather than D/2, so on the larger cases it is the one that needs "
        "this. Default 120.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Directory to write benchmark.json and index.html into "
        "(default: plots/benchmark/).",
    )
    args = parser.parse_args(argv)

    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    unknown = [v for v in variants if v not in VARIANTS]
    if unknown:
        print(f"Unknown search(es): {', '.join(unknown)}")
        print(f"Available: {', '.join(VARIANTS)}")
        return 1
    if not variants:
        print("No searches selected.")
        return 1

    cases = discover_cases(args.name)
    if not cases:
        print(f"No test case matching '{args.name}'" if args.name else "No test cases found.")
        return 1

    print(f"{len(cases)} case(s) x {len(variants)} search(es)")
    print("  turns  = minimum control turns to swap the robots (all searches must agree)")
    print("  states = states held in the search's visited map (exact, machine-independent)")
    print(f"  time   = one solve, fastest of {args.repeat}, flood caches already warm")
    print("  ram    = most memory held at once during one solve, flood caches cold")
    print("=" * 72)
    data = run_benchmark(cases, variants, args.repeat, args.timeout, progress=print)

    _print_summary(data)

    record = write_benchmark(data, args.out)
    page = write_benchmark_report(data, args.out)
    print(f"\nRecord: {_rel(record)}")
    print(f"Open:   {_rel(page)}")

    if not args.out:
        # The landing page links this comparison only when the page exists, so
        # refresh it here: otherwise the card is missing whenever the benchmark
        # was built after make_gallery.py rather than before it. A custom --out
        # is not the site layout, so there is nothing to link.
        print(f"Linked: {_rel(write_site_index(get_plots_dir()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
