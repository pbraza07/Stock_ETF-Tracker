#!/usr/bin/env python3
"""
MarketScope v5.11.9 corrective patch:
- Make the no-withdrawal Portfolio/Profit Simulator information table use the
  same complete column schema/order as withdrawal-enabled runs.
- Persist no-withdrawal portfolio-level positive-month counts.
- Make the no-withdrawal PDF retain the same page-1 information structure and
  the same Portfolio Information / Timeframe Performance sections.
- Keep withdrawal calculations and ranking/simulator formulas unchanged.

Run from the Stock_ETF-Tracker repository root:
    python apply_v5119_no_withdrawal_parity.py
"""

from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path.cwd()
APP = ROOT / "app.py"
PDF = ROOT / "portfolio_simulations.py"

if not APP.exists() or not PDF.exists():
    raise SystemExit(
        "Run this script from the Stock_ETF-Tracker repository root "
        "(app.py and portfolio_simulations.py must be present)."
    )

app = APP.read_text(encoding="utf-8")
pdf = PDF.read_text(encoding="utf-8")

if 'MARKETSCOPE_VERSION = _marketscope_version()' not in app:
    raise SystemExit("Unexpected app.py: MarketScope version anchor not found.")
if 'def build_portfolio_simulation_pdf(record: dict) -> bytes:' not in pdf:
    raise SystemExit("Unexpected portfolio_simulations.py: PDF builder anchor not found.")

# 1) Canonical table schema: identical regardless of withdrawal mode.
old = """        rows.append(row)
    return pd.DataFrame(rows)


with portfolio_tab:
"""
new = """        rows.append(row)

    # v5.11.9 corrective parity: the Portfolio/Profit Simulator information
    # table always uses one canonical schema. Withdrawal mode changes cash-flow
    # calculations, never which information/performance columns are shown.
    columns = [
        "Industry",
        "Stock",
        "Allocation",
        "10-year CAGR",
        "Positive years",
        "Positive months",
        "Worst year and %",
        "Best year and %",
        "Regular yield",
        "Est. annual dividend",
        *PERF_COLS,
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows).reindex(columns=columns)


def _portfolio_no_withdrawal_positive_month_counts(
    monthly_payload: dict,
    symbols: list[str],
    weights: dict[str, float],
    principal: float,
) -> tuple[int | None, int | None]:
    # Count positive portfolio months on the natural no-withdrawal drift path.
    returns = (monthly_payload or {}).get("returns") or {}
    clean = [
        str(symbol).upper()
        for symbol in symbols
        if float((weights or {}).get(str(symbol).upper(), 0.0) or 0.0) > 0
    ]
    if not clean:
        return None, None

    maps = []
    for symbol in clean:
        month_map = returns.get(symbol) or {}
        if not month_map:
            return None, None
        maps.append(month_map)

    common = set(maps[0])
    for month_map in maps[1:]:
        common &= set(month_map)
    periods = sorted(common)
    if not periods:
        return None, None

    weight_total = sum(float((weights or {}).get(symbol, 0.0) or 0.0) for symbol in clean)
    if weight_total <= 0 or float(principal or 0.0) <= 0:
        return None, None

    balances = {
        symbol: float(principal) * float((weights or {}).get(symbol, 0.0) or 0.0) / weight_total
        for symbol in clean
    }
    positive = 0
    modeled = 0
    for period in periods:
        before = sum(balances.values())
        valid = True
        next_balances = {}
        for symbol in clean:
            try:
                monthly_return = float((returns.get(symbol) or {}).get(period))
            except (TypeError, ValueError):
                valid = False
                break
            if not np.isfinite(monthly_return) or monthly_return <= -1.0:
                valid = False
                break
            next_balances[symbol] = balances[symbol] * (1.0 + monthly_return)
        if not valid or before <= 0:
            continue
        balances = next_balances
        after = sum(balances.values())
        positive += int(after > before)
        modeled += 1

    return (int(positive), int(modeled)) if modeled else (None, None)


with portfolio_tab:
"""
if old in app:
    app = app.replace(old, new, 1)
