#!/usr/bin/env python3
"""
Build a knowledge graph of a codebase (AST-only, no LLM).

Cross-platform: Windows, macOS, Linux.
Drop this folder into any project; it has no project-specific assumptions.

For richer extraction that also reads docs, papers, and images, use the
`/graphify` skill inside Claude Code instead -- that one dispatches AI
subagents. This script is the free, fast, code-only fallback.

Usage:
    python scripts/graphify/build_graph.py                     # scan current dir
    python scripts/graphify/build_graph.py src                 # scan a subfolder
    python scripts/graphify/build_graph.py . --exclude plots --exclude data
    python scripts/graphify/build_graph.py . --no-viz          # skip HTML
    python scripts/graphify/build_graph.py . --out custom-dir  # custom output dir

Requires: pip install graphifyy
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePath

# Make stdout tolerant of Unicode (the graphify.benchmark module prints box chars)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    from graphify.analyze import god_nodes, suggest_questions, surprising_connections
    from graphify.build import build_from_json
    from graphify.cluster import cluster, score_all
    from graphify.detect import detect, save_manifest
    from graphify.export import to_html, to_json
    from graphify.extract import collect_files, extract
    from graphify.report import generate
except ImportError:
    sys.exit("graphify is not installed. Run: pip install graphifyy")


def filter_excluded(detection: dict, patterns: list[str]) -> dict:
    """Drop any file whose path contains one of the exclude folder names."""
    if not patterns:
        return detection

    def is_excluded(path_str: str) -> bool:
        parts = PurePath(path_str).parts
        return any(pat in parts for pat in patterns)

    filtered = {
        cat: [f for f in files if not is_excluded(f)]
        for cat, files in detection.get("files", {}).items()
    }
    kept = sum(len(v) for v in filtered.values())
    orig = detection.get("total_files", 0)
    ratio = (kept / orig) if orig else 0

    detection["files"] = filtered
    detection["total_files"] = kept
    detection["total_words"] = int(detection.get("total_words", 0) * ratio)
    detection["warning"] = None
    return detection


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a code knowledge graph (AST-only).")
    ap.add_argument("path", nargs="?", default=".", help="Path to scan (default: .)")
    ap.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="FOLDER",
        help="Folder name to exclude anywhere in path (repeatable). "
        "Example: --exclude plots --exclude node_modules",
    )
    ap.add_argument("--no-viz", action="store_true", help="Skip the HTML visualization")
    ap.add_argument(
        "--out",
        default="graphify-out",
        metavar="DIR",
        help="Output directory (default: graphify-out)",
    )
    ap.add_argument(
        "--benchmark",
        action="store_true",
        help="Also print token-reduction benchmark at the end",
    )
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Step 1: detect ---
    print(f"[1/5] Scanning: {args.path}")
    detection = detect(Path(args.path))
    if args.exclude:
        detection = filter_excluded(detection, args.exclude)
        print(f"      Excluding folders: {args.exclude}")
    counts = {k: len(v) for k, v in detection.get("files", {}).items() if v}
    print(
        f"      Found: {detection['total_files']} "
        f"files ~{detection['total_words']:,} words  {counts}"
    )
    if detection["total_files"] == 0:
        print("Nothing to process.")
        return 1

    # --- Step 2: AST extraction (free, no LLM) ---
    print("[2/5] AST extraction (tree-sitter, no LLM)...")
    code_paths: list[Path] = []
    for f in detection["files"].get("code", []):
        p = Path(f)
        code_paths.extend(collect_files(p) if p.is_dir() else [p])

    if not code_paths:
        print("      No code files found.")
        print(
            "      This script is AST-only. For docs/papers/images, use /graphify in Claude Code."
        )
        return 1

    extraction = extract(code_paths)
    extraction.setdefault("hyperedges", [])
    extraction.setdefault("input_tokens", 0)
    extraction.setdefault("output_tokens", 0)
    print(f"      {len(extraction['nodes'])} nodes, {len(extraction['edges'])} edges")

    # --- Step 3: build graph, cluster, analyze ---
    print("[3/5] Building graph + community detection...")
    G = build_from_json(extraction)
    if G.number_of_nodes() == 0:
        print("Graph is empty -- nothing to do.")
        return 1

    communities = cluster(G)
    cohesion = score_all(G, communities)
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    labels = {cid: f"Community {cid}" for cid in communities}
    questions = suggest_questions(G, communities, labels)
    print(
        f"      {G.number_of_nodes()} nodes, "
        f"{G.number_of_edges()} edges, "
        f"{len(communities)} communities"
    )

    # --- Step 4: write outputs ---
    print(f"[4/5] Writing outputs to {out_dir}/ ...")
    tokens = {"input": 0, "output": 0}
    report = generate(
        G,
        communities,
        cohesion,
        labels,
        gods,
        surprises,
        detection,
        tokens,
        args.path,
        suggested_questions=questions,
    )
    (out_dir / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    to_json(G, communities, str(out_dir / "graph.json"))

    if args.no_viz:
        print("      HTML viz skipped (--no-viz)")
    elif G.number_of_nodes() > 5000:
        print(f"      HTML viz skipped (graph has {G.number_of_nodes()} nodes > 5000)")
    else:
        to_html(G, communities, str(out_dir / "graph.html"), community_labels=labels)
        print("      graph.html written")

    # --- Step 5: manifest + cost tracker ---
    print("[5/5] Saving manifest and cost tracker...")
    save_manifest(detection["files"])
    cost_path = out_dir / "cost.json"
    cost = (
        json.loads(cost_path.read_text(encoding="utf-8"))
        if cost_path.exists()
        else {"runs": [], "total_input_tokens": 0, "total_output_tokens": 0}
    )
    cost["runs"].append(
        {
            "date": datetime.now(timezone.utc).isoformat(),
            "input_tokens": 0,
            "output_tokens": 0,
            "files": detection.get("total_files", 0),
            "mode": "ast-only",
        }
    )
    cost_path.write_text(json.dumps(cost, indent=2), encoding="utf-8")

    # --- Optional: benchmark ---
    if args.benchmark:
        print()
        try:
            from graphify.benchmark import print_benchmark, run_benchmark

            result = run_benchmark(
                str(out_dir / "graph.json"), corpus_words=detection["total_words"]
            )
            print_benchmark(result)
        except Exception as e:
            print(f"(benchmark skipped: {e})")

    print()
    print(f"Done. Outputs in {out_dir}/")
    print(f"  {out_dir}/GRAPH_REPORT.md    audit report")
    print(f"  {out_dir}/graph.json         raw graph data (hand to other AI models)")
    if not args.no_viz and G.number_of_nodes() <= 5000:
        print(f"  {out_dir}/graph.html         interactive viz, open in browser")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
