# Optimal Sliding Squares

Two n×n square robots swap positions in a grid workspace.
Find the workspace that maximizes the minimum number of control switches.

**[📊 Browse the reports](https://srpoyrek.github.io/sliding-squares/)** —
every solved test case stepped switch by switch, the blocker heatmaps, and a
[gallery](https://srpoyrek.github.io/sliding-squares/gallery/index.html)
showing what each simplification recipe does. Rebuilt from `main` on every push;
nothing generated is committed.

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
│   ├── bfs.py              # Layered BFS — mirror (default), bidirectional, unidirectional
│   ├── lru.py              # LRU cache backing the bfs memoization
│   ├── grid.py             # Grid representation (free, boundary, hole tiles)
│   ├── robot.py            # n×n square robot representation
│   ├── state.py            # Immutable state snapshots for BFS
│   ├── workspace.py        # Grid + robots + movement rules; build-from-free-cells + placement queries
│   ├── canonical.py        # Spatial symmetries, canonical keys, touching-placement enumeration, Canonicalizer
│   ├── frontier.py         # Frontier helpers for grow/dig searches (initial_frontier, extend_frontier)
│   ├── solver.py           # Solver wrapping the BFS — mirror by default, switchable
│   ├── validator.py        # Step-by-step path execution and validation
│   ├── simplify.py         # Workspace simplification — strip redundant walls, preserve switch count
│   ├── visualizer.py       # Matplotlib visualization (grids, sequences, BFS frontiers, proof rendering)
│   ├── report.py           # run.json + the HTML reports built from it
│   ├── benchmark.py        # BFS comparison — measurement, benchmark.json, its report
│   ├── templates/          # Jinja2 templates for every generated page
│   │   ├── report.html.j2  #   one run: player, heatmap, recipes
│   │   ├── index.html.j2   #   the table over every run
│   │   ├── benchmark.html.j2 # the BFS comparison: charts, per-case tables, how each search works
│   │   ├── gallery.html.j2 #   every fixture x every simplify recipe
│   │   └── site.html.j2    #   the landing page linking the report trees
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
├── plots/                         # Generated reports — untracked, built by a run
├── demo_solver.py
├── demo_validator.py
├── tests/
│   ├── fixtures.py                # Hand-built corner/edge/junction layouts + expectations
│   ├── conftest.py
│   └── test_simplify.py           # Proves the simplification passes' claims
├── .github/workflows/pages.yml    # Verify, build reports, publish to Pages
├── find_hardest_workspace.py      # Parallel search for the workspace requiring the most switches
├── benchmark_bfs.py               # Compare the three BFS searches (see BFS comparison)
├── make_gallery.py                # Recipe gallery: every fixture x every recipe
├── render_run.py                  # run.json -> PNGs, offline (see Reports)
├── run_tests.py
├── requirements.txt
└── README.md
```

## Algorithm

The solver runs a **single-tree layered breadth-first search** over the state space `(pos_a, pos_b, control)` — see [`src/solver.py`](src/solver.py) and [`src/bfs.py`](src/bfs.py):

1. **Layered structure.** Each BFS layer represents states reachable with exactly *k* control switches. Within a layer, `flood_fill` explores all positions the controlled robot can reach without switching.
2. **Relabelling symmetry.** The two robots are identical squares and the grid never moves, so exchanging their labels is a symmetry of *every* workspace — no geometric symmetry of the walls is required. Because the goal is the start with the robots exchanged, that relabelling carries the start onto the goal, and the states *l* switches from the goal are exactly the relabelling of the states *l* switches from the start. The backward half of a search is therefore the forward half relabelled, the same size at every layer.
3. **Mirror meeting.** Only the forward tree is built. A state's distance to the goal is read out of the same `visited` map by looking up its relabelling, so the tree, its parent pointers and its frontier are built once instead of twice. Both initial controllers are seeded in layer 0, which covers either robot moving first — and, under the relabelling, either moving last.
4. **Memoization.** Per-process LRU caches in `bfs.py` (`_USABLE_CACHE`, `_PARENT_MAP_CACHE`, `_VALID_POS_CACHE`) memoize flood-fill results and valid-position sets. Keys include a `free_key` (an int bitmask where bit `r*cols + c` is set iff cell `(r,c)` is free — ~300× smaller than a frozenset and O(1) to hash), so cached entries are pure functions of their inputs and safely reused across every solve call within a worker. Cache caps are **auto-sized to the grid and the memory budget** (see [Memory budget](#memory-budget) below). Because the caches are pure memoization, they are fully disposable: under memory pressure they are cleared and shrunk (forcing recomputation, never a wrong answer).
5. **Optimality.** Layer *h* makes exactly two totals newly reachable — 2*h*−1 (relabelling one layer back) and 2*h* (relabelling in this layer). The whole layer is scanned and the smallest total taken before the layer is left, which is what keeps the answer minimal: arriving at layer *h* with nothing found already proves the optimum is at least 2*h*−1, so the first total found there is that optimum.
6. **Reconstruction.** Both halves are backtracked through the parent pointers as **segments** — one robot walking while the other stands still — and joined *before* either becomes moves. The halves meet inside a segment rather than between two: the first half walks a robot into the meeting square and the second walks the same robot, around the same stationary partner, back out of it. Those two are merged into one segment and planned as a single shortest route, so the path is minimal in moves as well as in switches. Rendering the halves separately instead would detour through the meeting square and imply a switch that is not in the count.
7. **First mover.** Each search reports which robot moves in layer 0 alongside the path. Commands name no robot, so a replay has to be told who holds control at step 0 and then follow the switches; reading it off the first *move* command is wrong whenever the layer-0 segment is empty, because the path then opens with a switch and the first robot to move is the second to hold control.

Commands: `U` (up), `D` (down), `L` (left), `R` (right), `S` (switch control).

`bfs_bidirectional` — the earlier forward-plus-backward pair — is still in [`src/bfs.py`](src/bfs.py) so the two searches can be cross-checked against each other (`run_tests.py --bidirectional`). It is also what `Solver` falls back to for a goal that is not a straight swap, which `bfs_mirror` rejects outright.

## Usage

### Run test cases

[`run_tests.py`](run_tests.py) solves each test case, validates the resulting path, and writes the solved sequence to `plots/tests/<name>/`. With no arguments it runs every test case; pass a substring to filter.

```bash
python run_tests.py                        # run every test case
python run_tests.py 3x3                    # only tests whose name contains "3x3"
python run_tests.py --simplified           # every test, every simplify recipe
python run_tests.py 4x4_robot_holes --simplified uncrossable untouched_spaced
```

| Flag | Default | Purpose |
|---|---|---|
| `name` (positional) | all | Substring filter — run only tests whose name contains it |
| `--simplified` | off | After solving, also run the wall-simplification recipes (below). Bare `--simplified` runs **every** recipe; name recipes after it to run a subset. Without the flag, behaviour is unchanged: solve + plot only |
| `-v`, `--verbose` | off | Print every recipe's full result. Without it each test gets one summary line: how many recipes held, which left the fewest walls, and which failed |
| `--png` | off | Also render the matplotlib images — the per-switch frames and each recipe's `summary.png`. Off by default: the HTML report (below) covers the same ground without paying matplotlib's per-frame cost, which dominates a run. Use it to cross-check the report against the images, or for paper figures |
| `--bidirectional` | off | Solve with the older forward+backward search instead of the single-tree mirror search (see [Algorithm](#algorithm)). Both are exact, so the switch counts must agree; the flag exists to check that they do. It applies to the recipe re-solves too, so a comparison covers the simplified workspaces as well |

Run `python run_tests.py --list-recipes` to print the recipes and what each one does. After a run, `plots/tests/<name>/simplified/README.txt` names every recipe folder and ranks them by how few walls survived.

The recipes, defined in `simplify.RECIPES` — each writes to its own folder:

| Recipe | Removes never-touched walls | Thins touched walls by | Frees uncrossable walls |
|---|---|---|---|
| `untouched_spaced` | ✓ | contact plateaus + spacing so no gap exceeds n−1 | — |
| `untouched_uncrossable` | ✓ | — | ✓ |
| `untouched_spaced_uncrossable` | ✓ | plateaus + spacing | ✓ |
| `uncrossable` | — | — | ✓ (**provably lossless**) |

**Pass order: crop → contact rules → placement rule.** The order is load-bearing,
and the tempting rearrangement is wrong.

The placement rule finds far more walls on a dense grid than on a thinned one —
124 versus 36 on `3x3_robot_holes`. That looks like the contact rules are
starving it, and like running it first would be free, since it leaves the
placement set unchanged **by definition**.

It isn't. That guarantee is relative to *the grid it measures*. The extra 88
walls are exactly the ones that **become load-bearing** once the contact rules
open the grid up. Remove them anyway and the workspace gets strictly more
permissive, the solver finds a shorter path, and the switch count drops —
`untouched_spaced_uncrossable` fails outright.

Running the placement rule **last** is what makes its guarantee apply to the
grid you actually ship.

Cropping stays first for a separate reason: an all-wall border is redundant only
while it is still all wall. Free a cell inside it and peeling that border would
delete a free cell, which is not lossless.

**The simplification pass** removes walls that aren't load-bearing and crops all-wall borders, then **re-solves to verify the minimum switch count is unchanged.** A wall the robots never touch is removed; touched walls are thinned according to the chosen recipe.

`--uncrossable` adds an *exact* pass on top: the solver sees the grid only through the set of legal n×n robot placements, so a wall whose removal opens no new placement is invisible to it and can be freed with the state space — and therefore the switch count — provably unchanged. This is what thins a straight line of walls down to a picket at spacing n while keeping the corners the robot could round; the spacing is derived from the robot size, so a 1×1 robot keeps every wall and a 5×5 robot keeps every fifth.

Each recipe writes into its own folder, `plots/tests/<name>/simplified/<mode>/`, so strategies sit side by side instead of overwriting each other — `untouched_spaced`, `untouched_uncrossable`, `uncrossable`, and so on. Results are that recipe's own `run.json` and `index.html`, plus `simplification.txt`, which reads **PRESERVED** if the switch count held or **FAILED** if a removed wall turned out to be load-bearing.

### Reports

Every run writes `plots/tests/<name>/run.json` — the encoded record of that
solve: the wall bitstring, both robots at every step, the per-switch turns, and
each simplification recipe's outcome. Everything else derives from it, and it is
regenerated (never hand-edited) on the next run.

Two HTML views are built from it automatically. **Where they land:**

```
plots/
├── index.html                          <- START HERE: landing page, links the trees
├── tests/
│   ├── index.html                      <- every run, one table
│   ├── 3x3_robot_holes/
│   │   ├── run.json                    <- the encoded record
│   │   ├── index.html                  <- this run: transitions, heatmap, recipes
│   │   ├── png_from_json/              <- only if you run render_run.py
│   │   └── simplified/
│   │       └── <recipe>/
│   │           ├── run.json            <- that recipe's own record
│   │           └── index.html          <- its own report, linked from above
│   └── 4x4_robot_holes/
│       └── ...
├── gallery/
│   └── index.html                      <- only if you run make_gallery.py
└── benchmark/
    ├── benchmark.json                  <- the comparison record
    └── index.html                      <- only if you run benchmark_bfs.py
```

The per-test folder is the test's name with spaces replaced by underscores.
Every page is self-contained, so opening one needs no server:

```bash
start plots/tests/index.html      # Windows
open  plots/tests/index.html      # macOS
xdg-open plots/tests/index.html   # Linux
```

| File | What it is |
|---|---|
| `plots/index.html` | The landing page. Links the report trees; the BFS-comparison card appears once that page has been built. Rewritten by both `make_gallery.py` and `benchmark_bfs.py`, so it reflects what is on disk rather than the order they were run in |
| `plots/benchmark/index.html` | The [BFS comparison](#bfs-comparison) |
| `plots/tests/index.html` | Every run in one table — grid, robot size, switches, recipe verdicts, and the **best recipe** for that test: every recipe leaving the fewest walls *while preserving the switch count*, each linked to its own page. Recipes tie often, so all winners are listed rather than one being picked arbitrarily; they are ordered so the result with more walls freed by the placement rule reads first, those being lossless by construction. A failed recipe usually leaves fewer walls, but it has changed the problem, so it cannot win. Below the table, **two charts per test** — solve time and states held — show each recipe's re-solve against that test's original solve as a signed percent change, with the absolute time or state count beside it and a dashed line at `±0%`; a bar ending left of it is a cheaper solve, negative is better, and a failed recipe is drawn hollow because its cheaper solve is for an easier problem. **Solve cost vs robot size** then overlays every recipe and the original on one chart for solve time and one for states held — solid for no-holes tests, dashed for holes, log axis since the cases span four orders of magnitude — so how each recipe's cost *scales* is visible, not only its size on one test. The **Recipes ranked** table adds the same two ratios per recipe across all tests (geometric mean over the runs it held) |
| `plots/tests/<name>/index.html` | One run, end to end (below) |

The index also carries two **robot-size charts** — minimum control switches, and
obstacles remaining after simplification — each plotted against robot size with
holed and hole-free workspaces as separate series, so the cost of interior
obstacles is visible at a glance. They are inline SVG, drawn from the same
`run.json` data, so the page stays self-contained.

And a **Recipes ranked** table: every recipe across every
test, ordered by mean wall reduction, with how often it preserved the switch
count and how often it was the best on a test. The average counts only runs
where the recipe held — including a failure would flatter it, since a broken
workspace is the smallest of all. The per-test winner tells you what suited one
workspace; this tells you which recipe is worth reaching for in general.

The per-test page holds:

- **A player that advances one control switch at a time** — arrow keys, a
  scrubber, or Play. Each step draws the board after that switch, tracing the
  route the robot actually took, with a faded ghost of where it started and the
  walls it touched shaded orange. Stepping move-by-move made a long solve tedious,
  so moves are summarised per turn instead.

  The board matches the PNGs deliberately: colours come from `visualizer.py`'s
  constants (see `report.palette()`), and the draw order follows
  `visualizer._draw_turn`, so page and image can be compared directly.

  **Every board on the page sits in its own fixed-size viewport and is scaled to
  fit it** — the player, the side-by-side panels, the heatmaps, the per-switch
  thumbnails and the recipe thumbnails. Stepping through switches, swapping
  recipes or opening a larger grid therefore never moves anything else on the
  page. Each viewport has `−` / `+` / `fit` buttons and takes `Ctrl`+wheel, which
  zooms towards the pointer; **drag the board to pan** once it is larger than
  its box — there are no scrollbars — and the corner handle drags the box
  itself larger. Zoom and pan are remembered per board, so stepping the player
  does not reset them. The side-by-side view opens on the original against
  `untouched_spaced_uncrossable` when that recipe was run.
- **The path split at each `S`**, so the moves belonging to each switch read
  separately rather than running together in one string.
- **A thumbnail per switch**, the whole solution at a glance.
- **The blocker heatmap** — each wall shaded and labelled by how often a robot
  face was in contact with it. Walls with no contact are left unshaded, and that
  split is what every contact-driven recipe acts on.
- **A side-by-side comparison.** Two dropdowns pick any two of the original and
  its simplified variants; both boards **step together**, so the same switch
  number shows on each and you can watch where the two solutions diverge. Their
  **heatmaps sit beneath**, so you can see which walls each solution actually
  leans on. A variant that solves in fewer switches simply holds at its final
  state once the longer one continues. Hidden when the run had no recipes.
- **The simplification recipes** — the full stats table (walls before/after, the
  untouched / thinned / uncrossable breakdown, total removed, switches, verdict),
  plus **what each recipe did to the cost of solving**: the re-solve's time and
  states held, each as a ratio against the original solve, which sits as the
  first row of the table for reference. Negative is cheaper.

  **Expect the two to disagree.** Removing walls opens the grid, so the search
  visits *more* positions for the same answer — states usually rise after
  simplification. But the recipes also crop the grid, and every flood fill
  scans the grid's legal positions, so each step gets cheaper — time can fall
  while states rise. To keep the times comparable, the original is solved
  twice and the second solve timed, with the flood caches cleared in between:
  the first solve in a fresh worker pays one-off costs the recipe re-solves
  never do, and clearing the caches stops the timed solve being handed the
  warm-up's floods. Peak RAM is deliberately not measured here — it would need
  `tracemalloc` inside the same worker as the timed solve, inflating the
  timings; the [BFS comparison](#bfs-comparison) measures it properly, one
  process per solve.
  Clicking a row plays that recipe's solution inline; its **page** column opens
  the recipe's own standalone report at
  `plots/tests/<name>/simplified/<recipe>/index.html`, which carries the same
  player, heatmap and path for the simplified workspace and links back here.
  Recipes are hidden entirely when the run had none.

Both pages are self-contained — open by double-click, no server. The grids are drawn
as SVG in the browser straight from `run.json`, so a report is kilobytes of text
rather than a folder of images, it diffs in git, and tooling can read it.

For raster output, convert on demand:

```bash
python render_run.py plots/tests/3x3_robot_holes/run.json   # per-switch PNGs + transitions.png
python render_run.py plots/tests/*/run.json --chart-only    # just the combined chart
python render_run.py plots/tests/3x3_robot_holes/run.json --out-dir figures/
```

It writes to `<run-dir>/png_from_json/`, leaving any existing `switch_NN.png`
untouched so the two can be compared side by side.

### BFS comparison

[`benchmark_bfs.py`](benchmark_bfs.py) runs every test case through all three
searches in [`src/bfs.py`](src/bfs.py) and publishes the comparison to
`plots/benchmark/index.html`.

| Search | Depth | Trees | What it does |
|---|---|---|---|
| `mirror` | D/2 | 1 | One forward tree; each state's distance to the goal is read off that same tree through the A↔B relabelling |
| `bidirectional` | D/2 | 2 | A forward and a backward tree, expanded in lockstep until they meet |
| `unidirectional` | D | 1 | One forward tree, expanded the whole way to the goal — the baseline |

```bash
python benchmark_bfs.py                            # every case, every search
python benchmark_bfs.py 3x3                        # only cases matching "3x3"
python benchmark_bfs.py --variants mirror,bidirectional
python benchmark_bfs.py --repeat 5 --timeout 300
```

| Flag | Default | Purpose |
|---|---|---|
| `name` (positional) | all | Substring filter — only benchmark cases whose name contains it |
| `--variants` | all three | Comma-separated searches to compare, in table order |
| `--repeat` | `3` | Warm repeats timed after the cold solve; the minimum and median of these are reported |
| `--timeout` | `120` | Seconds allowed per case+search before the measurement is killed and recorded as a timeout. The unidirectional search expands to depth D rather than D/2, so it is the one that needs this |
| `--out` | `plots/benchmark/` | Directory for `benchmark.json` and `index.html`. A custom path is not the site layout, so nothing is relinked |

**All three searches are exact, so this is a correctness check as much as a
performance one.** Their switch counts must agree and every path they return
must validate; the page leads with whether they did, because no timing below
that is worth reading until they do.

Each measurement runs in **its own spawned process**. That gives empty flood
caches (so whichever search runs second is not handed the first one's work), a
`tracemalloc` peak covering that search alone, and a hard timeout for a search
that runs away.

What each measurement means:

| Measurement | Unit | What it is |
|---|---|---|
| `turns` | count | The answer: minimum control turns to swap the robots. All three searches are exact, so this must be identical across them |
| `states` | count of states | States held in the search's `visited` map. **The structural cost, and exact** — the same number on every machine and every run. This is the number to judge the searches by |
| `time` | seconds | Wall clock for one solve, fastest of `--repeat` runs, with the flood caches already warm. Warm because that isolates each search's own bookkeeping from the flood fills all three share. Machine-dependent: a trend, not a constant |
| `ram` | bytes | Most memory held at once during one solve — `tracemalloc` peak on the first solve, in a fresh process with cold caches |
| `vs bidirectional` | % change | That search against `bidirectional`, same measurement, same cases, as a signed percent change: `−50%` is half as much, `+100%` twice as much, `±0%` the same. **Negative is better** |

**One convention for every comparison, on every page:** signed percent change
against the reference — the original solve, or `bidirectional` — where negative
is always better. This is the form the wall-reduction column already used
(`−84%`), so solve time, states held and peak RAM now read the same way, and the
same number is never a multiple in one place and a percentage in another.

**`ram` moves much less than `states` does**, and that is expected: `flood_fill`
keeps its results in the LRU caches in [`src/bfs.py`](src/bfs.py), all three
searches fill them identically, and that shared cache dominates the peak. The
state count is where the searches actually differ.

**`avg per case` is a geometric mean**, not an ordinary one. The centre of a
ratio is multiplicative — `+100%` and `−50%` are opposite results and must
cancel to `±0%`, which an arithmetic mean puts at `+25%`, biasing every
comparison towards "worse".

**Read the average and the total together; they can disagree.** These cases span
four orders of magnitude, so the average lets a 200 KB solve outvote a 95 MB one
while the total is decided almost entirely by the largest grid. `best on N/M`
counts the cases each search actually won, which is the tiebreaker. `mirror`
holds fewer states on every case, but on RAM and time it wins the large cases
and loses the toys — so its totals look good while its averages do not.

In the totals, **`states` and `time` are summed but `ram` is not**. A total of
states or seconds means something — all of them get built, all of them get
spent. Peak memory does not add up that way: every case runs in its own process
and peaks at its own moment, so summing those peaks would report a figure larger
than any amount of memory ever actually held. It is the **worst single case**
instead, with the ratio averaged per case so one large grid cannot decide it
alone.

`benchmark.json` also records `cold_seconds` and `warm_median` for each run;
the page shows the fastest warm time, since that is the least noisy number.

`plots/benchmark/benchmark.json` is the record; the page is rendered from it, so
regenerate rather than editing either by hand. The run also rewrites the landing
page `plots/index.html`, which links the comparison only once the page exists —
so the card is there whichever order `benchmark_bfs.py` and `make_gallery.py`
were run in.

### Verify the simplification

The recipes make specific claims; the suite checks them rather than taking them
on trust.

```bash
python -m pytest              # the whole suite
python make_gallery.py        # -> plots/gallery/index.html
```

[`tests/fixtures.py`](tests/fixtures.py) holds small layouts chosen so the right
answer is provable on paper — a solid mass, one-thick lines in both
orientations, a grid corner, a wall against the border, L and T junctions, a
lone wall in open space, a full wall border, and the degenerate `n=1` case.

[`tests/test_simplify.py`](tests/test_simplify.py) asserts *properties* rather
than golden pictures, because a pasted-in expected grid only proves the code
still does what it did that day. The claims it checks:

| Claim | Why it matters |
|---|---|
| `_prune_uncrossable` never changes the legal n×n placement set | This **is** the losslessness argument — the solver sees only placements, so an unchanged set means an unchanged switch count |
| one sweep is a fixed point | A second pass must find nothing, or callers are silently getting a partial result |
| a pass only ever frees walls | It must never add one |
| `n=1` frees nothing | Every wall is its own placement, so none is redundant |
| removals are monotonic in `n` | A bigger robot crosses fewer gaps, so more walls become redundant |
| the spacing rule never leaves a gap ≥ `n` | Otherwise an n×n robot slips through the thinned line |
| every recipe key equals `mode_name(**its kwargs)` | The key names the output folder while the status is stamped from `mode_name`; drift means writing to one folder and reporting another |

`make_gallery.py` renders the same fixtures as a page — the original beside each
recipe's result, every original wall coloured **kept**, **removed** or **cropped
away**. It drives `simplify_workspace` with the fixture's own contact counts, so
a case only has to be a *shape*, not a solvable puzzle; that is what keeps the
cases small enough to reason about.

### Published reports

[`.github/workflows/pages.yml`](.github/workflows/pages.yml) runs lint and the
test suite, then solves every test case, builds the reports and the gallery, and
publishes `plots/` to GitHub Pages — **committing nothing**. The site therefore
always matches the code at `main`, not whenever an artifact was last committed,
which is the same rule the repo applies locally.

Enable it once under **Settings → Pages → Source: GitHub Actions**. Then:

| Page | What it holds |
|---|---|
| [Landing page](https://srpoyrek.github.io/sliding-squares/) | Links to the report trees |
| [Test runs](https://srpoyrek.github.io/sliding-squares/tests/index.html) | Every test case, its solved sequence, heatmap and recipe comparison |
| [Recipe gallery](https://srpoyrek.github.io/sliding-squares/gallery/index.html) | What each simplification recipe does to corner, edge and junction layouts |
| [BFS comparison](https://srpoyrek.github.io/sliding-squares/benchmark/index.html) | The three searches side by side — charts and per-case tables for states held, execution time and peak memory, the switch-count cross-check, and for each search why it works that way, its algorithm step by step, and what it costs |

CI runs the benchmark with `--repeat 2 --timeout 180`. A shared runner is not a
benchmarking machine, so treat the published timings as indicative; `states` is
exact and reproducible, and the switch-count agreement between the three
searches is the part that must hold.

A pull request gets the verify and build signal without replacing what is live.

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
| `--max-mb` | auto | Ceiling for the whole process tree's resident memory. The run reports its peak against this at the end and flags an overshoot |
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
- [`src/report.py`](src/report.py) — `build_run(...)` / `write_run(...)` encode a solve as `run.json`; `write_local_report(...)` and `write_global_index(...)` render the HTML from it, and `write_site_index(...)` writes the landing page (called by both `make_gallery.py` and `benchmark_bfs.py`, so whichever runs last relinks correctly); `encode_grid`, `encode_sequence` and `palette()` are the pieces `simplify.py` and `render_run.py` reuse.
- [`src/benchmark.py`](src/benchmark.py) — `discover_cases(...)` / `run_benchmark(...)` measure the searches against each other one spawned process at a time, `write_benchmark(...)` / `write_benchmark_report(...)` emit `benchmark.json` and its page. `VARIANTS` and `VARIANT_DOCS` are the single definition of which searches exist and what each one does.
- [`src/bfs.py`](src/bfs.py) — `bfs_mirror` / `bfs_bidirectional` / `bfs` are the three searches, all returning `{switches, path, visited, initial_mover}` so a caller can replay a path without guessing who moves first.
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