elif '_portfolio_no_withdrawal_positive_month_counts(' not in app:
    raise SystemExit("Could not patch canonical analytics table schema: anchor not found.")

# 2) Initialize no-withdrawal portfolio month statistics.
anchor = """    portfolio_analytics: list[dict] = []
    portfolio_income_metrics: dict[str, dict] = {}
"""
replacement = """    portfolio_analytics: list[dict] = []
    portfolio_income_metrics: dict[str, dict] = {}
    portfolio_no_withdrawal_positive_months: int | None = None
    portfolio_no_withdrawal_available_months: int | None = None
"""
if "portfolio_no_withdrawal_positive_months: int | None = None" not in app:
    if anchor not in app:
        raise SystemExit("Could not initialize no-withdrawal month statistics.")
    app = app.replace(anchor, replacement)

# 3) Build no-withdrawal portfolio positive-month counts from actual monthly evidence.
old = """                    analytics_monthly_stats: dict[str, dict] = {}
                    analytics_years = tuple(str(y) for y in (effective_portfolio_years or [])[:10])
                    if analytics_years:
                        analytics_monthly_payload = cached_actual_monthly_returns(
"""
new = """                    analytics_monthly_stats: dict[str, dict] = {}
                    analytics_monthly_payload: dict = {"returns": {}, "unavailable": True}
                    analytics_years = tuple(str(y) for y in (effective_portfolio_years or [])[:10])
                    if analytics_years:
                        analytics_monthly_payload = cached_actual_monthly_returns(
"""
if old in app:
    app = app.replace(old, new, 1)
elif 'analytics_monthly_payload: dict = {"returns": {}, "unavailable": True}' not in app:
    raise SystemExit("Could not initialize analytics monthly payload.")

anchor = """                                analytics_monthly_stats[str(_sym).upper()] = {
                                    "positive_months": sum(1 for v in _values if v > 0.0),
                                    "available_months": len(_values),
                                }
                    market_lookup_for_analytics = market.set_index(market["Symbol"].astype(str).str.upper(), drop=False)
"""
replacement = """                                analytics_monthly_stats[str(_sym).upper()] = {
                                    "positive_months": sum(1 for v in _values if v > 0.0),
                                    "available_months": len(_values),
                                }

                    # v5.11.9 corrective parity: save a true portfolio-level
                    # positive-month count even when no withdrawal mode is on.
                    if (
                        not portfolio_withdrawals_enabled
                        and not portfolio_monthly_withdrawals_enabled
                        and not analytics_monthly_payload.get("unavailable")
                    ):
                        (
                            portfolio_no_withdrawal_positive_months,
                            portfolio_no_withdrawal_available_months,
                        ) = _portfolio_no_withdrawal_positive_month_counts(
                            analytics_monthly_payload,
                            list(selected_portfolio_symbols),
                            dict(portfolio_weights),
                            float(portfolio_total),
                        )

                    market_lookup_for_analytics = market.set_index(market["Symbol"].astype(str).str.upper(), drop=False)
"""
if anchor in app:
    app = app.replace(anchor, replacement, 1)
elif "portfolio_no_withdrawal_available_months," not in app:
    raise SystemExit("Could not add no-withdrawal portfolio month calculation.")

