# Graph Report - .  (2026-06-14)

## Corpus Check
- 34 files · ~22,054 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 302 nodes · 790 edges · 16 communities detected
- Extraction: 47% EXTRACTED · 53% INFERRED · 0% AMBIGUOUS · INFERRED: 420 edges (avg confidence: 0.58)
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

## God Nodes (most connected - your core abstractions)
1. `Grid` - 85 edges
2. `Robot` - 84 edges
3. `Workspace` - 79 edges
4. `Validator` - 41 edges
5. `LRUCache` - 34 edges
6. `State` - 30 edges
7. `Solver` - 29 edges
8. `TestCase` - 28 edges
9. `_run_simplification()` - 14 edges
10. `dig_search()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `state.py -------- A frozen snapshot of the entire system at one moment.  Use` --uses--> `Robot`  [INFERRED]
  src\state.py → src\robot.py
- `Immutable snapshot of the system.      Fields:         pos_a   : (row, col) o` --uses--> `Robot`  [INFERRED]
  src\state.py → src\robot.py
- `solver.py --------- Uses BFS to find the minimum number of control switches t` --uses--> `Workspace`  [INFERRED]
  src\solver.py → src\workspace.py
- `demo_validator.py ----------------- Manual demo for the validator.` --uses--> `Grid`  [INFERRED]
  demo_validator.py → src\grid.py
- `demo_validator.py ----------------- Manual demo for the validator.` --uses--> `Robot`  [INFERRED]
  demo_validator.py → src\robot.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (36): bfs(), bfs_bidirectional(), _clear_caches(), _cmds_from_parent_map(), configure_caches_for_grid(), _expand_layer(), _expand_one(), flood_fill() (+28 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (40): all_adjacent_placements(), all_touching_placements(), _build_cell_bits(), _build_workspace(), _canonical_key(), _dedup_placements(), _dig_options_n_strip(), dig_search() (+32 more)

### Community 2 - "Community 2"
Cohesion: 0.13
Nodes (28): validator.py ------------ Given a workspace, a path, and goal positions: vali, ValidationResult, Validator, _compute_contact(), _compute_contact_at(), _contact_along_turn(), draw(), draw_bfs_frontier() (+20 more)

### Community 3 - "Community 3"
Cohesion: 0.12
Nodes (24): main(), Return paths of .py files staged for commit (any status)., staged_python_files(), _aggregate_wall_counts(), _count_walls(), _crop_bounds(), discover_test_cases(), _orange_peak_keepers() (+16 more)

### Community 4 - "Community 4"
Cohesion: 0.14
Nodes (13): 2x2_robot_no_holes.py ------------------- Test case for a 2x2 robot scenario w, TwoByTwoNoHoles, 3x3_robot_holes.py ------------------- Test case for a 3x3 robot scenario with, ThreeByThreeHoles, 3x3_robot_no_holes.py ------------------- Test case for a 3x3 robot scenario w, ThreeByThreeNoHoles, FourByFourHoles, 4x4_robot_holes.py ------------------- Test case for a 4x4 robot scenario with (+5 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (11): robot.py -------- A single n×n square robot.  Knows only:   - its label, An n×n square robot on a grid.     Position is the (row, col) of its top-left c, label : name, e.g. 'A' or 'B'         n     : edge length in tiles         row, All (row, col) tiles this robot occupies., Return an independent copy of this robot., Robot, _build_workspace_from_tiles(), Fresh Workspace with the given tile layout, robots at ref_ws's start. (+3 more)

### Community 6 - "Community 6"
Cohesion: 0.16
Nodes (17): data_path(), get_data_dir(), get_plots_dir(), get_project_root(), get_src_dir(), get_testcases_dir(), plots_path(), directories.py -------- Central place for all project directory paths.  Ever (+9 more)

### Community 7 - "Community 7"
Cohesion: 0.12
Nodes (9): FiveByFiveNoHoles, 5x5_robot_no_holes.py ------------------- Test case for a 5x5 robot scenario w, Grid, grid.py ------- The physical environment — a 2D map of free tiles and obstacle, Print the raw grid. '.' = free, '#' = boundary, 'O' = hole., 2D grid of tiles.       0 = free       1 = boundary (perimeter wall)      -1, Return set of all hole cell positions (row, col)., Return set of all boundary cell positions (row, col). (+1 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (9): Is (row, col) within the grid?, Is (row, col) in bounds and not an obstacle?, Is (row, col) a boundary wall?, Is (row, col) an internal hole / island?, Is (row, col) out of bounds or any kind of obstacle?, Move `robot` one step in `direction` if valid.         Returns True if move was, Would robot fit at (row, col) without hitting any obstacle or wall?         Doe, Would two robots overlap?         Each robot has its own size (n_a, n_b) — they (+1 more)

### Community 9 - "Community 9"
Cohesion: 0.22
Nodes (5): 2x2_robot_holes.py ------------------- Test case for a 2x2 robot scenario with, TwoByTwoHoles, Set a rectangle of cells as internal holes/islands., Set a rectangle of cells as boundary — same as add_hole but marks as BOUNDARY., Draw the full perimeter of the grid as boundary.

### Community 10 - "Community 10"
Cohesion: 0.22
Nodes (5): demo_validator.py ----------------- Manual demo for the validator., PathResolver, path_resolver.py ---------------- Converts compact path strings into flat comm, Convert compact path string(s) to flat command list.          Accepts:, Parse a single segment like '12R2US'.

### Community 11 - "Community 11"
Cohesion: 0.38
Nodes (4): filter_excluded(), main(), Drop any file whose path contains one of the exclude folder names., main()

### Community 12 - "Community 12"
Cohesion: 0.33
Nodes (5): canonical_key(), is_label_swap_symmetric(), symmetry.py ----------- Spatial symmetry helpers: transform tables, canonical ke, Is there a non-identity spatial transform that:       - leaves the tile layout i, Lex-min canonical form over all spatial transforms and both label orderings.

### Community 13 - "Community 13"
Cohesion: 0.5
Nodes (2): OneByOneNoHoles, 1x1_robot_no_holes.py ------------------- Trivial 1x1 swap with a pocket.

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (0): 

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **42 isolated node(s):** `Drop any file whose path contains one of the exclude folder names.`, `Return paths of .py files staged for commit (any status).`, `directories.py -------- Central place for all project directory paths.  Ever`, `Absolute path to src/ (where this file lives).`, `Absolute path to the project root (one level above src/).` (+37 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 14`** (1 nodes): `demo_solver.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Grid` connect `Community 7` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 8`, `Community 9`, `Community 10`, `Community 13`?**
  _High betweenness centrality (0.242) - this node is a cross-community bridge._
- **Why does `Robot` connect `Community 5` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 13`?**
  _High betweenness centrality (0.219) - this node is a cross-community bridge._
- **Why does `Workspace` connect `Community 2` to `Community 0`, `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 13`?**
  _High betweenness centrality (0.196) - this node is a cross-community bridge._
- **Are the 69 inferred relationships involving `Grid` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Grid` has 69 INFERRED edges - model-reasoned connections that need verification._
- **Are the 75 inferred relationships involving `Robot` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Robot` has 75 INFERRED edges - model-reasoned connections that need verification._
- **Are the 69 inferred relationships involving `Workspace` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Workspace` has 69 INFERRED edges - model-reasoned connections that need verification._
- **Are the 37 inferred relationships involving `Validator` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Validator` has 37 INFERRED edges - model-reasoned connections that need verification._