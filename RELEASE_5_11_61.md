# MarketScope v5.11.61 — SQLite contention fix

The production traceback shows source-cache lease writes failing with SQLite "database is locked". News indexing previously shared the cache/job database and held one write transaction while performing expensive article analysis across the archive.

Changes:
- Separate SQLite news/index storage from source caches and calculation jobs. PostgreSQL installations keep their existing shared connection and row-level concurrency behavior.
- Analyze articles outside write transactions, then commit short per-article updates. Re-read within the transaction and retry conflicting updates so concurrent enrichment is preserved. Archive source metadata is merged in its own short transaction; interrupted imports can resume idempotently.
- Copy existing committed legacy news tables atomically to the news database on first initialization. The original data is retained. Schema initialization identities include the actual database path.
- Set busy timeout before configuring WAL, avoid repeated journal-mode changes, and close connections if setup fails.
- Cache lease contention returns the prior cache value with its original timestamp, or the existing caller fallback when no cache exists. It never invents prices or marks stale values current. Retry-marker and lease cleanup contention cannot crash the page. Unrelated database errors remain visible.

Validation includes real SQLite writer locks, independent news/cache/job activity, blocked article analysis with another writer, overlapping updates preserving publisher text, nondestructive migration, and non-contention error propagation. All prior application features and financial calculations are preserved.

Deployment uses the existing GitHub main → Render automatic deployment. No new paid infrastructure or credentials are required. Existing SQLite storage remains subject to the service's configured persistence; this change does not claim durability across an ephemeral-disk redeploy.
