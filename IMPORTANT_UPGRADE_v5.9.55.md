# MarketScope v5.9.55 — 25Y GitHub Persistence Race Fix

## Root cause fixed

v5.9.54 successfully calculated and validated 25 completed annual-return years, including 2005–2001, but a concurrent commit reached `main` while the long refresh was still running. The final `git push` was rejected as non-fast-forward, so the verified snapshot never became durable.

## New persistence architecture

v5.9.55 adds `scripts/persist_generated_files.sh`.

For every generated-data persistence checkpoint it:

1. copies the freshly generated files outside the Git worktree;
2. fetches the newest `origin/main`;
3. resets the worktree to that newest `main`;
4. restores the generated MarketScope files on top of the newest code;
5. commits them;
6. pushes to `main`;
7. if another commit lands during that small window, repeats the process automatically;
8. retries up to six times by default.

This preserves unrelated concurrent code changes while preventing a long-running refresh from losing its generated market data.

## Two automatic checkpoints

The workflow now saves data in two phases:

### Checkpoint 1 — verified 25Y snapshot

Immediately after the 25Y coverage audit passes, MarketScope persists:

- `data/default_universe.csv`
- `data/market_snapshot.csv`
- `data/snapshot_metadata.json`
- `data/universe_metadata.json`
- `data/monthly_returns_10y.csv`

This happens before the slower portfolio-ranking jobs.

### Checkpoint 2 — ranking datasets

After ranking generation completes, MarketScope separately persists:

- actual-monthly Rebalanced Top 100
- actual-monthly Not-Rebalanced Top 100
- recession-balanced Rebalanced Top 100
- recession-balanced Not-Rebalanced Top 100

Therefore a later ranking failure cannot prevent the verified 25-year annual-return snapshot from reaching GitHub.

## 25-year behavior

The automatic history source still begins at `2000-01-01`, which provides the prior-year anchor needed to calculate the 2001 completed annual return. MarketScope continues to populate 2025–2001 only where the instrument genuinely has sufficient trading history.

No manual 25Y repair task is required.
