from pathlib import Path
import pandas as pd
import numpy as np
from analytics import calculate_monthly_returns
from history_config import ANNUAL_HISTORY_START
from persistence import load_remote_csv
from providers import YahooFinanceProvider
from shared_cache import cached
BASE_DIR=Path(__file__).parent
provider=YahooFinanceProvider()
MONTHLY_RETURNS_FILE = BASE_DIR / "data" / "monthly_returns_10y.csv"
MONTHLY_RETURNS_REPO_PATH = "data/monthly_returns_10y.csv"
MONTHLY_RETURNS_FULL_FILE = BASE_DIR / "data" / "monthly_returns_full_history.csv"
MONTHLY_RETURNS_FULL_REPO_PATH = "data/monthly_returns_full_history.csv"
MONTHLY_RETURNS_25Y_FILE = BASE_DIR / "data" / "monthly_returns_25y.csv"
MONTHLY_RETURNS_25Y_REPO_PATH = "data/monthly_returns_25y.csv"

def _actual_month_labels(calendar_years: tuple[str, ...] | list[str]) -> list[str]:
    years = sorted({int(str(y)) for y in calendar_years if str(y).isdigit()})
    return [f"{year}-{month:02d}" for year in years for month in range(1, 13)]


def _monthly_csv_actual(frame: pd.DataFrame) -> bool:
    if frame is None or frame.empty or "Monthly Return Method" not in frame.columns:
        return False
    methods = frame["Monthly Return Method"].dropna().astype(str)
    return bool(len(methods)) and methods.str.contains(
        "Actual adjusted month-end return", case=False, regex=False
    ).all()


def cached_future_projection_monthly_returns(
    symbols: tuple[str, ...],
    calendar_years: tuple[str, ...],
) -> dict:
    """Load every observed monthly return available, including partial histories.

    The historical withdrawal simulator intentionally requires complete windows.
    Future Projection has a different limited-history contract: it preserves all
    observed post-IPO/post-inception months and explicitly imputes only the missing
    periods. This separate loader avoids changing any existing simulator result.
    """
    clean_symbols = tuple(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))
    years = tuple(sorted({str(y) for y in calendar_years if str(y).isdigit()}, key=int))
    labels = _actual_month_labels(years)
    if not clean_symbols or not years:
        return {"unavailable": True, "reason": "No holdings or completed years were supplied.", "returns": {}}

    returns: dict[str, dict[str, float]] = {symbol: {} for symbol in clean_symbols}
    sources: list[pd.DataFrame] = []
    for local_path in (MONTHLY_RETURNS_FILE, MONTHLY_RETURNS_25Y_FILE, MONTHLY_RETURNS_FULL_FILE):
        if local_path.exists():
            try:
                sources.append(pd.read_csv(local_path))
            except Exception:
                pass
    for repo_path in (MONTHLY_RETURNS_REPO_PATH, MONTHLY_RETURNS_25Y_REPO_PATH, MONTHLY_RETURNS_FULL_REPO_PATH):
        remote = load_remote_csv(repo_path, timeout=15)
        if remote is not None and not remote.empty:
            sources.append(remote)

    for candidate in sources:
        if candidate is None or candidate.empty or "Symbol" not in candidate.columns or not _monthly_csv_actual(candidate):
            continue
        frame = candidate.copy()
        frame["Symbol"] = frame["Symbol"].astype(str).str.upper().str.strip()
        frame = frame.drop_duplicates("Symbol", keep="last").set_index("Symbol", drop=False)
        for symbol in clean_symbols:
            if symbol not in frame.index:
                continue
            row = frame.loc[symbol]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[-1]
            for label in labels:
                value = pd.to_numeric(pd.Series([row.get(label)]), errors="coerce").iloc[0]
                if pd.notna(value) and np.isfinite(value) and float(value) > -100.0:
                    returns[symbol][label] = float(value) / 100.0

    # Direct history fills all genuinely observed months while leaving pre-inception
    # dates absent for the projection engine to identify and blend explicitly.
    try:
        histories = provider.download_daily_history_since(
            list(clean_symbols),
            start=ANNUAL_HISTORY_START,
            chunk_size=min(10, max(1, len(clean_symbols))),
        )
    except Exception:
        histories = {}
    for symbol in clean_symbols:
        hist = histories.get(symbol)
        if hist is None or hist.empty:
            continue
        try:
            calculated = calculate_monthly_returns(hist, min(int(y) for y in years), max(int(y) for y in years))
        except Exception:
            continue
        for label, value in calculated.items():
            if label in labels and value is not None and np.isfinite(value) and float(value) > -1.0:
                returns[symbol][label] = float(value)

    observed = {symbol: len(values) for symbol, values in returns.items()}
    returns = {symbol: values for symbol, values in returns.items() if values}
    return {
        "unavailable": not bool(returns),
        "reason": "No actual monthly observations could be loaded." if not returns else "",
        "returns": returns,
        "months": labels,
        "observed_periods": observed,
        "method": "Observed adjusted month-end returns; missing pre-inception periods remain explicit for calibrated imputation",
    }

