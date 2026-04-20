# Graph Report - .  (2026-04-19)

## Corpus Check
- 34 files · ~19,848 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 279 nodes · 676 edges · 21 communities detected
- Extraction: 50% EXTRACTED · 50% INFERRED · 0% AMBIGUOUS · INFERRED: 340 edges (avg confidence: 0.59)
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

## God Nodes (most connected - your core abstractions)
1. `Grid` - 73 edges
2. `Robot` - 70 edges
3. `Workspace` - 67 edges
4. `LRUCache` - 33 edges
5. `Validator` - 31 edges
6. `State` - 30 edges
7. `Solver` - 20 edges
8. `TestCase` - 20 edges
9. `dig_search()` - 16 edges
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
Cohesion: 0.08
Nodes (41): OneByOneNoHoles, 1x1_robot_no_holes.py ------------------- Trivial 1x1 swap with a pocket., 2x2_robot_holes.py ------------------- Test case for a 2x2 robot scenario with, TwoByTwoHoles, 2x2_robot_no_holes.py ------------------- Test case for a 2x2 robot scenario w, TwoByTwoNoHoles, 3x3_robot_holes.py ------------------- Test case for a 3x3 robot scenario with, ThreeByThreeHoles (+33 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (49): _clear_caches(), configure_caches_for_grid(), Resize module-level LRU caches so total memory scales with grid area.      Each, all_adjacent_placements(), all_touching_placements(), _build_cell_bits(), _build_workspace(), _canonical_key() (+41 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (26): bfs(), bfs_bidirectional(), _cmds_from_parent_map(), _expand_layer(), _expand_one(), flood_fill(), _original_flood_fill(), bfs.py ------ Core BFS logic for the sliding squares problem.  Public API:     f (+18 more)

### Community 3 - "Community 3"
Cohesion: 0.22
Nodes (15): filter_excluded(), main(), Drop any file whose path contains one of the exclude folder names., main(), _compute_contact(), _compute_contact_at(), _contact_along_turn(), draw() (+7 more)

### Community 4 - "Community 4"
Cohesion: 0.15
Nodes (17): data_path(), get_data_dir(), get_plots_dir(), get_project_root(), get_src_dir(), get_testcases_dir(), plots_path(), directories.py -------- Central place for all project directory paths.  Ever (+9 more)

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
Cohesion: 0.25
Nodes (7): build_transform_tables(), canonical_key(), is_label_swap_symmetric(), symmetry.py ----------- Spatial symmetry helpers: transform tables, canonical ke, Is there a non-identity spatial transform that:       - leaves the tile layout i, Return (n_kinds, cell_table, pos_table) for an rows*cols grid and n*n robot., Lex-min canonical form over all spatial transforms and both label orderings.

### Community 9 - "Community 9"
Cohesion: 0.4
Nodes (2): solver.py --------- Uses BFS to find the minimum number of control switches t, SolverResult

### Community 10 - "Community 10"
Cohesion: 1.0
Nodes (1): grid.py ------- The physical environment — a 2D map of free tiles and obstacle

### Community 11 - "Community 11"
Cohesion: 1.0
Nodes (1): Return set of all obstacle positions — both holes and boundaries.

### Community 12 - "Community 12"
Cohesion: 1.0
Nodes (1): Print the raw grid. '.' = free, '#' = boundary, 'O' = hole.

### Community 13 - "Community 13"
Cohesion: 1.0
Nodes (1): Return set of all hole cell positions (row, col).

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (1): Return set of all boundary cell positions (row, col).

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (1): All (row, col) tiles this robot occupies.

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (1): robot.py -------- A single n×n square robot.  Knows only:   - its label

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (1): label : name, e.g. 'A' or 'B'         n     : edge length in tiles         row

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (1): Return an independent copy of this robot.

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (0): 

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **42 isolated node(s):** `Drop any file whose path contains one of the exclude folder names.`, `Return paths of .py files staged for commit (any status).`, `directories.py -------- Central place for all project directory paths.  Ever`, `Absolute path to src/ (where this file lives).`, `Absolute path to the project root (one level above src/).` (+37 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 10`** (2 nodes): `grid.py ------- The physical environment — a 2D map of free tiles and obstacle`, `grid.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 11`** (2 nodes): `.get_all_obstacles()`, `Return set of all obstacle positions — both holes and boundaries.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 12`** (2 nodes): `.display()`, `Print the raw grid. '.' = free, '#' = boundary, 'O' = hole.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 13`** (2 nodes): `.get_holes()`, `Return set of all hole cell positions (row, col).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 14`** (2 nodes): `.get_boundaries()`, `Return set of all boundary cell positions (row, col).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (2 nodes): `All (row, col) tiles this robot occupies.`, `.cells()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (2 nodes): `robot.py -------- A single n×n square robot.  Knows only:   - its label`, `robot.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (2 nodes): `label : name, e.g. 'A' or 'B'         n     : edge length in tiles         row`, `.__init__()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (2 nodes): `Return an independent copy of this robot.`, `.clone()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `demo_solver.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Grid` connect `Community 0` to `Community 1`, `Community 2`, `Community 5`, `Community 6`, `Community 7`, `Community 10`, `Community 11`, `Community 12`, `Community 13`, `Community 14`?**
  _High betweenness centrality (0.248) - this node is a cross-community bridge._
- **Why does `Robot` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 5`, `Community 6`, `Community 7`, `Community 15`, `Community 16`, `Community 17`, `Community 18`?**
  _High betweenness centrality (0.204) - this node is a cross-community bridge._
- **Why does `Workspace` connect `Community 0` to `Community 1`, `Community 2`, `Community 5`, `Community 6`, `Community 7`, `Community 9`?**
  _High betweenness centrality (0.202) - this node is a cross-community bridge._
- **Are the 57 inferred relationships involving `Grid` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Grid` has 57 INFERRED edges - model-reasoned connections that need verification._
- **Are the 61 inferred relationships involving `Robot` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Robot` has 61 INFERRED edges - model-reasoned connections that need verification._
- **Are the 57 inferred relationships involving `Workspace` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Workspace` has 57 INFERRED edges - model-reasoned connections that need verification._
- **Are the 23 inferred relationships involving `LRUCache` (e.g. with `find_hardest_workspace.py ------------------------- Self-contained, optimized` and `Incrementally update valid-block-positions after digging one cell.     Only top`) actually correct?**
  _`LRUCache` has 23 INFERRED edges - model-reasoned connections that need verification._