from __future__ import annotations

import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import pandas as pd

from favorite_picks import build_favorite_picks, favorite_candidate_symbols
from favorite_picks_history import (
    empty_favorite_picks_ledger,
    normalize_favorite_picks_ledger,
    record_favorite_picks_run,
)
from future_projection_live import fetch_live_projection_context
from persistence import now_et
from providers import YahooFinanceProvider


SNAPSHOT = BASE_DIR / "data" / "market_snapshot.csv"
METADATA = BASE_DIR / "data" / "snapshot_metadata.json"
HISTORY = BASE_DIR / "data" / "favorite_picks_history.json"
BOOTSTRAP_HISTORY = BASE_DIR / "data" / "favorite_picks_history.bootstrap.json"


def _read_json(path: Path, fallback):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload
    except Exception:
        return fallback


def main() -> None:
    if not SNAPSHOT.exists():
        raise FileNotFoundError("Favorite Picks history requires data/market_snapshot.csv.")
    market = pd.read_csv(SNAPSHOT)
    year_columns = sorted(
        [str(column) for column in market.columns if str(column).isdigit() and len(str(column)) == 4],
        key=int,
        reverse=True,
    )
    symbols = favorite_candidate_symbols(market, year_columns)
    if not symbols:
        raise RuntimeError("No eligible Favorite Picks candidates were found in the refreshed snapshot.")

    try:
        live_context = fetch_live_projection_context(YahooFinanceProvider(), symbols, market)
    except Exception as exc:
        live_context = {"failures": [f"Daily supplemental data unavailable ({type(exc).__name__}); historical fallback used."]}
    metadata = _read_json(METADATA, {})
    data_as_of = str(metadata.get("updated_at_display_et") or metadata.get("updated_at_et") or "Latest available")
    result = build_favorite_picks(
        market,
        year_columns,
        live_context=live_context,
        projection_years=5,
        simulations=5_000,
        random_seed=20260904,
        data_as_of=data_as_of,
    )
    stored = _read_json(HISTORY, _read_json(BOOTSTRAP_HISTORY, empty_favorite_picks_ledger()))
    ledger, events = record_favorite_picks_run(
        normalize_favorite_picks_ledger(stored),
        result["table"],
        observed_at=now_et(),
        data_as_of=data_as_of,
        random_seed=result["random_seed"],
    )
    temporary = HISTORY.with_suffix(".tmp")
    temporary.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    temporary.replace(HISTORY)
    print(
        f"Favorite Picks run saved: {result['pick_count']} picks across {result['sector_count']} sectors; "
        f"{len(events)} first-detected change event(s); {len(ledger['events'])} total retained event(s)."
    )


if __name__ == "__main__":
    main()
