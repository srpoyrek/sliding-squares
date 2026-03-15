"""
directories.py
--------
Central place for all project directory paths.

Every other module imports from here instead of
computing paths individually.

Layout assumed:
    <project_root>/
        src/        <- all .py files live here
        plots/      <- saved images go here  (auto-created)
        data/       <- saved grids/workspaces (auto-created)
        testcases/   <- test case files go here
"""

import os

# ── Root ────────────────────────────────────────────────


def get_src_dir() -> str:
    """Absolute path to src/ (where this file lives)."""
    return os.path.dirname(os.path.abspath(__file__))


def get_project_root() -> str:
    """Absolute path to the project root (one level above src/)."""
    return os.path.dirname(get_src_dir())


# ── Output folders ──────────────────────────────────────


def get_plots_dir() -> str:
    """Absolute path to plots/. Created if it doesn't exist."""
    d = os.path.join(get_project_root(), "plots")
    os.makedirs(d, exist_ok=True)
    return d


def get_data_dir() -> str:
    """Absolute path to data/. Created if it doesn't exist."""
    d = os.path.join(get_project_root(), "data")
    os.makedirs(d, exist_ok=True)
    return d


def get_testcases_dir() -> str:
    """Absolute path to testcases/. Created if it doesn't exist."""
    d = os.path.join(get_project_root(), "testcases")
    os.makedirs(d, exist_ok=True)
    return d


# ── Path builders ───────────────────────────────────────


def plots_path(filename: str) -> str:
    """Full path for a file in plots/.  e.g. plots_path('start.png')"""
    return os.path.join(get_plots_dir(), filename)


def data_path(filename: str) -> str:
    """Full path for a file in data/.  e.g. data_path('grid_01.json')"""
    return os.path.join(get_data_dir(), filename)


def testcases_path(filename: str) -> str:
    """Full path for a file in testcases/.  e.g. testcases_path('test.json')"""
    return os.path.join(get_testcases_dir(), filename)


# ── Sanity check ────────────────────────────────────────

if __name__ == "__main__":
    print("src:  ", get_src_dir())
    print("root: ", get_project_root())
    print("plots:", get_plots_dir())
    print("data: ", get_data_dir())
    print("testcases: ", get_testcases_dir())
    print()
    print("plots_path('test.png'):", plots_path("test.png"))
    print("data_path('grid.png'):", data_path("grid.png"))
    print("testcases_path('test.png'):", testcases_path("test.png"))
