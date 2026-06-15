# Graph Report - .  (2026-06-14)

## Corpus Check
- 35 files · ~22,735 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 322 nodes · 798 edges · 12 communities detected
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

## God Nodes (most connected - your core abstractions)
1. `Grid` - 83 edges
2. `Robot` - 81 edges
3. `Workspace` - 77 edges
4. `Validator` - 39 edges
5. `LRUCache` - 31 edges
6. `State` - 30 edges
7. `Solver` - 27 edges
8. `TestCase` - 22 edges
9. `Canonicalizer` - 19 edges
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
Nodes (38): OneByOneNoHoles, 1x1_robot_no_holes.py ------------------- Trivial 1x1 swap with a pocket., 2x2_robot_holes.py ------------------- Test case for a 2x2 robot scenario with, TwoByTwoHoles, 2x2_robot_no_holes.py ------------------- Test case for a 2x2 robot scenario w, TwoByTwoNoHoles, 3x3_robot_holes.py ------------------- Test case for a 3x3 robot scenario with, ThreeByThreeHoles (+30 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (55): all_adjacent_placements(), all_touching_placements(), blocks_overlap(), build_transform_tables(), canonical_key(), Canonicalizer, is_label_swap_symmetric(), pick_central_placements() (+47 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (36): bfs(), bfs_bidirectional(), _clear_caches(), _cmds_from_parent_map(), configure_caches_for_grid(), _expand_layer(), _expand_one(), flood_fill() (+28 more)

### Community 3 - "Community 3"
Cohesion: 0.1
Nodes (41): main(), _aggregate_wall_counts(), _count_walls(), _crop_bounds(), _orange_peak_keepers(), _orange_relative_keepers(), simplify.py ----------- Reusable workspace-simplification pass.  Given a solved, Like the peak keeper, but on each per-face edge also keep enough cells     that (+33 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (27): data_path(), get_data_dir(), get_plots_dir(), get_project_root(), get_src_dir(), get_testcases_dir(), plots_path(), directories.py -------- Central place for all project directory paths.  Ever (+19 more)

### Community 5 - "Community 5"
Cohesion: 0.14
Nodes (8): main(), Return paths of .py files staged for commit (any status)., staged_python_files(), validator.py ------------ Given a workspace, a path, and goal positions: vali, ValidationResult, Move `robot` one step in `direction` if valid.         Returns True if move was, Would two robots overlap?         Each robot has its own size (n_a, n_b) — they, Can `robot` move one step in `direction`?         Checks: grid fit + no collisi

### Community 6 - "Community 6"
Cohesion: 0.17
Nodes (6): Is (row, col) within the grid?, Is (row, col) in bounds and not an obstacle?, Is (row, col) a boundary wall?, Is (row, col) an internal hole / island?, Is (row, col) out of bounds or any kind of obstacle?, Would robot fit at (row, col) without hitting any obstacle or wall?         Doe

### Community 7 - "Community 7"
Cohesion: 0.22
Nodes (5): demo_validator.py ----------------- Manual demo for the validator., PathResolver, path_resolver.py ---------------- Converts compact path strings into flat comm, Convert compact path string(s) to flat command list.          Accepts:, Parse a single segment like '12R2US'.

### Community 8 - "Community 8"
Cohesion: 0.4
Nodes (2): solver.py --------- Uses BFS to find the minimum number of control switches t, SolverResult

### Community 9 - "Community 9"
Cohesion: 0.67
Nodes (3): filter_excluded(), main(), Drop any file whose path contains one of the exclude folder names.

### Community 10 - "Community 10"
Cohesion: 1.0
Nodes (0): 

### Community 11 - "Community 11"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **55 isolated node(s):** `Drop any file whose path contains one of the exclude folder names.`, `Return paths of .py files staged for commit (any status).`, `canonical.py ------------ Reusable API for robot placements and workspace canoni`, `Return (n_kinds, cell_table, pos_table) for an rows*cols grid and n*n robot.`, `Lex-min canonical form over all spatial transforms and both label orderings.` (+50 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 10`** (1 nodes): `demo_solver.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 11`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Grid` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.236) - this node is a cross-community bridge._
- **Why does `Robot` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.212) - this node is a cross-community bridge._
- **Why does `Workspace` connect `Community 3` to `Community 0`, `Community 1`, `Community 2`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`?**
  _High betweenness centrality (0.191) - this node is a cross-community bridge._
- **Are the 67 inferred relationships involving `Grid` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Grid` has 67 INFERRED edges - model-reasoned connections that need verification._
- **Are the 72 inferred relationships involving `Robot` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Robot` has 72 INFERRED edges - model-reasoned connections that need verification._
- **Are the 67 inferred relationships involving `Workspace` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Workspace` has 67 INFERRED edges - model-reasoned connections that need verification._
- **Are the 35 inferred relationships involving `Validator` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Validator` has 35 INFERRED edges - model-reasoned connections that need verification._