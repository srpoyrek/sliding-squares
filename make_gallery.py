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
from src.simplify import RECIPES, _prune_uncrossable, simplify_workspace
from tests.fixtures import CASES

CELL = 26


def _diff_svg(before, after, crop, removed, cell=CELL) -> tuple[str, dict]:
    """The original grid with every wall coloured by *which pass* took it.

    Drawn on the ORIGINAL geometry — a cropped result has different dimensions,
    and `crop` is the (top, left) offset that maps one onto the other.

    Colouring by pass rather than by kept/removed is the whole point: "9 walls
    went" says nothing, while "6 were never touched, 3 could never be crossed"
    explains the recipe. `removed` carries the three lists `simplify_workspace`
    returns, which is exactly that attribution.
    """
    top, left = crop
    rows, cols = len(before), len(before[0])
    a_rows, a_cols = len(after), len(after[0]) if after else 0
    by_pass = {key: set(map(tuple, cells)) for key, cells in removed.items()}
    tint = {
        "untouched": "var(--untouched)",
        "thinned": "var(--thinned)",
        "uncrossable": "var(--uncross)",
    }
    counts = {"kept": 0, "untouched": 0, "thinned": 0, "uncrossable": 0, "cropped": 0}
    parts = [
        f'<svg viewBox="0 0 {cols * cell} {rows * cell}" '
        f'width="{cols * cell}" height="{rows * cell}" role="img">'
    ]
    for r in range(rows):
        for c in range(cols):
            fill = "var(--free)"
            if before[r][c] != 0:
                ar, ac = r - top, c - left
                key = next((k for k, cells in by_pass.items() if (r, c) in cells), None)
                if key:
                    fill = tint[key]
                elif not (0 <= ar < a_rows and 0 <= ac < a_cols):
                    fill, key = "var(--cropped)", "cropped"
                elif after[ar][ac] != 0:
                    fill, key = "var(--wall)", "kept"
                else:
                    # Freed, but by none of the three named passes — cropping is
                    # the only other way a wall disappears.
                    fill, key = "var(--cropped)", "cropped"
                counts[key] += 1
            parts.append(
                f'<rect x="{c * cell}" y="{r * cell}" width="{cell}" height="{cell}" '
                f'fill="{fill}" stroke="var(--grid)" stroke-width=".5"/>'
            )
    parts.append("</svg>")
    return "".join(parts), counts


def _scene_svg(case, counts, uncrossable, cell=CELL) -> str:
    """The starting picture, annotated with everything the recipes react to.

    Three things at once, because each recipe is a different answer to them:
    where the robots are, which walls they press (orange, by contact count, the
    same scheme as the blocker heatmap), and which walls the geometry rule finds
    redundant (hatched). Undrawn, a reader has no way to check any recipe's
    result against its inputs.
    """
    tiles = case.tiles
    rows, cols = len(tiles), len(tiles[0])
    peak = max(counts.values()) if counts else 1
    parts = [
        f'<svg viewBox="0 0 {cols * cell} {rows * cell}" '
        f'width="{cols * cell}" height="{rows * cell}" role="img">',
        '<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" '
        'stroke="var(--uncross)" stroke-width="3"/></pattern></defs>',
    ]
    for r in range(rows):
        for c in range(cols):
            wall = tiles[r][c] != 0
            parts.append(
                f'<rect x="{c * cell}" y="{r * cell}" width="{cell}" height="{cell}" '
                f'fill="{"var(--wall)" if wall else "var(--free)"}" '
                f'stroke="var(--grid)" stroke-width=".5"/>'
            )
            if not wall:
                continue
            if (r, c) in uncrossable:
                parts.append(
                    f'<rect x="{c * cell}" y="{r * cell}" width="{cell}" '
                    f'height="{cell}" fill="url(#hatch)" fill-opacity=".85"/>'
                )
            hits = counts.get((r, c), 0)
            if hits:
                parts.append(
                    f'<rect x="{c * cell}" y="{r * cell}" width="{cell}" height="{cell}" '
                    f'fill="var(--hot)" fill-opacity="{0.3 + 0.6 * (hits / peak):.3f}"/>'
                    f'<text x="{(c + 0.5) * cell}" y="{(r + 0.5) * cell}" '
                    f'font-size="{cell * 0.4:.1f}" font-weight="700" fill="#fff" '
                    f'text-anchor="middle" dominant-baseline="central">{hits}</text>'
                )

    # Robot A's whole slide: the start solid, later steps ghosted, so the run
    # that produced those contact numbers is visible rather than implied.
    n = case.n
    for i, (ar, ac) in enumerate(case.path_a or []):
        op = 0.85 if i == 0 else 0.22
        parts.append(
            f'<rect x="{ac * cell}" y="{ar * cell}" width="{n * cell}" '
            f'height="{n * cell}" fill="var(--a)" fill-opacity="{op}" '
            f'stroke="#fff" stroke-width="2"/>'
        )
    if case.path_a:
        ar, ac = case.path_a[0]
        parts.append(
            f'<text x="{(ac + n / 2) * cell}" y="{(ar + n / 2) * cell}" '
            f'font-size="{cell * 0.7:.1f}" font-weight="700" fill="#fff" '
            f'text-anchor="middle" dominant-baseline="central">A</text>'
        )
    br, bc = case.pos_b
    parts.append(
        f'<rect x="{bc * cell}" y="{br * cell}" width="{n * cell}" height="{n * cell}" '
        f'fill="var(--b)" fill-opacity=".85" stroke="#fff" stroke-width="2"/>'
        f'<text x="{(bc + n / 2) * cell}" y="{(br + n / 2) * cell}" '
        f'font-size="{cell * 0.7:.1f}" font-weight="700" fill="#fff" '
        f'text-anchor="middle" dominant-baseline="central">B</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def build_case(case) -> dict:
    """One scenario through every recipe, with the inputs shown alongside."""
    before = case.tiles
    counts, face_counts = case.contacts()

    # The geometry rule in isolation, purely so the scene can mark which walls
    # it considers redundant before any recipe runs.
    probe = case.tiles
    uncrossable = set(map(tuple, _prune_uncrossable(probe, case.n)))

    results = []
    for mode, recipe in RECIPES.items():
        ws = case.workspace()
        simplified, untouched, thinned, uncross, crop = simplify_workspace(
            ws, counts, face_counts=face_counts, **recipe["kwargs"]
        )
        svg, tally = _diff_svg(
            before,
            simplified.grid.tiles,
            crop,
            {"untouched": untouched, "thinned": thinned, "uncrossable": uncross},
        )
        results.append({"mode": mode, "svg": svg, **tally})

    return {
        "name": case.name,
        "n": case.n,
        "why": case.why,
        "walls_before": sum(cell != 0 for row in before for cell in row),
        "touched": len(counts),
        "uncrossable": len(uncrossable),
        "steps": len(case.path_a or []),
        "scene_svg": _scene_svg(case, counts, uncrossable),
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
