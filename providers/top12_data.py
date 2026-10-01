"""Reuse durable monthly datasets without per-stock network history downloads."""

from pathlib import Path
import re
import pandas as pd
from persistence import load_remote_csv


def load_monthly(symbols, years, remote=True):
    result = {s: {} for s in symbols}
    root = Path(__file__).parent / "data"
    for name in (
        "monthly_returns_10y.csv",
        "monthly_returns_25y.csv",
        "monthly_returns_full_history.csv",
    ):
        path = root / name
        frame = (
            pd.read_csv(path)
            if path.exists()
            else (
                load_remote_csv("data/" + name, timeout=5) if remote else pd.DataFrame()
            )
        )
        if frame.empty or "Symbol" not in frame:
            continue
        labels = [
            c for c in frame if re.fullmatch(r"\d{4}-\d{2}", str(c)) and c[:4] in years
        ]
        for row in frame.to_dict("records"):
            symbol = str(row["Symbol"]).upper()
            if symbol not in result:
                continue
            for label in labels:
                value = pd.to_numeric(row.get(label), errors="coerce")
                if pd.notna(value) and value > -100:
                    result[symbol][label] = float(value) / 100
    return {"returns": result, "source": "MarketScope durable actual monthly datasets"}
