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

Requires Python 3.8+. Re-run the install after pulling — `jinja2` was added for
the HTML reports, and `run_tests.py` fails at import without it.

The `pre-commit` hooks run on every commit:

- **ruff** — auto-format and lint Python code

## Structure

```
sliding-squares/
├── src/
│   ├── bfs.py              # Layered BFS — both unidirectional and bidirectional
│   ├── lru.py              # LRU cache backing the bfs memoization
│   ├── grid.py             # Grid representation (free, boundary, hole tiles)
│   ├── robot.py            # n×n square robot representation
│   ├── state.py            # Immutable state snapshots for BFS
│   ├── workspace.py        # Grid + robots + movement rules; build-from-free-cells + placement queries
│   ├── canonical.py        # Spatial symmetries, canonical keys, touching-placement enumeration, Canonicalizer
│   ├── frontier.py         # Frontier helpers for grow/dig searches (initial_frontier, extend_frontier)
│   ├── solver.py           # Solver wrapping bidirectional BFS
│   ├── validator.py        # Step-by-step path execution and validation
│   ├── simplify.py         # Workspace simplification — strip redundant walls, preserve switch count
│   ├── visualizer.py       # Matplotlib visualization (grids, sequences, BFS frontiers, proof rendering)
│   ├── report.py           # run.json + the HTML reports built from it
│   ├── templates/          # Jinja2 templates for those reports
│   │   ├── report.html.j2  #   one run: player, heatmap, recipes
│   │   └── index.html.j2   #   the table over every run
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
├── demo_solver.py
├── demo_validator.py
├── find_hardest_workspace.py      # Parallel search for the workspace requiring the most switches
├── render_run.py                  # run.json -> PNGs, offline (see Reports)
├── run_tests.py
├── requirements.txt
└── README.md
```

## Algorithm

The solver runs a **bidirectional layered breadth-first search** over the state space `(pos_a, pos_b, control)` — see [`src/solver.py`](src/solver.py) and [`src/bfs.py`](src/bfs.py):

