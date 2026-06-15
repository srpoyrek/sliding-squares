# Graph Report - .  (2026-06-14)

## Corpus Check
- 36 files · ~23,370 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 330 nodes · 791 edges · 19 communities detected
- Extraction: 49% EXTRACTED · 51% INFERRED · 0% AMBIGUOUS · INFERRED: 405 edges (avg confidence: 0.59)
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

## God Nodes (most connected - your core abstractions)
1. `Grid` - 80 edges
2. `Robot` - 78 edges
3. `Workspace` - 77 edges
4. `Solver` - 39 edges
5. `State` - 34 edges
6. `Validator` - 32 edges
7. `LRUCache` - 30 edges
8. `TestCase` - 22 edges
9. `Canonicalizer` - 18 edges
10. `run_simplification()` - 13 edges

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
Cohesion: 0.06
Nodes (44): all_adjacent_placements(), all_touching_placements(), blocks_overlap(), build_transform_tables(), canonical_key(), Canonicalizer, is_label_swap_symmetric(), pick_central_placements() (+36 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (36): bfs(), bfs_bidirectional(), _clear_caches(), _cmds_from_parent_map(), configure_caches_for_grid(), _expand_layer(), _expand_one(), flood_fill() (+28 more)

### Community 2 - "Community 2"
Cohesion: 0.09
Nodes (32): Worker function: rebuild workspace and run solver.     Used by the batch-parall, _solve_payload(), run_tests.py ------------ Discovers all test cases in testcases/ and runs them., Fresh Workspace with the given tile layout, robots at ref_ws's start., Run a single test by class name.      `args` is (cls_name, simplified, remove_al, run_one(), _aggregate_wall_counts(), _count_walls() (+24 more)

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (26): filter_excluded(), main(), Drop any file whose path contains one of the exclude folder names., main(), _compute_contact(), _compute_contact_at(), _contact_along_turn(), draw() (+18 more)

### Community 4 - "Community 4"
Cohesion: 0.12
Nodes (21): data_path(), get_data_dir(), get_plots_dir(), get_project_root(), get_src_dir(), get_testcases_dir(), plots_path(), directories.py -------- Central place for all project directory paths.  Ever (+13 more)

### Community 5 - "Community 5"
Cohesion: 0.12
Nodes (10): FiveByFiveNoHoles, 5x5_robot_no_holes.py ------------------- Test case for a 5x5 robot scenario w, robot.py -------- A single n×n square robot.  Knows only:   - its label, An n×n square robot on a grid.     Position is the (row, col) of its top-left c, label : name, e.g. 'A' or 'B'         n     : edge length in tiles         row, All (row, col) tiles this robot occupies., Return an independent copy of this robot., Robot (+2 more)

### Community 6 - "Community 6"
Cohesion: 0.11
Nodes (9): Is (row, col) within the grid?, Is (row, col) in bounds and not an obstacle?, Is (row, col) a boundary wall?, Is (row, col) an internal hole / island?, Is (row, col) out of bounds or any kind of obstacle?, Would robot fit at (row, col) without hitting any obstacle or wall?         Doe, Would two robots overlap?         Each robot has its own size (n_a, n_b) — they, Can `robot` move one step in `direction`?         Checks: grid fit + no collisi (+1 more)

### Community 7 - "Community 7"
Cohesion: 0.17
Nodes (11): 2x2_robot_holes.py ------------------- Test case for a 2x2 robot scenario with, TwoByTwoHoles, 3x3_robot_holes.py ------------------- Test case for a 3x3 robot scenario with, ThreeByThreeHoles, 3x3_robot_no_holes.py ------------------- Test case for a 3x3 robot scenario w, ThreeByThreeNoHoles, FourByFourHoles, 4x4_robot_holes.py ------------------- Test case for a 4x4 robot scenario with (+3 more)

### Community 8 - "Community 8"
Cohesion: 0.13
Nodes (8): Grid, grid.py ------- The physical environment — a 2D map of free tiles and obstacle, Print the raw grid. '.' = free, '#' = boundary, 'O' = hole., 2D grid of tiles.       0 = free       1 = boundary (perimeter wall)      -1, Return set of all hole cell positions (row, col)., Return set of all boundary cell positions (row, col)., Return set of all obstacle positions — both holes and boundaries., All top-left positions where an n*n block fits entirely in free_cells.

### Community 9 - "Community 9"
Cohesion: 0.2
Nodes (6): FourByFourNoHoles, 4x4_robot_no_holes.py ------------------- Test case for a 4x4 robot scenario w, Restore robot positions from a State snapshot.         BFS uses this to backtra, Combines a Grid with two robots and enforces movement rules., The set of free (non-obstacle) cells in this workspace's grid., Workspace

### Community 10 - "Community 10"
Cohesion: 0.22
Nodes (5): demo_validator.py ----------------- Manual demo for the validator., PathResolver, path_resolver.py ---------------- Converts compact path strings into flat comm, Convert compact path string(s) to flat command list.          Accepts:, Parse a single segment like '12R2US'.

### Community 11 - "Community 11"
Cohesion: 0.33
Nodes (3): Set a rectangle of cells as internal holes/islands., Set a rectangle of cells as boundary — same as add_hole but marks as BOUNDARY., Draw the full perimeter of the grid as boundary.

### Community 12 - "Community 12"
Cohesion: 0.33
Nodes (5): extend_frontier(), initial_frontier(), frontier.py ----------- Frontier helpers for grow / dig searches over a free-cel, Obstacle cells orthogonally adjacent to the free region., Frontier after `dug_cell` becomes free: drop it, add its still-blocked     ortho

### Community 13 - "Community 13"
Cohesion: 0.4
Nodes (2): from_free_cells(), workspace.py ------------ The grid + both robots + all movement rules.  Owns

### Community 14 - "Community 14"
Cohesion: 0.67
Nodes (3): main(), Return paths of .py files staged for commit (any status)., staged_python_files()

### Community 15 - "Community 15"
Cohesion: 0.5
Nodes (2): 2x2_robot_no_holes.py ------------------- Test case for a 2x2 robot scenario w, TwoByTwoNoHoles

### Community 16 - "Community 16"
Cohesion: 0.5
Nodes (2): OneByOneNoHoles, 1x1_robot_no_holes.py ------------------- Trivial 1x1 swap with a pocket.

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (0): 

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **58 isolated node(s):** `Drop any file whose path contains one of the exclude folder names.`, `Return paths of .py files staged for commit (any status).`, `canonical.py ------------ Reusable API for robot placements and workspace canoni`, `Return (n_kinds, cell_table, pos_table) for an rows*cols grid and n*n robot.`, `Lex-min canonical form over all spatial transforms and both label orderings.` (+53 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 17`** (1 nodes): `demo_solver.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Workspace` connect `Community 9` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 10`, `Community 11`, `Community 13`, `Community 15`, `Community 16`?**
  _High betweenness centrality (0.303) - this node is a cross-community bridge._
- **Why does `Grid` connect `Community 8` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 9`, `Community 10`, `Community 11`, `Community 13`, `Community 15`, `Community 16`?**
  _High betweenness centrality (0.192) - this node is a cross-community bridge._
- **Why does `Robot` connect `Community 5` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 11`, `Community 13`, `Community 15`, `Community 16`?**
  _High betweenness centrality (0.175) - this node is a cross-community bridge._
- **Are the 64 inferred relationships involving `Grid` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `run_tests.py ------------ Discovers all test cases in testcases/ and runs them.`) actually correct?**
  _`Grid` has 64 INFERRED edges - model-reasoned connections that need verification._
- **Are the 69 inferred relationships involving `Robot` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `run_tests.py ------------ Discovers all test cases in testcases/ and runs them.`) actually correct?**
  _`Robot` has 69 INFERRED edges - model-reasoned connections that need verification._
- **Are the 66 inferred relationships involving `Workspace` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Workspace` has 66 INFERRED edges - model-reasoned connections that need verification._
- **Are the 36 inferred relationships involving `Solver` (e.g. with `find_hardest_workspace.py ------------------------- Self-contained, optimized` and `Worker function: rebuild workspace and run solver.     Used by the batch-parall`) actually correct?**
  _`Solver` has 36 INFERRED edges - model-reasoned connections that need verification._