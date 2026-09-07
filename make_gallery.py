"""
make_gallery.py
---------------
Render every simplification recipe against every fixture, as one page.

The recipe docs say what each pass is meant to do; this shows it. For each
layout in `tests/fixtures.py` the page puts the original beside the result of
every recipe, colouring each original wall by what happened to it — kept,
removed, or cropped away — so the transform is visible in place rather than
inferred from two separate pictures.

It drives `simplify_workspace` directly with the fixture's own contact counts,
so a case needs only to be a *shape*, not a solvable puzzle. That keeps the
cases small enough to reason about by hand, which is what makes the matching
assertions in `tests/test_simplify.py` worth anything.

Usage::

    python make_gallery.py                 # -> plots/gallery/index.html
    python make_gallery.py --out somewhere/
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from src.directories import get_plots_dir
from src.report import TEMPLATE_DIR, palette
from src.simplify import RECIPES, simplify_workspace
from tests.fixtures import CASES

CELL = 26


def _diff_svg(before, after, crop, cell=CELL) -> tuple[str, dict]:
    """The original grid with every wall classified against a result.

    Drawn on the ORIGINAL geometry, because that is the only way to show what a
    recipe took: a cropped result has different dimensions, and `crop` is the
    (top, left) offset that maps one onto the other.
    """
    top, left = crop
    rows, cols = len(before), len(before[0])
    a_rows, a_cols = len(after), len(after[0]) if after else 0
    counts = {"kept": 0, "removed": 0, "cropped": 0}
    parts = [
        f'<svg viewBox="0 0 {cols * cell} {rows * cell}" '
        f'width="{cols * cell}" height="{rows * cell}" role="img">'
    ]
    for r in range(rows):
        for c in range(cols):
            fill = "var(--free)"
            if before[r][c] != 0:
                ar, ac = r - top, c - left
                if not (0 <= ar < a_rows and 0 <= ac < a_cols):
                    fill, key = "var(--cropped)", "cropped"
                elif after[ar][ac] != 0:
                    fill, key = "var(--wall)", "kept"
                else:
                    fill, key = "var(--removed)", "removed"
                counts[key] += 1
            parts.append(
                f'<rect x="{c * cell}" y="{r * cell}" width="{cell}" height="{cell}" '
                f'fill="{fill}" stroke="var(--grid)" stroke-width=".5"/>'
            )
    parts.append("</svg>")
    return "".join(parts), counts


def _plain_svg(tiles, cell=CELL) -> str:
    """A grid with no annotation — the 'before' picture."""
    rows, cols = len(tiles), len(tiles[0])
    parts = [
        f'<svg viewBox="0 0 {cols * cell} {rows * cell}" '
        f'width="{cols * cell}" height="{rows * cell}" role="img">'
    ]
    for r in range(rows):
        for c in range(cols):
            fill = "var(--wall)" if tiles[r][c] else "var(--free)"
            parts.append(
                f'<rect x="{c * cell}" y="{r * cell}" width="{cell}" height="{cell}" '
                f'fill="{fill}" stroke="var(--grid)" stroke-width=".5"/>'
            )
    parts.append("</svg>")
    return "".join(parts)


def build_case(case) -> dict:
    """One fixture through every recipe."""
    before = case.tiles
    results = []
    for mode, recipe in RECIPES.items():
        ws = case.workspace()
        simplified, _black, _orange, _uncross, crop = simplify_workspace(
            ws,
            case.counts(),
            face_counts=case.face_contacts,
            **recipe["kwargs"],
        )
        after = simplified.grid.tiles
        svg, counts = _diff_svg(before, after, crop)
        results.append(
            {
                "mode": mode,
                "svg": svg,
                "walls_after": counts["kept"],
                "removed": counts["removed"],
                "cropped": counts["cropped"],
            }
        )
    return {
        "name": case.name,
        "n": case.n,
        "why": case.why,
        "walls_before": sum(cell != 0 for row in before for cell in row),
        "original_svg": _plain_svg(before),
        "results": results,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[3])
    parser.add_argument(
        "--out",
        default=None,
        help="directory to write index.html into (default: plots/gallery/)",
    )
    args = parser.parse_args(argv)

    # Imported here so the module can be read without Jinja installed.
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(default_for_string=True, default=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    page = env.get_template("gallery.html.j2").render(
        cases=[build_case(c) for c in CASES],
        recipes={name: r["doc"] for name, r in RECIPES.items()},
        palette=palette(),
        generated=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )

    plots = get_plots_dir()
    dest_dir = args.out or os.path.join(plots, "gallery")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "index.html")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"{len(CASES)} case(s) x {len(RECIPES)} recipe(s) -> {dest}")

    if not args.out:
        # Landing page for the published site, linking the two report trees.
        # Only for the default layout; a custom --out is not a site root.
        site = os.path.join(plots, "index.html")
        with open(site, "w", encoding="utf-8") as fh:
            fh.write(
                env.get_template("site.html.j2").render(
                    generated=datetime.now(timezone.utc).isoformat(timespec="seconds")
                )
            )
        print(f"site index -> {site}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
