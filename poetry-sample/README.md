# poetry-sample — two isolated Poetry projects

The same two-package layout as `sample/`, but each package is its own
Poetry project with its own `poetry.lock`. There is no workspace root
and no shared lockfile — that is the whole point of the contrast.

- `packages/shared_lib` — publishes `greet(name)`. Owns its own
  `poetry.lock`.
- `packages/app` — imports `greet` through a Poetry `path` dependency
  with `develop = true`. Owns its own `poetry.lock`.

Because each project resolves independently, the same transitive
dependency (`pytest` and everything it pulls in) is pinned twice —
once per lockfile. Step 3 of the article walks through the setup and
compares it against the single `uv.lock` produced by `sample/`.

## Running the tests

Each project installs into its own virtualenv:

```bash
cd packages/shared_lib && poetry install && poetry run pytest
cd packages/app        && poetry install && poetry run pytest
```

Or, from `poetry-sample/`, run both suites end-to-end:

```bash
python3 run_tests.py
```
