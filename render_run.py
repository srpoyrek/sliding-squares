"""
render_run.py
-------------
Render a `run.json` to PNGs, offline and on demand.

`run_tests.py` no longer writes per-switch images: the HTML report covers the
same ground without paying matplotlib's per-frame cost, which dominates a run.
This script is the escape hatch for when raster really is wanted — figures for
the paper, a diff against an older image set, anything outside a browser.

It writes into `<run-dir>/png_from_json/`, a folder of its own, so an existing
`switch_NN.png` set stays untouched and can be compared side by side.

Usage::

    python render_run.py plots/tests/3x3_robot_holes/run.json
    python render_run.py plots/tests/3x3_robot_holes/run.json --chart-only
    python render_run.py plots/tests/*/run.json --out-dir figures/

Outputs:
    png_from_json/switch_NN.png   one image per switch
    png_from_json/transitions.png the whole sequence as a single chart
"""

from __future__ import annotations

import argparse
import math
import os
import sys

from src.report import load_run

# Imported, not re-declared: visualizer.py holds the one definition of the board
# palette, and the HTML report reads the same constants. A colour changed there
# moves the page and every PNG together.
from src.visualizer import (
    COLOR_ARROW_A as COLOR_A_ARROW,
)
from src.visualizer import (
    COLOR_ARROW_B as COLOR_B_ARROW,
)
from src.visualizer import (
    COLOR_FREE,
)
from src.visualizer import (
    COLOR_GRID_LINE as COLOR_LINE,
)
from src.visualizer import (
    COLOR_OBSTACLE as COLOR_WALL,
)
from src.visualizer import (
    COLOR_ROBOT_A as COLOR_A,
)
from src.visualizer import (
    COLOR_ROBOT_B as COLOR_B,
)


def _walls(run: dict) -> list[list[int]]:
    """The wall bitstring back into rows of 0/1."""
    g = run["grid"]
    bits, cols = g["walls"], g["cols"]
    return [[int(bits[r * cols + c]) for c in range(cols)] for r in range(g["rows"])]


def _draw(ax, grid_rows, run, a, b, title, arrow=None):
    """One board on an axis: walls, both robots, and the move that got here."""
    import matplotlib.patches as patches

    rows, cols = len(grid_rows), len(grid_rows[0])
    n = run["meta"]["n"]
    labels = run["labels"]
    ax.set_aspect("equal")
    ax.set_xlim(0, cols)
    ax.set_ylim(0, rows)
    ax.invert_yaxis()
    ax.axis("off")
    ax.set_title(title, fontsize=9, fontweight="bold", pad=4)

    for r in range(rows):
        for c in range(cols):
            ax.add_patch(
                patches.Rectangle(
                    (c, r),
                    1,
                    1,
                    linewidth=0.5,
                    edgecolor=COLOR_LINE,
                    facecolor=COLOR_WALL if grid_rows[r][c] else COLOR_FREE,
                )
            )

    for pos, color, label in ((a, COLOR_A, labels["a"]), (b, COLOR_B, labels["b"])):
        if pos is None:
            continue
        ax.add_patch(
            patches.Rectangle(
                (pos[1], pos[0]),
                n,
                n,
                linewidth=1.5,
                edgecolor="white",
                facecolor=color,
                alpha=0.85,
                zorder=3,
            )
        )
        ax.text(
            pos[1] + n / 2,
            pos[0] + n / 2,
            label,
            ha="center",
            va="center",
            fontsize=8 * n,
            fontweight="bold",
            color="white",
            zorder=4,
        )

    if arrow:
        (fr, fc), (tr, tc), color = arrow
        if (fr, fc) != (tr, tc):
            ax.annotate(
                "",
                xy=(tc + n / 2, tr + n / 2),
                xytext=(fc + n / 2, fr + n / 2),
                arrowprops={"arrowstyle": "->", "color": color, "lw": 2},
                zorder=5,
            )