# 4) Persist the no-withdrawal portfolio-level month statistics.
anchor = """                "instruments": saved_instruments,
                "effective_calendar_years": list(effective_portfolio_years or []),
                "monthly_positive_months_rebalanced": int(portfolio_monthly_withdrawal_rebalanced_result.get("positive_months") or 0) if portfolio_monthly_withdrawals_enabled else None,
"""
replacement = """                "instruments": saved_instruments,
                "effective_calendar_years": list(effective_portfolio_years or []),
                "portfolio_positive_months": (
                    int(portfolio_no_withdrawal_positive_months)
                    if (
                        not portfolio_withdrawals_enabled
                        and not portfolio_monthly_withdrawals_enabled
                        and portfolio_no_withdrawal_positive_months is not None
                    )
                    else None
                ),
                "portfolio_available_months": (
                    int(portfolio_no_withdrawal_available_months)
                    if (
                        not portfolio_withdrawals_enabled
                        and not portfolio_monthly_withdrawals_enabled
                        and portfolio_no_withdrawal_available_months is not None
                    )
                    else None
                ),
                "monthly_positive_months_rebalanced": int(portfolio_monthly_withdrawal_rebalanced_result.get("positive_months") or 0) if portfolio_monthly_withdrawals_enabled else None,
"""
if anchor in app:
    app = app.replace(anchor, replacement, 1)
elif '"portfolio_positive_months": (' not in app:
    raise SystemExit("Could not persist no-withdrawal positive-month fields.")

# 5) Repair older no-withdrawal saved records while monthly data is available.
anchor = """                if values:
                    item["positive_months"] = int(sum(1 for v in values if v > 0.0))
                    item["available_months"] = int(len(values))

    if market_df is not None and not market_df.empty:
"""
replacement = """                if values:
                    item["positive_months"] = int(sum(1 for v in values if v > 0.0))
                    item["available_months"] = int(len(values))

            if (
                not bool(upgraded.get("annual_withdrawals_enabled"))
                and not bool(upgraded.get("monthly_withdrawals_enabled"))
                and not actual_payload.get("unavailable")
            ):
                legacy_weights = {
                    str(item.get("symbol") or "").upper(): float(item.get("weight") or 0.0)
                    for item in instruments
                }
                legacy_positive, legacy_months = _portfolio_no_withdrawal_positive_month_counts(
                    actual_payload,
                    [str(item.get("symbol") or "").upper() for item in instruments],
                    legacy_weights,
                    float(upgraded.get("total_invested") or 0.0),
                )
                if legacy_positive is not None and legacy_months is not None:
                    upgraded["portfolio_positive_months"] = int(legacy_positive)
                    upgraded["portfolio_available_months"] = int(legacy_months)

    if market_df is not None and not market_df.empty:
"""
if anchor in app:
    app = app.replace(anchor, replacement, 1)
elif "legacy_positive, legacy_months = _portfolio_no_withdrawal_positive_month_counts" not in app:
    raise SystemExit("Could not add saved-record no-withdrawal month repair.")

# 6) Bump only the internal PDF-layout contract, not VERSION.txt.
old_marker = (
    "MarketScope Portfolio Split Simulator v37 - v5.9.82 monthly reset + "
    "monthly start-year RB/NR depletion dashboard + continuous monthly start-year paths + "
    "start-year RB/NR depletion dashboard + split start-year strategies + persistent Build Simulation withdrawal tabs + "
    "annual and monthly reset views + annual positive years + display-mode searchable dropdowns + "
    "six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + "
    "Market Table target transcription + required instrument market data on page 1"
)
new_marker = old_marker + " + no-withdrawal table/PDF parity"
if new_marker not in app:
    if old_marker not in app:
        raise SystemExit("Current PDF layout marker was not found in app.py.")
    app = app.replace(old_marker, new_marker)

# 7) PDF combined metrics carry no-withdrawal portfolio positive months.
anchor = """            "positive_years": 0,
            "available_years": 0,
            "worst_year": None,
"""
replacement = """            "positive_years": 0,
            "available_years": 0,
            "positive_months": (
                int(record.get("portfolio_positive_months"))
                if record.get("portfolio_positive_months") is not None else None
            ),
            "available_months": (
                int(record.get("portfolio_available_months"))
                if record.get("portfolio_available_months") is not None else None
            ),
            "worst_year": None,
"""
if anchor in pdf:
    pdf = pdf.replace(anchor, replacement, 1)

