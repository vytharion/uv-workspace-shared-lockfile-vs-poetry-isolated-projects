#!/usr/bin/env python3
"""Stdlib test runner used before any dependency manager is wired up."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGES = ROOT / "packages"

for src_dir in sorted(PACKAGES.glob("*/src")):
    sys.path.insert(0, str(src_dir))

loader = unittest.TestLoader()
suite = unittest.TestSuite()
for tests_dir in sorted(PACKAGES.glob("*/tests")):
    suite.addTests(
        loader.discover(
            start_dir=str(tests_dir),
            pattern="test_*.py",
            top_level_dir=str(tests_dir),
        )
    )

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