def _turn_positions(run: dict, turn: dict):
    """(a, b, arrow) for a turn, resolving which robot actually moved."""
    is_a = turn["label"] == run["labels"]["a"]
    moving_to, still = turn["to"], turn["stationary"]
    a, b = (moving_to, still) if is_a else (still, moving_to)
    # The arrow colour is the dedicated per-robot arrow shade, not the robot's
    # own fill -- same distinction visualizer.py draws.
    arrow = (tuple(turn["from"]), tuple(turn["to"]), COLOR_A_ARROW if is_a else COLOR_B_ARROW)
    return a, b, arrow


def render(run_path: str, out_dir: str | None = None, chart_only: bool = False) -> str:
    """Render one run.json. Returns the directory written to."""
    import matplotlib

    matplotlib.use("Agg")  # no display needed; this is a batch renderer
    import matplotlib.pyplot as plt

    run = load_run(run_path)
    dest = out_dir or os.path.join(os.path.dirname(run_path), "png_from_json")
    os.makedirs(dest, exist_ok=True)

    grid_rows = _walls(run)
    rows, cols = len(grid_rows), len(grid_rows[0])
    turns = run["turns"]

    if not chart_only:
        start = run["start"]
        fig, ax = plt.subplots(figsize=(cols * 0.7 + 0.5, rows * 0.7 + 0.5))
        _draw(ax, grid_rows, run, start["a"], start["b"], "start")
        fig.tight_layout()
        fig.savefig(os.path.join(dest, "start.png"), dpi=150, bbox_inches="tight")
        plt.close(fig)

        for turn in turns:
            a, b, arrow = _turn_positions(run, turn)
            fig, ax = plt.subplots(figsize=(cols * 0.7 + 0.5, rows * 0.7 + 0.5))
            _draw(ax, grid_rows, run, a, b, f"switch {turn['layer']:02d}: {turn['label']}", arrow)
            fig.tight_layout()
            fig.savefig(
                os.path.join(dest, f"switch_{turn['layer']:02d}.png"),
                dpi=150,
                bbox_inches="tight",
            )
            plt.close(fig)

    # The whole sequence on one canvas: start plus every switch, in reading
    # order, so a run can be taken in without stepping through files.
    panels = 1 + len(turns)
    n_cols = min(panels, 5)
    n_rows = math.ceil(panels / n_cols)
    fig, axes = plt.subplots(
        n_rows,
        n_cols,
        figsize=(n_cols * (cols * 0.45 + 0.4), n_rows * (rows * 0.45 + 0.5)),
        squeeze=False,
    )
    start = run["start"]
    _draw(axes[0][0], grid_rows, run, start["a"], start["b"], "start")
    for idx, turn in enumerate(turns, start=1):
        a, b, arrow = _turn_positions(run, turn)
        _draw(
            axes[idx // n_cols][idx % n_cols],
            grid_rows,
            run,
            a,
            b,
            f"switch {turn['layer']:02d}: {turn['label']}",
            arrow,
        )
    for idx in range(panels, n_rows * n_cols):
        axes[idx // n_cols][idx % n_cols].set_visible(False)

    meta = run["meta"]
    fig.suptitle(
        f"{meta['name']} — {meta['switches']} switches, {rows}x{cols} grid, "
        f"{meta['n']}x{meta['n']} robots",
        fontsize=11,
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(os.path.join(dest, "transitions.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    return dest


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[3])
    parser.add_argument("runs", nargs="+", help="one or more run.json paths")
    parser.add_argument("--out-dir", default=None, help="write here instead of png_from_json/")
    parser.add_argument(
        "--chart-only",
        action="store_true",
        help="only the combined transitions.png, skipping the per-switch images",
    )
    args = parser.parse_args(argv)

    failed = 0
    for run_path in args.runs:
        try:
            dest = render(run_path, args.out_dir, args.chart_only)
        except (OSError, ValueError, KeyError) as exc:
            print(f"{run_path}: {type(exc).__name__}: {exc}", file=sys.stderr)
            failed += 1
            continue
        print(f"{run_path} -> {dest}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
