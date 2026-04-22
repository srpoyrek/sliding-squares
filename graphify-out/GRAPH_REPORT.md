# Graph Report - .  (2026-04-22)

## Corpus Check
- 34 files · ~19,845 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 285 nodes · 691 edges · 16 communities detected
- Extraction: 50% EXTRACTED · 50% INFERRED · 0% AMBIGUOUS · INFERRED: 346 edges (avg confidence: 0.58)
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
1. `Grid` - 74 edges
2. `Robot` - 71 edges
3. `Workspace` - 68 edges
4. `LRUCache` - 35 edges
5. `Validator` - 32 edges
6. `State` - 30 edges
7. `Solver` - 21 edges
8. `TestCase` - 20 edges
9. `dig_search()` - 13 edges
10. `_plot_proof()` - 11 edges

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
Cohesion: 0.07
Nodes (36): bfs(), bfs_bidirectional(), _clear_caches(), _cmds_from_parent_map(), configure_caches_for_grid(), _expand_layer(), _expand_one(), flood_fill() (+28 more)

### Community 1 - "Community 1"
Cohesion: 0.09
Nodes (40): all_adjacent_placements(), all_touching_placements(), _build_cell_bits(), _build_workspace(), _canonical_key(), _dedup_placements(), _dig_options_n_strip(), dig_search() (+32 more)

### Community 2 - "Community 2"
Cohesion: 0.12
Nodes (27): filter_excluded(), main(), Drop any file whose path contains one of the exclude folder names., main(), Validator, _compute_contact(), _compute_contact_at(), _contact_along_turn() (+19 more)

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (12): 3x3_robot_holes.py ------------------- Test case for a 3x3 robot scenario with, ThreeByThreeHoles, Grid, grid.py ------- The physical environment — a 2D map of free tiles and obstacle, Print the raw grid. '.' = free, '#' = boundary, 'O' = hole., 2D grid of tiles.       0 = free       1 = boundary (perimeter wall)      -1, Set a rectangle of cells as internal holes/islands., Set a rectangle of cells as boundary — same as add_hole but marks as BOUNDARY. (+4 more)

### Community 4 - "Community 4"
Cohesion: 0.1
Nodes (22): data_path(), get_data_dir(), get_plots_dir(), get_project_root(), get_src_dir(), get_testcases_dir(), plots_path(), directories.py -------- Central place for all project directory paths.  Ever (+14 more)

### Community 5 - "Community 5"
Cohesion: 0.13
Nodes (8): FiveByFiveNoHoles, 5x5_robot_no_holes.py ------------------- Test case for a 5x5 robot scenario w, robot.py -------- A single n×n square robot.  Knows only:   - its label, An n×n square robot on a grid.     Position is the (row, col) of its top-left c, label : name, e.g. 'A' or 'B'         n     : edge length in tiles         row, All (row, col) tiles this robot occupies., Return an independent copy of this robot., Robot

### Community 6 - "Community 6"
Cohesion: 0.17
Nodes (11): 2x2_robot_holes.py ------------------- Test case for a 2x2 robot scenario with, TwoByTwoHoles, 2x2_robot_no_holes.py ------------------- Test case for a 2x2 robot scenario w, TwoByTwoNoHoles, FourByFourHoles, 4x4_robot_holes.py ------------------- Test case for a 4x4 robot scenario with, FourByFourNoHoles, 4x4_robot_no_holes.py ------------------- Test case for a 4x4 robot scenario w (+3 more)

### Community 7 - "Community 7"
Cohesion: 0.14
Nodes (8): main(), Return paths of .py files staged for commit (any status)., staged_python_files(), validator.py ------------ Given a workspace, a path, and goal positions: vali, ValidationResult, Move `robot` one step in `direction` if valid.         Returns True if move was, Would two robots overlap?         Each robot has its own size (n_a, n_b) — they, Can `robot` move one step in `direction`?         Checks: grid fit + no collisi

### Community 8 - "Community 8"
Cohesion: 0.2
Nodes (7): 3x3_robot_no_holes.py ------------------- Test case for a 3x3 robot scenario w, ThreeByThreeNoHoles, N-aware topology check (tight): swap is feasible only if the component     of `, workspace.py ------------ The grid + both robots + all movement rules.  Owns, Restore robot positions from a State snapshot.         BFS uses this to backtra, Combines a Grid with two robots and enforces movement rules., Workspace

### Community 9 - "Community 9"
Cohesion: 0.17
Nodes (6): Is (row, col) within the grid?, Is (row, col) in bounds and not an obstacle?, Is (row, col) a boundary wall?, Is (row, col) an internal hole / island?, Is (row, col) out of bounds or any kind of obstacle?, Would robot fit at (row, col) without hitting any obstacle or wall?         Doe

### Community 10 - "Community 10"
Cohesion: 0.22
Nodes (5): demo_validator.py ----------------- Manual demo for the validator., PathResolver, path_resolver.py ---------------- Converts compact path strings into flat comm, Convert compact path string(s) to flat command list.          Accepts:, Parse a single segment like '12R2US'.

### Community 11 - "Community 11"
Cohesion: 0.33
Nodes (5): canonical_key(), is_label_swap_symmetric(), symmetry.py ----------- Spatial symmetry helpers: transform tables, canonical ke, Is there a non-identity spatial transform that:       - leaves the tile layout i, Lex-min canonical form over all spatial transforms and both label orderings.

### Community 12 - "Community 12"
Cohesion: 0.4
Nodes (2): solver.py --------- Uses BFS to find the minimum number of control switches t, SolverResult

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

- **Why does `Grid` connect `Community 3` to `Community 0`, `Community 1`, `Community 2`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 13`?**
  _High betweenness centrality (0.246) - this node is a cross-community bridge._
- **Why does `Robot` connect `Community 5` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 13`?**
  _High betweenness centrality (0.203) - this node is a cross-community bridge._
- **Why does `Workspace` connect `Community 8` to `Community 0`, `Community 1`, `Community 2`, `Community 3`, `Community 5`, `Community 6`, `Community 7`, `Community 9`, `Community 10`, `Community 12`, `Community 13`?**
  _High betweenness centrality (0.200) - this node is a cross-community bridge._
- **Are the 58 inferred relationships involving `Grid` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Grid` has 58 INFERRED edges - model-reasoned connections that need verification._
- **Are the 62 inferred relationships involving `Robot` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Robot` has 62 INFERRED edges - model-reasoned connections that need verification._
- **Are the 58 inferred relationships involving `Workspace` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Workspace` has 58 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `LRUCache` (e.g. with `find_hardest_workspace.py ------------------------- Self-contained, optimized` and `Incrementally update valid-block-positions after digging one cell.     Only top`) actually correct?**
  _`LRUCache` has 25 INFERRED edges - model-reasoned connections that need verification._