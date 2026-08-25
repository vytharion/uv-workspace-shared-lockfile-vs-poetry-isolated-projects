# Benchmarks

This directory holds captured measurement runs for the article.

## Cold and warm install times

```bash
python3 bench_install.py --runs 3
```

The harness clears each tool's cache directory and the local `.venv`
before every cold run, then re-runs the same install to measure the
warm case. Median of `--runs` samples per scenario lands in
`results.json` alongside the console table.

## Lockfile churn

```bash
python3 measure_churn.py \
    --label "uv workspace pytest bump" \
    --before /tmp/uv.lock.before \
    --after  sample/uv.lock
```

Fetch the "before" snapshot with `git show <ref>:<path> > /tmp/...`
before running.
