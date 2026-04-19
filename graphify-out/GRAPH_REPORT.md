# Graph Report - .  (2026-04-19)

## Corpus Check
- 33 files · ~19,735 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 263 nodes · 641 edges · 12 communities detected
- Extraction: 49% EXTRACTED · 51% INFERRED · 0% AMBIGUOUS · INFERRED: 324 edges (avg confidence: 0.58)
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
1. `Grid` - 78 edges
2. `Robot` - 74 edges
3. `Workspace` - 71 edges
4. `Validator` - 34 edges
5. `State` - 28 edges
6. `Solver` - 24 edges
7. `TestCase` - 23 edges
8. `dig_search()` - 12 edges
9. `_plot_proof()` - 11 edges
10. `run_one()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `state.py -------- A frozen snapshot of the entire system at one moment.  Use` --uses--> `Robot`  [INFERRED]
  src\state.py → src\robot.py
- `Immutable snapshot of the system.      Fields:         pos_a   : (row, col) o` --uses--> `Robot`  [INFERRED]
  src\state.py → src\robot.py
- `validator.py ------------ Given a workspace, a path, and goal positions: vali` --uses--> `Workspace`  [INFERRED]
  src\validator.py → src\workspace.py
- `demo_validator.py ----------------- Manual demo for the validator.` --uses--> `Grid`  [INFERRED]
  demo_validator.py → src\grid.py
- `demo_validator.py ----------------- Manual demo for the validator.` --uses--> `Robot`  [INFERRED]
  demo_validator.py → src\robot.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (29): OneByOneNoHoles, 1x1_robot_no_holes.py ------------------- Trivial 1x1 swap with a pocket., 2x2_robot_holes.py ------------------- Test case for a 2x2 robot scenario with, TwoByTwoHoles, 2x2_robot_no_holes.py ------------------- Test case for a 2x2 robot scenario w, TwoByTwoNoHoles, 3x3_robot_holes.py ------------------- Test case for a 3x3 robot scenario with, ThreeByThreeHoles (+21 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (30): FourByFourNoHoles, 4x4_robot_no_holes.py ------------------- Test case for a 4x4 robot scenario w, _dig_options_n_strip(), find_hardest_workspace.py ------------------------- Self-contained, optimized, Worker function: rebuild workspace and run solver.     Used by the batch-parall, Precompute, per cell, the bit-position values under each transform., Build and set module-level transform tables. Called once in main process., Assign pre-built transform tables in worker processes (no recomputation). (+22 more)

### Community 2 - "Community 2"
Cohesion: 0.1
Nodes (26): bfs(), bfs_bidirectional(), _clear_caches(), _cmds_from_parent_map(), _expand_layer(), _expand_one(), flood_fill(), _original_flood_fill() (+18 more)

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (29): all_adjacent_placements(), all_touching_placements(), _build_cell_bits(), _build_workspace(), _canonical_key(), _dedup_placements(), dig_search(), _extend_frontier() (+21 more)

### Community 4 - "Community 4"
Cohesion: 0.12
Nodes (26): run_one(), validator.py ------------ Given a workspace, a path, and goal positions: vali, ValidationResult, Validator, _compute_contact(), _compute_contact_at(), _contact_along_turn(), draw() (+18 more)

### Community 5 - "Community 5"
Cohesion: 0.1
Nodes (22): data_path(), get_data_dir(), get_plots_dir(), get_project_root(), get_src_dir(), get_testcases_dir(), plots_path(), directories.py -------- Central place for all project directory paths.  Ever (+14 more)

### Community 6 - "Community 6"
Cohesion: 0.12
Nodes (8): Is (row, col) within the grid?, Is (row, col) in bounds and not an obstacle?, Is (row, col) a boundary wall?, Is (row, col) an internal hole / island?, Is (row, col) out of bounds or any kind of obstacle?, Move `robot` one step in `direction` if valid.         Returns True if move was, Would robot fit at (row, col) without hitting any obstacle or wall?         Doe, Can `robot` move one step in `direction`?         Checks: grid fit + no collisi

### Community 7 - "Community 7"
Cohesion: 0.22
Nodes (5): demo_validator.py ----------------- Manual demo for the validator., PathResolver, path_resolver.py ---------------- Converts compact path strings into flat comm, Convert compact path string(s) to flat command list.          Accepts:, Parse a single segment like '12R2US'.

### Community 8 - "Community 8"
Cohesion: 0.67
Nodes (3): filter_excluded(), main(), Drop any file whose path contains one of the exclude folder names.

### Community 9 - "Community 9"
Cohesion: 1.0
Nodes (0): 

### Community 10 - "Community 10"
Cohesion: 1.0
Nodes (0): 

### Community 11 - "Community 11"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **39 isolated node(s):** `Drop any file whose path contains one of the exclude folder names.`, `directories.py -------- Central place for all project directory paths.  Ever`, `Absolute path to src/ (where this file lives).`, `Absolute path to the project root (one level above src/).`, `Absolute path to plots/. Created if it doesn't exist.` (+34 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 9`** (2 nodes): `main()`, `list_communities.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 10`** (1 nodes): `demo_solver.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 11`** (1 nodes): `__init__.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Grid` connect `Community 0` to `Community 1`, `Community 2`, `Community 3`, `Community 4`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.262) - this node is a cross-community bridge._
- **Why does `Robot` connect `Community 1` to `Community 0`, `Community 2`, `Community 3`, `Community 4`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.225) - this node is a cross-community bridge._
- **Why does `Workspace` connect `Community 1` to `Community 0`, `Community 2`, `Community 3`, `Community 4`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.225) - this node is a cross-community bridge._
- **Are the 62 inferred relationships involving `Grid` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Grid` has 62 INFERRED edges - model-reasoned connections that need verification._
- **Are the 65 inferred relationships involving `Robot` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Robot` has 65 INFERRED edges - model-reasoned connections that need verification._
- **Are the 61 inferred relationships involving `Workspace` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Workspace` has 61 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `Validator` (e.g. with `demo_validator.py ----------------- Manual demo for the validator.` and `find_hardest_workspace.py ------------------------- Self-contained, optimized`) actually correct?**
  _`Validator` has 30 INFERRED edges - model-reasoned connections that need verification._