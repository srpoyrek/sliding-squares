# Graph Report - .  (2026-04-19)

## Corpus Check
- 33 files · ~19,724 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 261 nodes · 616 edges · 18 communities detected
- Extraction: 51% EXTRACTED · 49% INFERRED · 0% AMBIGUOUS · INFERRED: 300 edges (avg confidence: 0.58)
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

## God Nodes (most connected - your core abstractions)
1. `Grid` - 73 edges
2. `Robot` - 70 edges
3. `Workspace` - 67 edges
4. `Validator` - 31 edges
5. `State` - 28 edges
6. `Solver` - 20 edges
7. `TestCase` - 20 edges
8. `dig_search()` - 12 edges
9. `_plot_proof()` - 11 edges
10. `run_one()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `state.py -------- A frozen snapshot of the entire system at one moment.  Use` --uses--> `Robot`  [INFERRED]
  src\state.py → src\robot.py
- `Immutable snapshot of the system.      Fields:         pos_a   : (row, col) o` --uses--> `Robot`  [INFERRED]
  src\state.py → src\robot.py
- `demo_validator.py ----------------- Manual demo for the validator.` --uses--> `Grid`  [INFERRED]
  demo_validator.py → src\grid.py
- `demo_validator.py ----------------- Manual demo for the validator.` --uses--> `Robot`  [INFERRED]
  demo_validator.py → src\robot.py
- `demo_validator.py ----------------- Manual demo for the validator.` --uses--> `Validator`  [INFERRED]
  demo_validator.py → src\validator.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.1
Nodes (20): _dig_options_n_strip(), find_hardest_workspace.py ------------------------- Self-contained, optimized, Worker function: rebuild workspace and run solver.     Used by the batch-parall, Precompute, per cell, the bit-position values under each transform., Build and set module-level transform tables. Called once in main process., Assign pre-built transform tables in worker processes (no recomputation)., Canonical key from a precomputed transforms_free tuple and per-transform     ti, Yield 1×n or n×1 strips that extend the valid region by one robot step.      F (+12 more)

### Community 1 - "Community 1"
Cohesion: 0.11
Nodes (25): bfs(), bfs_bidirectional(), _clear_caches(), _cmds_from_parent_map(), _expand_layer(), _expand_one(), flood_fill(), _original_flood_fill() (+17 more)

### Community 2 - "Community 2"
Cohesion: 0.12
Nodes (28): all_adjacent_placements(), all_touching_placements(), _build_cell_bits(), _build_workspace(), _canonical_key(), _dedup_placements(), dig_search(), _extend_frontier() (+20 more)

### Community 3 - "Community 3"
Cohesion: 0.1
Nodes (22): data_path(), get_data_dir(), get_plots_dir(), get_project_root(), get_src_dir(), get_testcases_dir(), plots_path(), directories.py -------- Central place for all project directory paths.  Ever (+14 more)

### Community 4 - "Community 4"
Cohesion: 0.16
Nodes (23): Validator, _compute_contact(), _compute_contact_at(), _contact_along_turn(), draw(), draw_bfs_frontier(), draw_blocker_heatmap(), _draw_face_highlight() (+15 more)

### Community 5 - "Community 5"
Cohesion: 0.11
Nodes (11): 3x3_robot_no_holes.py ------------------- Test case for a 3x3 robot scenario w, ThreeByThreeNoHoles, Grid, grid.py ------- The physical environment — a 2D map of free tiles and obstacle, Print the raw grid. '.' = free, '#' = boundary, 'O' = hole., 2D grid of tiles.       0 = free       1 = boundary (perimeter wall)      -1, Return set of all hole cell positions (row, col)., Return set of all boundary cell positions (row, col). (+3 more)

### Community 6 - "Community 6"
Cohesion: 0.15
Nodes (13): 2x2_robot_holes.py ------------------- Test case for a 2x2 robot scenario with, TwoByTwoHoles, 3x3_robot_holes.py ------------------- Test case for a 3x3 robot scenario with, ThreeByThreeHoles, FourByFourHoles, 4x4_robot_holes.py ------------------- Test case for a 4x4 robot scenario with, FourByFourNoHoles, 4x4_robot_no_holes.py ------------------- Test case for a 4x4 robot scenario w (+5 more)

### Community 7 - "Community 7"
Cohesion: 0.1
Nodes (11): robot.py -------- A single n×n square robot.  Knows only:   - its label, An n×n square robot on a grid.     Position is the (row, col) of its top-left c, label : name, e.g. 'A' or 'B'         n     : edge length in tiles         row, All (row, col) tiles this robot occupies., Return an independent copy of this robot., Robot, workspace.py ------------ The grid + both robots + all movement rules.  Owns, Restore robot positions from a State snapshot.         BFS uses this to backtra (+3 more)

### Community 8 - "Community 8"
Cohesion: 0.2
Nodes (5): Is (row, col) within the grid?, Is (row, col) in bounds and not an obstacle?, Is (row, col) a boundary wall?, Is (row, col) an internal hole / island?, Is (row, col) out of bounds or any kind of obstacle?

### Community 9 - "Community 9"
Cohesion: 0.22
Nodes (5): demo_validator.py ----------------- Manual demo for the validator., PathResolver, path_resolver.py ---------------- Converts compact path strings into flat comm, Convert compact path string(s) to flat command list.          Accepts:, Parse a single segment like '12R2US'.

### Community 10 - "Community 10"
Cohesion: 0.33
Nodes (3): Set a rectangle of cells as internal holes/islands., Set a rectangle of cells as boundary — same as add_hole but marks as BOUNDARY., Draw the full perimeter of the grid as boundary.

### Community 11 - "Community 11"
Cohesion: 0.67
Nodes (3): filter_excluded(), main(), Drop any file whose path contains one of the exclude folder names.

### Community 12 - "Community 12"
Cohesion: 0.67
Nodes (3): main(), Return paths of .py files staged for commit (any status)., staged_python_files()

### Community 13 - "Community 13"
Cohesion: 0.5
Nodes (2): 2x2_robot_no_holes.py ------------------- Test case for a 2x2 robot scenario w, TwoByTwoNoHoles

### Community 14 - "Community 14"
Cohesion: 0.5
Nodes (2): OneByOneNoHoles, 1x1_robot_no_holes.py ------------------- Trivial 1x1 swap with a pocket.

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (0): 

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (0): 

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **40 isolated node(s):** `Drop any file whose path contains one of the exclude folder names.`, `Return paths of .py files staged for commit (any status).`, `directories.py -------- Central place for all project directory paths.  Ever`, `Absolute path to src/ (where this file lives).`, `Absolute path to the project root (one level above src/).` (+35 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 15`** (2 nodes): `main()`, `list_communities.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (1 nodes): `demo_solver.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Grid` connect `Community 5` to `Community 0`, `Community 1`, `Community 2`, `Community 4`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 13`, `Community 14`?**
  _High betweenness centrality (0.254) - this node is a cross-community bridge._
- **Why does `Workspace` connect `Community 0` to `Community 1`, `Community 2`, `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 9`, `Community 10`, `Community 13`, `Community 14`?**
  _High betweenness centrality (0.226) - this node is a cross-community bridge._
- **Why does `Robot` connect `Community 7` to `Community 0`, `Community 1`, `Community 2`, `Community 4`, `Community 5`, `Community 6`, `Community 9`, `Community 10`, `Community 13`, `Community 14`?**
  _High betweenness centrality (0.222) - this node is a cross-community bridge._
- **Are the 57 inferred relationships involving `Grid` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Grid` has 57 INFERRED edges - model-reasoned connections that need verification._
- **Are the 61 inferred relationships involving `Robot` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Robot` has 61 INFERRED edges - model-reasoned connections that need verification._
- **Are the 57 inferred relationships involving `Workspace` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Workspace` has 57 INFERRED edges - model-reasoned connections that need verification._
- **Are the 27 inferred relationships involving `Validator` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Validator` has 27 INFERRED edges - model-reasoned connections that need verification._