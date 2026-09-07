# Graph Report - .  (2026-09-07)

## Corpus Check
- 46 files · ~27,043 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 404 nodes · 971 edges · 26 communities detected
- Extraction: 50% EXTRACTED · 50% INFERRED · 0% AMBIGUOUS · INFERRED: 483 edges (avg confidence: 0.59)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]

## God Nodes (most connected - your core abstractions)
1. `Workspace` - 84 edges
2. `Grid` - 83 edges
3. `Robot` - 81 edges
4. `LRUCache` - 37 edges
5. `State` - 36 edges
6. `Validator` - 35 edges
7. `Solver` - 33 edges
8. `Canonicalizer` - 22 edges
9. `TestCase` - 22 edges
10. `SpillableSet` - 20 edges

## Surprising Connections (you probably didn't know these)
- `state.py -------- A frozen snapshot of the entire system at one moment.  Use` --uses--> `Robot`  [INFERRED]
  src\state.py → src\robot.py
- `Immutable snapshot of the system.      Fields:         pos_a   : (row, col) o` --uses--> `Robot`  [INFERRED]
  src\state.py → src\robot.py
- `solver.py --------- Uses BFS to find the minimum number of control switches t` --uses--> `Workspace`  [INFERRED]
  src\solver.py → src\workspace.py
- `validator.py ------------ Given a workspace, a path, and goal positions: vali` --uses--> `Workspace`  [INFERRED]
  src\validator.py → src\workspace.py
