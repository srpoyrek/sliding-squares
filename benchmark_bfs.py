"""Forwarder: the solver benchmark driver lives in `benchmark_solvers.py` — the
comparison covers every variant, not only the BFS searches, so the name moved
with it. This file only forwards and can be deleted once nothing calls it."""

from __future__ import annotations

import sys

from benchmark_solvers import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
