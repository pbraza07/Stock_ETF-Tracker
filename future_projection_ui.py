"""Compatibility layer for MarketScope Future Projection UI enhancements.

v5.10.2 keeps the v5.10.1 UI intact and inserts P25/P50/P75 plus Profit %
summary cards without changing the existing simulator controls or charts.
"""

from __future__ import annotations

import numbers

import future_projection_ui_legacy as _legacy

# Preserve the complete v5.10.1 UI surface.
for _name in dir(_legacy):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_legacy, _name)

_original_summary_metrics = _legacy._summary_metrics
_original_format_summary_value = _legacy._format_summary_value


def _summary_metrics(summary: dict, show_extended: bool, include_no_withdrawal: bool) -> list[str]:
    metrics = list(_original_summary_metrics(summary, show_extended, include_no_withdrawal))

    # Make the central probability range prominent while retaining all existing
    # P10/P90 and optional P5/P95 cards.
    central = [
        "P25 Ending Balance",
        "P50 Ending Balance",
        "P75 Ending Balance",
        "Profit %",
    ]
    insert_at = metrics.index("Median Ending Balance") if "Median Ending Balance" in metrics else min(4, len(metrics))
    for metric in reversed(central):
        if metric not in metrics:
            metrics.insert(insert_at, metric)
    return metrics


def _format_summary_value(metric: str, value) -> str:
    if isinstance(value, numbers.Number) and (metric.endswith("Profit %") or metric == "Profit %"):
        return f"{float(value):,.2f}%"
    return _original_format_summary_value(metric, value)


_legacy._summary_metrics = _summary_metrics
_legacy._format_summary_value = _format_summary_value

# The original render function now resolves the patched helpers above.
render_future_projection = _legacy.render_future_projection