anchor = """        "positive_years": positive_years,
        "available_years": len(annual),
        "worst_year": worst[0] if worst else None,
"""
replacement = """        "positive_years": positive_years,
        "available_years": len(annual),
        "positive_months": (
            int(record.get("portfolio_positive_months"))
            if record.get("portfolio_positive_months") is not None else None
        ),
        "available_months": (
            int(record.get("portfolio_available_months"))
            if record.get("portfolio_available_months") is not None else None
        ),
        "worst_year": worst[0] if worst else None,
"""
if anchor in pdf:
    pdf = pdf.replace(anchor, replacement, 1)
elif 'record.get("portfolio_available_months")' not in pdf:
    raise SystemExit("Could not add no-withdrawal month metrics to PDF.")

# 8) Page 1 uses no-withdrawal positive months instead of a dash.
anchor = """    pos_years = f"{int(combined.get('positive_years') or 0)}/{int(combined.get('available_years') or 0)}"
    page1_positive_months = "-"
    if bool(record.get("monthly_withdrawals_enabled")):
"""
replacement = """    pos_years = f"{int(combined.get('positive_years') or 0)}/{int(combined.get('available_years') or 0)}"
    _base_positive_months = combined.get("positive_months")
    _base_available_months = combined.get("available_months")
    page1_positive_months = (
        f"{int(_base_positive_months)}/{int(_base_available_months)}"
        if _base_positive_months is not None and _base_available_months is not None
        else "-"
    )
    if bool(record.get("monthly_withdrawals_enabled")):
"""
if anchor in pdf:
    pdf = pdf.replace(anchor, replacement, 1)
elif '_base_positive_months = combined.get("positive_months")' not in pdf:
    raise SystemExit("Could not patch PDF page-1 Positive Months fallback.")

# 9) Page 1 retains the same information band when withdrawals are off.
anchor = """            return [
                f"ANNUAL WITHDRAWAL {_money(amount)}",
                f"REBALANCED {_money(rb_end)}  |  NOT-REBAL {_money(nr_end)}",
                f"REBALANCE DIFF {_money(rb_end - nr_end, signed=True)}  |  POSITIVE YRS RB {rb_pos}/{rb_years} NR {nr_pos}/{nr_years}",
            ]
        return []

    withdrawal_lines = _page1_withdrawal_lines()
"""
replacement = """            return [
                f"ANNUAL WITHDRAWAL {_money(amount)}",
                f"REBALANCED {_money(rb_end)}  |  NOT-REBAL {_money(nr_end)}",
                f"REBALANCE DIFF {_money(rb_end - nr_end, signed=True)}  |  POSITIVE YRS RB {rb_pos}/{rb_years} NR {nr_pos}/{nr_years}",
            ]
        return [
            "WITHDRAWAL MODE NONE",
            "NO CASH WITHDRAWALS APPLIED",
            "FULL PORTFOLIO INFORMATION + TIMEFRAME PERFORMANCE TABLES INCLUDED",
        ]

    withdrawal_lines = _page1_withdrawal_lines()
"""
if anchor in pdf:
    pdf = pdf.replace(anchor, replacement, 1)
elif '"WITHDRAWAL MODE NONE"' not in pdf:
    raise SystemExit("Could not add no-withdrawal page-1 context.")

for path in (APP, PDF):
    backup = path.with_suffix(path.suffix + ".before_v5119_no_withdrawal_parity")
    if not backup.exists():
        shutil.copy2(path, backup)

APP.write_text(app, encoding="utf-8")
PDF.write_text(pdf, encoding="utf-8")

compile(app, str(APP), "exec")
compile(pdf, str(PDF), "exec")

print("Applied MarketScope v5.11.9 no-withdrawal table/PDF parity patch.")
print("Updated: app.py")
print("Updated: portfolio_simulations.py")
print("MarketScope VERSION.txt is intentionally unchanged.")
