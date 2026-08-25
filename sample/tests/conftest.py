"""Put the codebase root on sys.path so tests can import top-level helpers.

The measurement scripts (`bench_install.py`, `measure_churn.py`) live at
the repository root, not inside the `sample/` package, so pytest needs
an explicit path insertion to reach them.
"""
from __future__ import annotations

import sys
from pathlib import Path

CODEBASE_ROOT = Path(__file__).resolve().parents[2]
if str(CODEBASE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODEBASE_ROOT))
