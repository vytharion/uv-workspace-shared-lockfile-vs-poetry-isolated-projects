# sample — shared library + app consumer

Minimal two-package Python layout used to compare dependency-manager
setups.

- `packages/shared_lib` — publishes `greet(name)`.
- `packages/app` — imports `greet` and exposes `welcome(name)`.

Tests use only the standard library so the scaffold runs before any
dependency manager is installed:

```bash
python3 run_tests.py
```
