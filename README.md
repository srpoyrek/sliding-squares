# Optimal Sliding Squares

Two n×n square robots swap positions in a grid workspace.
Find the workspace that maximizes the minimum number of control switches.

## Problem

Given a grid workspace with obstacles, two identical n×n square robots (A and B) must exchange positions. Only one robot is "controlled" at a time — issuing a control switch command transfers control to the other robot. The solver finds the path that minimizes the number of control switches needed to complete the swap.

## Setup

```bash
pip install -r requirements.txt
python -m pre_commit install
```

Requires Python 3.8+.

## Structure

```
sliding-squares/
├── src/
│   ├── bfs.py              # Layered BFS algorithm (core solver logic)
│   ├── grid.py             # Grid representation (free, boundary, hole tiles)
│   ├── robot.py            # n×n square robot representation
│   ├── state.py            # Immutable state snapshots for BFS
│   ├── workspace.py        # Grid + robots + movement/collision rules
│   ├── solver.py           # Solver interface wrapping BFS
│   ├── validator.py        # Step-by-step path execution and validation
│   ├── visualizer.py       # Matplotlib visualization (grids, sequences, BFS frontiers)
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
├── plots/
├── data/
├── demo_solver.py
├── demo_validator.py
├── run_tests.py
├── requirements.txt
└── README.md
```

## Algorithm

The solver uses a **layered breadth-first search** over the state space `(pos_a, pos_b, control)`:

1. Each BFS layer represents states reachable with exactly *k* control switches.
2. Within a layer, `flood_fill` explores all positions reachable by moving the controlled robot without switching.
3. The goal is checked at each layer — the first match is optimal by construction.
4. Path reconstruction backtracks through parent pointers to produce a command sequence.

Commands: `U` (up), `D` (down), `L` (left), `R` (right), `S` (switch control).

## Usage

### Run all test cases

```bash
python run_tests.py
```

### Run a specific test case

```bash
python run_tests.py 3x3_robot_no_holes
```

### Run demos

```bash
python demo_solver.py
python demo_validator.py
```

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
