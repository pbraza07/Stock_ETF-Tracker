"""Shared projection dashboard formatting for UI and PDF."""
import numpy as np

def _format_summary_value(metric: str, value) -> str:
    if value is None or value == "":
        return "N/A"
    if isinstance(value, (int, float, np.number)):
        if "Score" in metric:
            return f"{float(value):,.1f} / 100"
        if any(token in metric for token in ("Probability", "Percentage", "Drawdown", "CAGR")):
            return f"{float(value):,.2f}%"
        if metric == "Median Depletion Year":
            return str(int(value))
        return f"${float(value):,.2f}"
    return str(value)


def _summary_metrics(summary: dict, include_no_withdrawal: bool) -> list[str]:
    metrics = [
        "Starting Investment", "Forecast Period", "Selected Holdings", "Allocation",
        "P10 Ending Balance", "P25 Ending Balance", "P50 Ending Balance", "P75 Ending Balance", "P90 Ending Balance",
        "Median Total Investment Profit", "Median Total Wealth Profit", "Median Actual Withdrawals Received",
        "Withdrawal Shortfall", "Full-Withdrawal Success Probability", "Depletion Probability", "Median Depletion Year",
    ]
    if summary.get("Median Depletion Month and Year") is not None:
        metrics.append("Median Depletion Month and Year")
    if include_no_withdrawal:
        metrics.extend(["Median No-Withdrawal Ending Balance", "Median No-Withdrawal CAGR"])
    metrics.extend([
        "Best Modeled Year", "Worst Modeled Year", "Maximum Projected Drawdown", "Positive-Year Percentage",
    ])
    if summary.get("Positive-Month Percentage") is not None:
        metrics.append("Positive-Month Percentage")
    metrics.extend(["Projection Calibration Score", "Model Confidence", "Projection Confidence Explanation"])
    return metrics


