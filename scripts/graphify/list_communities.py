#!/usr/bin/env python3
"""
Print the contents of every community in an existing graph.json.

Useful for picking human-readable names for each community before sharing
the graph or before running the labeling step in /graphify.

Usage:
    python scripts/graphify/list_communities.py                  # uses graphify-out/graph.json
    python scripts/graphify/list_communities.py path/to/graph.json
    python scripts/graphify/list_communities.py --max-samples 15

Note: this file is intentionally NOT named inspect.py because that would
shadow Python's stdlib `inspect` module and break graphify imports.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Inspect each community in a graphify graph.")
    ap.add_argument(
        "graph",
        nargs="?",
        default="graphify-out/graph.json",
        help="Path to graph.json (default: graphify-out/graph.json)",
    )
    ap.add_argument(
        "--max-samples",
        type=int,
        default=10,
        help="Max node labels to show per community (default: 10)",
    )
    ap.add_argument(
        "--max-files",
        type=int,
        default=6,
        help="Max source files to show per community (default: 6)",
    )
    args = ap.parse_args()

    graph_path = Path(args.graph)
    if not graph_path.exists():
        print(f"Graph not found: {graph_path}")
        print("Run scripts/graphify/build_graph.py first, or pass a path.")
        return 1

    g = json.loads(graph_path.read_text(encoding="utf-8"))

    id2label = {n["id"]: n.get("label", n["id"]) for n in g["nodes"]}
    id2src = {n["id"]: n.get("source_file", "") for n in g["nodes"]}

    # graph.json stores community per node; group ids by community
    comm_nodes: dict[int, list[str]] = defaultdict(list)
    for n in g["nodes"]:
        cid = n.get("community", n.get("group", -1))
        comm_nodes[int(cid)].append(n["id"])

    if not comm_nodes:
        print("No communities found in graph.")
        return 1

    ordered = sorted(comm_nodes.items(), key=lambda kv: -len(kv[1]))
    for cid, nids in ordered:
        sample = [id2label.get(n, n) for n in nids[: args.max_samples]]
        files = sorted({os.path.basename(id2src.get(n, "")) for n in nids if id2src.get(n)})
        files = [f for f in files if f][: args.max_files]
        print(f"C{cid} ({len(nids)} nodes)  files={files}")
        print(f"   sample: {sample}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
