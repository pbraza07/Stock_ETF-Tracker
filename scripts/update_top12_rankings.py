"""Daily Top 12 snapshots and permanent change ledgers."""

import sys
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
import pandas as pd
from top12_rankings import build_top12_rankings
from top12_data import load_monthly
from top12_history import load_ledger, current_table, record_run, persist_ledger
from future_projection_live import fetch_live_projection_context
from providers import YahooFinanceProvider


def main():
    market = pd.read_csv(BASE / "data/market_snapshot.csv")
    years = [c for c in market if c.isdigit() and len(c) == 4]
    symbols = market.loc[market.Type.eq("Stock"), "Symbol"].tolist()
    histories = {kind: load_ledger(kind) for kind in ("Recession", "Max Profit")}
    try:
        live = fetch_live_projection_context(YahooFinanceProvider(), symbols, market)
    except Exception:
        live = {}
    monthly_symbols = symbols + (
        ["SPY"] if "SPY" in set(market.Symbol) and "SPY" not in symbols else []
    )
    monthly = load_monthly(monthly_symbols, years, remote=False)
    result = build_top12_rankings(
        market,
        years,
        monthly,
        live,
        previous={k: current_table(v) for k, v in histories.items()},
    )
    metadata_path = BASE / "data/snapshot_metadata.json"
    snapshot_metadata = (
        json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    )
    result["metadata"]["Market Data Through"] = snapshot_metadata.get(
        "updated_at_et", "Unavailable"
    )
    result["metadata"]["Monthly Data Through"] = max(
        (p for history in monthly["returns"].values() for p in history),
        default="Unavailable",
    )
    for kind in histories:
        ledger = record_run(histories[kind], kind, result[kind], result["metadata"])
        ok, msg = persist_ledger(kind, ledger)
        if not ok:
            raise RuntimeError(msg)
        print(kind + ": " + msg)


if __name__ == "__main__":
    main()
