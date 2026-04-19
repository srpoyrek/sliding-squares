# Optimal Sliding Squares

Two n×n square robots swap positions in a grid workspace.
Find the workspace that maximizes the minimum number of control switches.

## Problem

Given a grid workspace with obstacles, two identical n×n square robots (A and B) must exchange positions. Only one robot is "controlled" at a time — issuing a control switch command transfers control to the other robot. The solver finds the path that minimizes the number of control switches needed to complete the swap.

## Setup

```bash
pip install -r requirements.txt
python -m pre_commit install
```

Requires Python 3.8+.

The `pre-commit` hooks run on every commit:

- **ruff** — auto-format and lint Python code
- **graphify-build** — rebuild the code knowledge graph (only when `.py` files are staged) and re-stage the regenerated `graphify-out/` artifacts so the graph stays in sync with the code

To skip the graph rebuild on a single commit (rare): `SKIP=graphify-build git commit -m "..."`.

## Structure

```
sliding-squares/
├── src/
│   ├── bfs.py              # Layered BFS — both unidirectional and bidirectional
│   ├── grid.py             # Grid representation (free, boundary, hole tiles)
│   ├── robot.py            # n×n square robot representation
│   ├── state.py            # Immutable state snapshots for BFS
│   ├── workspace.py        # Grid + robots + movement/collision rules
│   ├── symmetry.py         # Spatial symmetries + canonical keys (used to prune redundant BFS halves)
│   ├── solver.py           # Solver wrapping bidirectional BFS
│   ├── validator.py        # Step-by-step path execution and validation
│   ├── visualizer.py       # Matplotlib visualization (grids, sequences, BFS frontiers)
│   ├── path_resolver.py    # Compact path notation parser (e.g. "12R2US")
│   ├── test_case.py        # Base class for test cases
│   └── directories.py      # Path management utilities
├── testcases/
│   ├── 1x1_robot_no_holes.py
│   ├── 2x2_robot_no_holes.py
│   ├── 2x2_robot_holes.py
│   ├── 3x3_robot_no_holes.py
│   ├── 3x3_robot_holes.py
│   ├── 4x4_robot_no_holes.py
│   ├── 4x4_robot_holes.py
│   └── 5x5_robot_no_holes.py
├── plots/
├── data/
├── scripts/
│   └── graphify/                  # Optional: build a code knowledge graph (see below)
├── demo_solver.py
├── demo_validator.py
├── find_hardest_workspace.py      # Parallel search for the workspace requiring the most switches
├── run_tests.py
├── requirements.txt
└── README.md
```

## Algorithm

The solver runs a **bidirectional layered breadth-first search** over the state space `(pos_a, pos_b, control)` — see [`src/solver.py`](src/solver.py) and [`src/bfs.py`](src/bfs.py):

1. **Layered structure.** Each BFS layer represents states reachable with exactly *k* control switches. Within a layer, `flood_fill` explores all positions the controlled robot can reach without switching.
2. **Bidirectional expansion.** A forward BFS from the start and a backward BFS from the goal are expanded in lockstep. Both initial controllers are seeded in forward layer 0 and both final controllers in backward layer 0, so the run finds the minimum-switch solution over any choice of first/last mover in a single pass.
3. **Symmetry pruning.** [`src/symmetry.py`](src/symmetry.py) detects when a workspace is invariant under an A↔B label swap; in that case the dual-start expansion is collapsed to a single BFS half, halving the work.
4. **Memoization.** Per-process caches in `bfs.py` (`_FLOOD_CACHE`, `_VALID_POS_CACHE`) reuse flood-fill results and valid-position sets across forward/backward halves of the same run.
5. **Optimality.** The goal is checked at each layer; the first match is optimal by construction. Path reconstruction backtracks through parent pointers to produce a command sequence.

Commands: `U` (up), `D` (down), `L` (left), `R` (right), `S` (switch control).

## Usage

### Run all test cases

```bash
python run_tests.py
```

### Run a specific test case

```bash
python run_tests.py 3x3_robot_no_holes
```

### Run demos

```bash
python demo_solver.py
python demo_validator.py
```

### Find the hardest workspace

[`find_hardest_workspace.py`](find_hardest_workspace.py) is a parallel candidate generator that searches grid + obstacle configurations to find the workspace requiring the most control switches. It uses a priority queue with enqueue-time depth filtering, a sound symmetric-connectivity pre-check, multiprocessing across cores, and a kill-switch for graceful early termination.

```bash
python find_hardest_workspace.py --rows 3 --cols 3 --n 1 --depth 4
```

Flags:

| Flag | Default | Purpose |
|---|---|---|
| `--rows`, `--cols` | `3`, `3` | Grid dimensions |
| `--n` | `1` | Robot edge length (n×n) |
| `--depth` | `4` | Max obstacles to dig |
| `--processes` | auto | Worker count for the multiprocessing pool |
| `--strategy` | `single` | `single` digs one cell at a time; `strip` digs n-cell strips |
| `--touching` | `edge` | `edge` = full-edge-adjacent robot pairs only; `all` = also corner / partial-offset pairs |
| `--central-only` | off | Only run the most-central representative per adjacency orientation (1–2 placements) — sound because any placement's workspaces can be replicated from a central one |
| `--quiet` | off | Suppress per-iteration progress output |

Outputs land in `plots/hardest/run_<R>x<C>_n<N>/` (proof images plus a `summary.txt`).

## Test Cases

| Test Case | Robot Size | Has Holes |
|-----------|-----------|-----------|
| `1x1_robot_no_holes` | 1×1 | No |
| `2x2_robot_no_holes` | 2×2 | No |
| `2x2_robot_holes` | 2×2 | Yes |
| `3x3_robot_no_holes` | 3×3 | No |
| `3x3_robot_holes` | 3×3 | Yes |
| `4x4_robot_no_holes` | 4×4 | No |
| `4x4_robot_holes` | 4×4 | Yes |
| `5x5_robot_no_holes` | 5×5 | No |

## Code Knowledge Graph (optional)

The `scripts/graphify/` folder contains a small wrapper around [graphify](https://github.com/safishamsi/graphify) that builds a queryable knowledge graph of this codebase — useful for navigating the architecture or handing a structured map of the code to other AI models.

```bash
pip install graphifyy
python scripts/graphify/build_graph.py . --exclude plots
```

Outputs land in `graphify-out/`:

- `graph.json` — raw graph data (pass this to ChatGPT, Cursor, Codex, etc.)
- `GRAPH_REPORT.md` — audit report with god nodes, surprising connections, and suggested questions
- `graph.html` — interactive visualization, open in any browser

To list community contents (helps when naming them):

```bash
python scripts/graphify/list_communities.py
```

The graph is **rebuilt automatically on every commit** that touches a `.py` file, via the `graphify-build` pre-commit hook. You don't need to run `build_graph.py` manually unless you want to refresh between commits.

For richer extraction that also reads docs and images via AI subagents, see the [graphify project](https://github.com/safishamsi/graphify) for the list of supported environments. Local usage details are in [`scripts/graphify/README.md`](scripts/graphify/README.md).
