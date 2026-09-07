"""Put the repo root on sys.path so `import src...` works under pytest.

The project is not installed as a package (pyproject.toml carries only tool
config), so tests rely on the repo root being importable the same way
`python run_tests.py` does from the working directory.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