1. **Layered structure.** Each BFS layer represents states reachable with exactly *k* control switches. Within a layer, `flood_fill` explores all positions the controlled robot can reach without switching.
2. **Bidirectional expansion.** A forward BFS from the start and a backward BFS from the goal are expanded in lockstep. Both initial controllers are seeded in forward layer 0 and both final controllers in backward layer 0, so the run finds the minimum-switch solution over any choice of first/last mover in a single pass.
3. **Symmetry pruning.** [`src/canonical.py`](src/canonical.py) detects when a workspace is invariant under an A↔B label swap; in that case the dual-start expansion is collapsed to a single BFS half, halving the work.
4. **Memoization.** Per-process LRU caches in `bfs.py` (`_USABLE_CACHE`, `_PARENT_MAP_CACHE`, `_VALID_POS_CACHE`) memoize flood-fill results and valid-position sets. Keys include a `free_key` (an int bitmask where bit `r*cols + c` is set iff cell `(r,c)` is free — ~300× smaller than a frozenset and O(1) to hash), so cached entries are pure functions of their inputs and safely reused across every solve call within a worker. Cache caps are **auto-sized to the grid and the memory budget** (see [Memory budget](#memory-budget) below). Because the caches are pure memoization, they are fully disposable: under memory pressure they are cleared and shrunk (forcing recomputation, never a wrong answer).
5. **Optimality.** The goal is checked at each layer; the first match is optimal by construction. Path reconstruction backtracks through parent pointers to produce a command sequence.

Commands: `U` (up), `D` (down), `L` (left), `R` (right), `S` (switch control).

## Usage

### Run test cases

[`run_tests.py`](run_tests.py) solves each test case, validates the resulting path, and writes the solved sequence to `plots/tests/<name>/`. With no arguments it runs every test case; pass a substring to filter.

```bash
python run_tests.py                        # run every test case
python run_tests.py 3x3                    # only tests whose name contains "3x3"
python run_tests.py --simplified           # every test, every simplify recipe
python run_tests.py 4x4_robot_holes --simplified uncrossable black_peaks
```

| Flag | Default | Purpose |
|---|---|---|
| `name` (positional) | all | Substring filter — run only tests whose name contains it |
| `--simplified` | off | After solving, also run the wall-simplification recipes (below). Bare `--simplified` runs **every** recipe; name recipes after it to run a subset. Without the flag, behaviour is unchanged: solve + plot only |
| `-v`, `--verbose` | off | Print every recipe's full result. Without it each test gets one summary line: how many recipes held, which left the fewest walls, and which failed |
| `--png` | off | Also render the matplotlib images — the per-switch frames and each recipe's `summary.png`. Off by default: the HTML report (below) covers the same ground without paying matplotlib's per-frame cost, which dominates a run. Use it to cross-check the report against the images, or for paper figures |

Run `python run_tests.py --list-recipes` to print the recipes and what each one does. After a run, `plots/tests/<name>/simplified/README.txt` names every recipe folder and ranks them by how few walls survived.

The recipes, defined in `simplify.RECIPES` — each writes to its own folder:

| Recipe | Removes never-touched walls | Thins touched walls by | Frees uncrossable walls |
|---|---|---|---|
| `black` | ✓ | — (keeps every touched wall) | — |
| `black_alternate` | ✓ | every other one, row-major | — |
| `black_peaks` | ✓ | per-face-edge contact peak | — |
| `black_relative` | ✓ | peaks + spacing so no gap exceeds n−1 | — |
| `black_uncrossable` | ✓ | — | ✓ |
| `black_peaks_uncrossable` | ✓ | per-face-edge contact peak | ✓ |
| `black_relative_uncrossable` | ✓ | peaks + spacing | ✓ |
| `uncrossable` | — | — | ✓ (**provably lossless**) |

**The simplification pass** removes walls that aren't load-bearing and crops all-wall borders, then **re-solves to verify the minimum switch count is unchanged.** A wall the robots never touch ("black") is always removed; touched ("orange") walls are thinned according to the chosen mode.

`--uncrossable` adds an *exact* pass on top: the solver sees the grid only through the set of legal n×n robot placements, so a wall whose removal opens no new placement is invisible to it and can be freed with the state space — and therefore the switch count — provably unchanged. This is what thins a straight line of walls down to a picket at spacing n while keeping the corners the robot could round; the spacing is derived from the robot size, so a 1×1 robot keeps every wall and a 5×5 robot keeps every fifth.

Each recipe writes into its own folder, `plots/tests/<name>/simplified/<mode>/`, so strategies sit side by side instead of overwriting each other — `black`, `black_peaks`, `black_uncrossable`, `uncrossable`, and so on. Results are a before/after image, a solved sequence, and `simplification.txt`, which reads **PRESERVED** if the switch count held or **FAILED** if a removed wall turned out to be load-bearing.

### Reports

Every run writes `plots/tests/<name>/run.json` — the encoded record of that
solve: the wall bitstring, both robots at every step, the per-switch turns, and
each simplification recipe's outcome. Everything else derives from it, and it is
regenerated (never hand-edited) on the next run.

Two HTML views are built from it automatically. **Where they land:**

```
plots/
└── tests/
    ├── index.html                      <- START HERE: every run, one table
    ├── 3x3_robot_holes/
    │   ├── run.json                    <- the encoded record
    │   ├── index.html                  <- this run: transitions, heatmap, recipes
    │   ├── png_from_json/              <- only if you run render_run.py
    │   └── simplified/
    │       └── <recipe>/
    │           ├── run.json            <- that recipe's own record
    │           └── index.html          <- its own report, linked from above
    └── 4x4_robot_holes/
        └── ...
```

The per-test folder is the test's name with spaces replaced by underscores. Open
the top-level file directly:

```bash
start plots/tests/index.html      # Windows
open  plots/tests/index.html      # macOS
```

| File | What it is |
|---|---|
| `plots/tests/index.html` | Every run in one table — grid, robot size, switches, recipe verdicts, generation time. Each row links to its run |
| `plots/tests/<name>/index.html` | One run, end to end (below) |

The per-test page holds:

- **A player that advances one control switch at a time** — arrow keys, a
  scrubber, or Play. Each step draws the board after that switch, tracing the
  route the robot actually took, with a faded ghost of where it started and the
  walls it touched shaded orange. Stepping move-by-move made a long solve tedious,
  so moves are summarised per turn instead.

  The board matches the PNGs deliberately: colours come from `visualizer.py`'s
  constants (see `report.palette()`), and the draw order follows
  `visualizer._draw_turn`, so page and image can be compared directly.
- **The path split at each `S`**, so the moves belonging to each switch read
  separately rather than running together in one string.
- **A thumbnail per switch**, the whole solution at a glance.
- **The blocker heatmap** — each wall shaded and labelled by how often it was in
  contact with a robot face. Untouched walls stay black; that split is exactly
  what the recipes act on.
- **The simplification recipes** — the full stats table (walls before/after, the
  black / orange / uncrossable breakdown, total removed, switches, verdict).
  Clicking a row **plays that recipe inline**; its **page** column opens the
  recipe's own standalone report at
  `plots/tests/<name>/simplified/<recipe>/index.html`, which has the same
  player, heatmap and path for the simplified workspace and links back here.
  Recipes are hidden entirely when the run had none.

Both pages are self-contained — open by double-click, no server. The grids are drawn
as SVG in the browser straight from `run.json`, so a report is kilobytes of text
rather than a folder of images, it diffs in git, and tooling can read it.

For raster output, convert on demand:

```bash
python render_run.py plots/tests/3x3_robot_holes/run.json   # per-switch PNGs + transitions.png
python render_run.py plots/tests/*/run.json --chart-only    # just the combined chart
```

It writes to `<run-dir>/png_from_json/`, leaving any existing `switch_NN.png`
untouched so the two can be compared side by side.

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
| `--cache-mb` | `150` | Per-worker memory budget for the bfs flood caches. Cap counts auto-scale with grid area so memory stays near this target. Raise for very large grids (e.g. `500` for 30×30, `1000+` for 100×100) if you have the RAM, or lower `--processes` to give each worker more headroom. |
| `--quiet` | off | Suppress per-iteration progress output |

Outputs land in `plots/hardest/run_<R>x<C>_n<N>/` (proof images plus a `summary.txt`).

At startup each run prints its auto-sized caps, e.g.:
```
Cache sizing (budget=150 MB/worker): parent_map=3400  usable=8400  valid_pos=4200
```

At the end of each run the aggregated cache usage is printed (and appended to `summary.txt`):
```
CACHE USAGE (aggregated across all placements)
  usable      peak_size=.../8400 (...) hits=... hit_rate=...  evictions=...
  parent_map  peak_size=.../3400 (...) hits=... hit_rate=...  evictions=...
```
If any line ends with `HIT LIMIT`, that cache had evictions — raise `--cache-mb` or tune the per-cache caps in [`src/bfs.py`](src/bfs.py).

### Reusable building blocks

Several pieces are factored into `src/` so other tools can import them:

- [`src/canonical.py`](src/canonical.py) — touching-placement enumeration (`all_touching_placements` covers full-edge, partial-edge, and corner contacts; `all_adjacent_placements` is full-edge only), `pick_central_placements`, and the **`Canonicalizer`** class. `Canonicalizer(rows, cols, n)` turns a workspace (free cells + the two robot positions) into one key that is identical under D4 rotation/flip/mirror and the A↔B label swap; use `.dedup_placements(...)` or `.unique_touching(...)` to collapse symmetric duplicates.
- [`src/frontier.py`](src/frontier.py) — `initial_frontier` / `extend_frontier` for growing or digging a free region cell by cell.
- [`src/simplify.py`](src/simplify.py) — `run_simplification(...)`, the wall-removal pass behind `run_tests.py --simplified`.
- [`src/report.py`](src/report.py) — `build_run(...)` / `write_run(...)` encode a solve as `run.json`; `write_local_report(...)` and `write_global_index(...)` render the HTML from it; `encode_grid`, `encode_sequence` and `palette()` are the pieces `simplify.py` and `render_run.py` reuse.
- [`src/workspace.py`](src/workspace.py) — `Workspace.from_free_cells(...)` builds a wall-filled grid with only the given cells carved free; `Workspace.valid_block_positions` / `Workspace.extend_valid` answer n×n placement queries over a free-cell set.

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
