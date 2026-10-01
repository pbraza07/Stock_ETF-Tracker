"""Generate representative PDFs for visual release QA."""

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from future_projection import build_pdf_export
from portfolio_simulations import build_portfolio_simulation_pdf
from top12_exports import build_top12_pdf


def _top12_result():
    rows = []
    for rank in range(1, 13):
        rows.append({
            "Rank": rank,
            "Symbol": f"S{rank:02d}",
            "Name": f"Sample Company {rank}",
            "Sector": ["Technology", "Healthcare", "Industrials"][((rank - 1) // 4)],
            "Recession Score": 91 - rank,
            "Max Profit Score": 92 - rank,
            "Data Confidence": "HIGH",
            "Maximum Drawdown %": -12 - rank,
            "Recovery Periods": rank,
            "Recovery Basis": "Monthly",
            "Why Selected": "Ranks favorably using calculated return, downside, consistency, and projection evidence.",
            **{f"Bear P{q} Future Return %": q / 10 for q in (10, 25, 50, 75, 90)},
            **{f"P{q} Future Return %": q / 10 for q in (10, 25, 50, 75, 90)},
        })
    table = pd.DataFrame(rows)
    return table, {
        "metadata": {
            "Ranking Generated": "2026-09-08 12:00 UTC",
            "Market Data Through": "2026-09-07",
            "Eligible Stocks": 167,
            "Model Version": "5.11.11",
        },
        "all_scores": table.copy(),
        "warnings": [],
    }


def _future_result():
    return {
        "metadata": {
            "data_as_of": "2026-09-07", "model_as_of": "2026-09-08",
            "simulation_count": 5000, "random_seed": 42,
            "forecast_start_year": 2027, "forecast_end_year": 2031,
            "live_data_status": "Latest available",
            "projection_calibration_score": 78, "projection_confidence": "Medium",
        },
        "inputs": {
            "starting_investment": 300000, "withdrawal_frequency": "Annual",
            "withdrawal_timing": "Year end", "annual_withdrawal": 60000,
            "monthly_withdrawal": 0, "strategy": "Both",
            "projection_profile": "Auto", "rebalancing_frequency": "Annual",
            "annual_management_fee": 0, "holdings": ["AAPL", "ABBV", "CAT", "CVX"],
            "allocations": {"AAPL": 25, "ABBV": 25, "CAT": 25, "CVX": 25},
        },
        "current_market_state": {
            "regime_probabilities": {"Bear": 20, "Normal": 55, "Bull": 25},
            "market_trend": "Positive", "volatility_environment": "Normal",
            "valuation_environment": "Neutral", "earnings_trend": "Stable",
            "interest_rate_environment": "Restrictive",
            "portfolio_correlation_risk": "Moderate", "data_freshness": {},
        },
        "strategies": {}, "comparison": pd.DataFrame(), "warnings": [],
        "limitations": ["Illustrative probabilistic projection; future returns are not guaranteed."],
        "model_assumptions": pd.DataFrame(),
    }


def main():
    output = ROOT / "output" / "pdf"
    output.mkdir(parents=True, exist_ok=True)
    table, ranking = _top12_result()
    artifacts = {
        "Stock_Projection_Reference.pdf": build_portfolio_simulation_pdf({
            "id": "QA-REFERENCE", "name": "Stock Projection Reference",
            "app_version": "5.11.11", "period": "10Y", "allocation_mode": "Equal split",
            "created_at_display_et": "Sep 8, 2026", "total_invested": 300000,
            "ending_value": 615000, "profit_loss": 315000, "total_return": 105,
            "instruments": [],
        }),
        "Future_Projection_Unified.pdf": build_pdf_export(_future_result()),
        "Top12_Recession_Unified.pdf": build_top12_pdf("Recession", table, ranking),
    }
    for name, content in artifacts.items():
        path = output / name
        path.write_bytes(content)
        print(path)


if __name__ == "__main__":
    main()