- `demo_validator.py ----------------- Manual demo for the validator.` --uses--> `Grid`  [INFERRED]
  demo_validator.py → src\grid.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (64): all_adjacent_placements(), all_touching_placements(), blocks_overlap(), build_transform_tables(), canonical_key(), Canonicalizer, is_label_swap_symmetric(), pick_central_placements() (+56 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (50): bfs(), bfs_bidirectional(), _clear_caches(), _cmds_from_parent_map(), configure_caches_for_grid(), _expand_layer(), _expand_one(), flood_fill() (+42 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (28): filter_excluded(), main(), Drop any file whose path contains one of the exclude folder names., assign(), load_results(), main(), Every structured agent return in a workflow run, keyed by agent id., Match each dimension to the agent that cites its files most often.      Greedy a (+20 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (17): _changed_files(), _expand(), _git(), main(), _pack(), Files you're currently working on: tracked changes vs HEAD + new untracked., A plain directory becomes `<dir>/**` so repomix matches the files under it., main() (+9 more)

### Community 4 - "Community 4"
Cohesion: 0.18
Nodes (26): simplify.py ----------- Reusable workspace-simplification pass.  Given a solved, Like the peak keeper, but on each per-face edge also keep enough cells     that, Free every wall the robot can never cross. Mutates `tiles`.      The solver sees, Folder name for one simplification recipe, e.g. "black_peaks_uncrossable"., Fully-wall rows/cols to peel from each side: (top, bottom, left, right).     The, Wall-removal simplification driven by the contact heatmap.      All black walls, Count wall contact at every step, for both robots — including the     initial pl, Run one simplification recipe; save results into     <plot_dir>/simplified/<mode (+18 more)

### Community 5 - "Community 5"
Cohesion: 0.12
Nodes (21): data_path(), get_data_dir(), get_plots_dir(), get_project_root(), get_src_dir(), get_testcases_dir(), plots_path(), directories.py -------- Central place for all project directory paths.  Ever (+13 more)

### Community 6 - "Community 6"
Cohesion: 0.14
Nodes (13): OneByOneNoHoles, 1x1_robot_no_holes.py ------------------- Trivial 1x1 swap with a pocket., 2x2_robot_holes.py ------------------- Test case for a 2x2 robot scenario with, TwoByTwoHoles, 3x3_robot_holes.py ------------------- Test case for a 3x3 robot scenario with, ThreeByThreeHoles, FourByFourHoles, 4x4_robot_holes.py ------------------- Test case for a 4x4 robot scenario with (+5 more)

### Community 7 - "Community 7"
Cohesion: 0.13
Nodes (10): 3x3_robot_no_holes.py ------------------- Test case for a 3x3 robot scenario w, ThreeByThreeNoHoles, FourByFourNoHoles, 4x4_robot_no_holes.py ------------------- Test case for a 4x4 robot scenario w, demo_validator.py ----------------- Manual demo for the validator., An n×n square robot on a grid.     Position is the (row, col) of its top-left c, Robot, Restore robot positions from a State snapshot.         BFS uses this to backtra (+2 more)

### Community 8 - "Community 8"
Cohesion: 0.2
Nodes (9): 2x2_robot_no_holes.py ------------------- Test case for a 2x2 robot scenario w, TwoByTwoNoHoles, Grid, 2D grid of tiles.       0 = free       1 = boundary (perimeter wall)      -1, Set a rectangle of cells as internal holes/islands., Set a rectangle of cells as boundary — same as add_hole but marks as BOUNDARY., Draw the full perimeter of the grid as boundary., Combines a Grid with two robots and enforces movement rules. (+1 more)

### Community 9 - "Community 9"
Cohesion: 0.17
Nodes (6): Is (row, col) within the grid?, Is (row, col) in bounds and not an obstacle?, Is (row, col) a boundary wall?, Is (row, col) an internal hole / island?, Is (row, col) out of bounds or any kind of obstacle?, Would robot fit at (row, col) without hitting any obstacle or wall?         Doe

### Community 10 - "Community 10"
Cohesion: 0.38
Nodes (9): _aggregate_wall_counts(), _count_walls(), _crop_bounds(), mode_name(), _orange_peak_keepers(), _orange_relative_keepers(), _prune_uncrossable(), run_simplification() (+1 more)

### Community 11 - "Community 11"
Cohesion: 0.25
Nodes (7): _build_workspace_from_tiles(), run_tests.py ------------ Discovers all test cases in testcases/ and runs them., Fresh Workspace with the given tile layout, robots at ref_ws's start., Run a single test by class name.      `args` is (cls_name, recipes) where `recip, run_one(), test_case.py ------------ Base class for all test cases. Every test case in t, TestResult

### Community 12 - "Community 12"
Cohesion: 0.29
Nodes (4): PathResolver, path_resolver.py ---------------- Converts compact path strings into flat comm, Convert compact path string(s) to flat command list.          Accepts:, Parse a single segment like '12R2US'.

### Community 13 - "Community 13"
Cohesion: 0.67
Nodes (3): main(), Every survey in ``folder``, concatenated newest-implementation-point first., read_surveys()

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (2): main(), _run()

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (1): Return set of all hole cell positions (row, col).

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (1): Print the raw grid. '.' = free, '#' = boundary, 'O' = hole.

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (1): grid.py ------- The physical environment — a 2D map of free tiles and obstacle

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (1): Return set of all boundary cell positions (row, col).

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (1): Return set of all obstacle positions — both holes and boundaries.

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (1): robot.py -------- A single n×n square robot.  Knows only:   - its label

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): All (row, col) tiles this robot occupies.

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): label : name, e.g. 'A' or 'B'         n     : edge length in tiles         row

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Return an independent copy of this robot.

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (0): 

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **73 isolated node(s):** `Drop any file whose path contains one of the exclude folder names.`, `Every structured agent return in a workflow run, keyed by agent id.`, `Match each dimension to the agent that cites its files most often.      Greedy a`, `How strongly a report belongs to a dimension: citations of its files.`, `One survey report as markdown, findings grouped by file.` (+68 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 15`** (2 nodes): `.get_holes()`, `Return set of all hole cell positions (row, col).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (2 nodes): `.display()`, `Print the raw grid. '.' = free, '#' = boundary, 'O' = hole.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (2 nodes): `grid.py ------- The physical environment — a 2D map of free tiles and obstacle`, `grid.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (2 nodes): `.get_boundaries()`, `Return set of all boundary cell positions (row, col).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (2 nodes): `.get_all_obstacles()`, `Return set of all obstacle positions — both holes and boundaries.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (2 nodes): `robot.py -------- A single n×n square robot.  Knows only:   - its label`, `robot.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (2 nodes): `All (row, col) tiles this robot occupies.`, `.cells()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (2 nodes): `label : name, e.g. 'A' or 'B'         n     : edge length in tiles         row`, `.__init__()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (2 nodes): `Return an independent copy of this robot.`, `.clone()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `demo_solver.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Workspace` connect `Community 4` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 11`?**
  _High betweenness centrality (0.320) - this node is a cross-community bridge._
- **Why does `Grid` connect `Community 8` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 6`, `Community 7`, `Community 9`, `Community 10`, `Community 11`, `Community 15`, `Community 16`, `Community 17`, `Community 18`, `Community 19`?**
  _High betweenness centrality (0.165) - this node is a cross-community bridge._
- **Why does `Robot` connect `Community 7` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 6`, `Community 8`, `Community 9`, `Community 10`, `Community 11`, `Community 20`, `Community 21`, `Community 22`, `Community 23`?**
  _High betweenness centrality (0.142) - this node is a cross-community bridge._
- **Are the 73 inferred relationships involving `Workspace` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `_MemoryMonitor`) actually correct?**
  _`Workspace` has 73 INFERRED edges - model-reasoned connections that need verification._
- **Are the 67 inferred relationships involving `Grid` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `run_tests.py ------------ Discovers all test cases in testcases/ and runs them.`) actually correct?**
  _`Grid` has 67 INFERRED edges - model-reasoned connections that need verification._
- **Are the 72 inferred relationships involving `Robot` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `run_tests.py ------------ Discovers all test cases in testcases/ and runs them.`) actually correct?**
  _`Robot` has 72 INFERRED edges - model-reasoned connections that need verification._
- **Are the 26 inferred relationships involving `LRUCache` (e.g. with `_MemoryMonitor` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`LRUCache` has 26 INFERRED edges - model-reasoned connections that need verification._