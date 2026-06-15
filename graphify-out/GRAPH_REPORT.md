# Graph Report - .  (2026-06-14)

## Corpus Check
- 37 files · ~24,172 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 362 nodes · 880 edges · 13 communities detected
- Extraction: 49% EXTRACTED · 51% INFERRED · 0% AMBIGUOUS · INFERRED: 446 edges (avg confidence: 0.58)
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

## God Nodes (most connected - your core abstractions)
1. `Workspace` - 82 edges
2. `Grid` - 81 edges
3. `Robot` - 79 edges
4. `Solver` - 44 edges
5. `LRUCache` - 36 edges
6. `State` - 35 edges
7. `Validator` - 33 edges
8. `Canonicalizer` - 22 edges
9. `TestCase` - 22 edges
10. `MemoryGuard` - 18 edges

## Surprising Connections (you probably didn't know these)
- `Immutable snapshot of the system.      Fields:         pos_a   : (row, col) o` --uses--> `Robot`  [INFERRED]
  src\state.py → src\robot.py
- `solver.py --------- Uses BFS to find the minimum number of control switches t` --uses--> `Workspace`  [INFERRED]
  src\solver.py → src\workspace.py
- `validator.py ------------ Given a workspace, a path, and goal positions: vali` --uses--> `Workspace`  [INFERRED]
  src\validator.py → src\workspace.py
- `demo_validator.py ----------------- Manual demo for the validator.` --uses--> `Grid`  [INFERRED]
  demo_validator.py → src\grid.py
- `demo_validator.py ----------------- Manual demo for the validator.` --uses--> `Robot`  [INFERRED]
  demo_validator.py → src\robot.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (46): OneByOneNoHoles, 1x1_robot_no_holes.py ------------------- Trivial 1x1 swap with a pocket., 2x2_robot_holes.py ------------------- Test case for a 2x2 robot scenario with, TwoByTwoHoles, 2x2_robot_no_holes.py ------------------- Test case for a 2x2 robot scenario w, TwoByTwoNoHoles, 3x3_robot_holes.py ------------------- Test case for a 3x3 robot scenario with, ThreeByThreeHoles (+38 more)

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (60): all_adjacent_placements(), all_touching_placements(), blocks_overlap(), build_transform_tables(), canonical_key(), Canonicalizer, is_label_swap_symmetric(), pick_central_placements() (+52 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (55): Worker function: rebuild workspace and run solver.     Used by the batch-parall, _solve_payload(), main(), main(), Return paths of .py files staged for commit (any status)., staged_python_files(), run_tests.py ------------ Discovers all test cases in testcases/ and runs them., Fresh Workspace with the given tile layout, robots at ref_ws's start. (+47 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (38): bfs(), bfs_bidirectional(), _clear_caches(), _cmds_from_parent_map(), configure_caches_for_grid(), _expand_layer(), _expand_one(), flood_fill() (+30 more)

### Community 4 - "Community 4"
Cohesion: 0.12
Nodes (21): data_path(), get_data_dir(), get_plots_dir(), get_project_root(), get_src_dir(), get_testcases_dir(), plots_path(), directories.py -------- Central place for all project directory paths.  Ever (+13 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (9): Is (row, col) within the grid?, Is (row, col) in bounds and not an obstacle?, Is (row, col) a boundary wall?, Is (row, col) an internal hole / island?, Is (row, col) out of bounds or any kind of obstacle?, Would robot fit at (row, col) without hitting any obstacle or wall?         Doe, Would two robots overlap?         Each robot has its own size (n_a, n_b) — they, Can `robot` move one step in `direction`?         Checks: grid fit + no collisi (+1 more)

### Community 6 - "Community 6"
Cohesion: 0.22
Nodes (5): demo_validator.py ----------------- Manual demo for the validator., PathResolver, path_resolver.py ---------------- Converts compact path strings into flat comm, Convert compact path string(s) to flat command list.          Accepts:, Parse a single segment like '12R2US'.

### Community 7 - "Community 7"
Cohesion: 0.33
Nodes (5): extend_frontier(), initial_frontier(), frontier.py ----------- Frontier helpers for grow / dig searches over a free-cel, Obstacle cells orthogonally adjacent to the free region., Frontier after `dug_cell` becomes free: drop it, add its still-blocked     ortho

### Community 8 - "Community 8"
Cohesion: 0.4
Nodes (2): solver.py --------- Uses BFS to find the minimum number of control switches t, SolverResult

### Community 9 - "Community 9"
Cohesion: 0.4
Nodes (2): validator.py ------------ Given a workspace, a path, and goal positions: vali, ValidationResult

### Community 10 - "Community 10"
Cohesion: 0.67
Nodes (3): filter_excluded(), main(), Drop any file whose path contains one of the exclude folder names.

### Community 11 - "Community 11"
Cohesion: 1.0
Nodes (0): 

### Community 12 - "Community 12"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **65 isolated node(s):** `Drop any file whose path contains one of the exclude folder names.`, `Return paths of .py files staged for commit (any status).`, `canonical.py ------------ Reusable API for robot placements and workspace canoni`, `Return (n_kinds, cell_table, pos_table) for an rows*cols grid and n*n robot.`, `Lex-min canonical form over all spatial transforms and both label orderings.` (+60 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 11`** (1 nodes): `demo_solver.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 12`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Workspace` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 8`, `Community 9`?**
  _High betweenness centrality (0.324) - this node is a cross-community bridge._
- **Why does `Grid` connect `Community 0` to `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`?**
  _High betweenness centrality (0.172) - this node is a cross-community bridge._
- **Why does `Robot` connect `Community 0` to `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 6`?**
  _High betweenness centrality (0.155) - this node is a cross-community bridge._
- **Are the 71 inferred relationships involving `Workspace` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `_MemoryMonitor`) actually correct?**
  _`Workspace` has 71 INFERRED edges - model-reasoned connections that need verification._
- **Are the 65 inferred relationships involving `Grid` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `run_tests.py ------------ Discovers all test cases in testcases/ and runs them.`) actually correct?**
  _`Grid` has 65 INFERRED edges - model-reasoned connections that need verification._
- **Are the 70 inferred relationships involving `Robot` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `run_tests.py ------------ Discovers all test cases in testcases/ and runs them.`) actually correct?**
  _`Robot` has 70 INFERRED edges - model-reasoned connections that need verification._
- **Are the 41 inferred relationships involving `Solver` (e.g. with `_MemoryMonitor` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Solver` has 41 INFERRED edges - model-reasoned connections that need verification._