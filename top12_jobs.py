"""Ranking jobs independent of Streamlit reruns and optional persistence."""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from time import monotonic

from top12_history import load_ledger, current_table, record_run, persist_ledger
from top12_rankings import build_top12_rankings

LOGGER = logging.getLogger(__name__)
EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="marketscope-top12")
INPUT_EXECUTOR = ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="marketscope-top12-inputs"
)
HISTORY_WAIT_SECONDS = 3
MONTHLY_WAIT_SECONDS = 5
LIVE_WAIT_SECONDS = 8
SAVE_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="marketscope-top12-save")


def calculate_rankings(
    market, years, data_as_of, monthly_loader, live_loader, threshold, progress
):
    warnings = []
    progress["stage"] = "Loading saved selections and monthly evidence"
    # Selection history is local-first. Remote history is merged only by the
    # background persistence path and can never delay a ranking table.
    histories = {}
    for kind in ("Recession", "Max Profit"):
        try:
            histories[kind] = load_ledger(kind, remote=False)
        except Exception:
            LOGGER.exception("Top 12 local history load failed")
            histories[kind] = {}
            warnings.append(
                f"{kind} local history unavailable; calculating without incumbent preference."
            )
    symbols = tuple(sorted(market.loc[market.Type.eq("Stock"), "Symbol"].tolist()))
    monthly_symbols = symbols + (
        ("SPY",) if "SPY" in set(market.Symbol) and "SPY" not in symbols else ()
    )
    try:
        monthly = INPUT_EXECUTOR.submit(
            monthly_loader, monthly_symbols, tuple(years)
        ).result(timeout=MONTHLY_WAIT_SECONDS) or {"returns": {}}
    except Exception:
        LOGGER.exception("Top 12 supplemental monthly load failed")
        monthly = {"returns": {}}
        warnings.append(
            "Monthly history could not be loaded. Annual approximations are used."
        )
    progress["stage"] = "Loading recent market inputs; source requests may take longer"
    try:
        live = (
            INPUT_EXECUTOR.submit(live_loader, symbols).result(
                timeout=LIVE_WAIT_SECONDS
            )
            or {}
        )
    except Exception:
        LOGGER.exception("Top 12 live context load failed")
        live = {}
        warnings.append(
            "Recent supplemental inputs unavailable. Using historical fallback."
        )
    progress["stage"] = "Calculating both Top 12 lists with 5,000 scenarios"
    result = build_top12_rankings(
        market,
        list(years),
        monthly,
        live,
        5000,
        previous={k: current_table(v) for k, v in histories.items()},
        threshold=threshold,
    )
    for kind in ("Recession", "Max Profit"):
        if kind not in result or len(result[kind]) != 12:
            raise ValueError(
                f"{kind} did not produce 12 stocks. Check eligible history and sector diversity."
            )
    result["metadata"]["Market Data Through"] = data_as_of
    result["metadata"]["Monthly Data Through"] = max(
        (p for h in (monthly.get("returns") or {}).values() for p in h),
        default="Unavailable",
    )
    result.setdefault("warnings", []).extend(warnings)
    # Timestamp the completed calculation, not a later download or save retry.
    stamp = datetime.now(timezone.utc).isoformat()
    for kind in histories:
        try:
            histories[kind] = record_run(
                histories[kind], kind, result[kind], result["metadata"], stamp
            )
        except Exception:
            LOGGER.exception("Top 12 history event creation failed")
            result["warnings"].append(
                f"{kind} change event could not be recorded; the calculated ranking remains available."
            )
    return {"result": result, "histories": histories}


def save_histories(histories):
    messages = []
    for kind, ledger in histories.items():
        try:
            ok, message = persist_ledger(kind, ledger)
            messages.append((ok, message))
        except Exception:
            LOGGER.exception("Top 12 history persistence failed")
            messages.append(
                (
                    False,
                    f"{kind} history could not be saved. The ranking remains available in this session.",
                )
            )
    return messages
