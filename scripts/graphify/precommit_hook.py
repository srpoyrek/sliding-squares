#!/usr/bin/env python3
"""
Pre-commit wrapper around build_graph.py.

Runs the AST-only graph build before each commit *only if* Python files
are staged. If the build succeeds, the regenerated outputs are added to
the same commit so the graph stays in sync with the code.

Wired up in .pre-commit-config.yaml under hook id: graphify-build
Skip in an emergency with: SKIP=graphify-build git commit ...
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Outputs to re-stage if they exist after the build.
# Anything in the # graphify .gitignore section is intentionally NOT here.
TRACKED_OUTPUTS = [
    "graphify-out/graph.json",
    "graphify-out/GRAPH_REPORT.md",
    "graphify-out/graph.html",
    "graphify-out/manifest.json",
]


def staged_python_files() -> list[str]:
    """Return paths of .py files staged for commit (any status)."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.endswith(".py")]


def main() -> int:
    py_changes = staged_python_files()
    if not py_changes:
        print("[graphify] No staged .py changes - skipping graph rebuild.")
        return 0

    print(f"[graphify] {len(py_changes)} staged .py file(s) - rebuilding code knowledge graph...")
    rc = subprocess.call(
        [
            sys.executable,
            "scripts/graphify/build_graph.py",
            ".",
            "--exclude",
            "plots",
        ]
    )
    if rc != 0:
        print("[graphify] Build failed - aborting commit.", file=sys.stderr)
        return rc

    existing = [o for o in TRACKED_OUTPUTS if Path(o).exists()]
    if existing:
        subprocess.check_call(["git", "add", *existing])
        print(f"[graphify] Re-staged: {', '.join(existing)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
