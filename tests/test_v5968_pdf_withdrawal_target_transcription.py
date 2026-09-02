from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
PDF = (ROOT / "portfolio_simulations.py").read_text(encoding="utf-8")

MARKER = (
    'MarketScope Portfolio Split Simulator v33 - v5.9.75 persistent Build Simulation withdrawal tabs + annual reset inside withdrawal tabs + annual reset withdrawal factor + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
)


def test_release_version_5968():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "5.9.75"
    assert "v5.9.75" in APP


def test_pdf_contract_bumped_to_v26():
    assert APP.count(MARKER) >= 2


def test_pdf_total_invested_box_contains_annual_withdrawal_summary():
    for token in [
        "def _page1_withdrawal_lines()",
        'f"ANNUAL WITHDRAWAL {_money(amount)}"',
        'f"REBALANCED {_money(rb_end)}  |  NOT-REBAL {_money(nr_end)}"',
        'f"REBALANCE DIFF {_money(rb_end - nr_end, signed=True)}  |  POSITIVE YRS RB {rb_pos}/{rb_years} NR {nr_pos}/{nr_years}"',
        "box_h = 70 if withdrawal_lines else 54",
        "if i == 0 and withdrawal_lines:",
    ]:
        assert token in PDF


def test_pdf_total_invested_box_contains_monthly_withdrawal_summary():
    for token in [
        'f"MONTHLY WITHDRAWAL {_money(amount)}"',
        'f"REBALANCE DIFF {_money(rb_end - nr_end, signed=True)}  |  POSITIVE RB {rb_pos}/{rb_total} NR {nr_pos}/{nr_total}"',
        'record.get("monthly_positive_months_rebalanced")',
        'record.get("monthly_positive_months_not_rebalanced")',
    ]:
        assert token in PDF


def _registry_functions():
    tree = ast.parse(APP)
    names = {
        "_valid_price_target",
        "_price_target_registry",
        "_remember_price_targets",
        "_apply_remembered_price_targets",
    }
    return [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]


def test_market_table_target_registry_transcribes_exact_values_into_blank_pdf_source():
    ns = {
        "pd": pd,
        "np": np,
        "_PRICE_TARGET_REGISTRY_FALLBACK": {},
    }
    exec(compile(ast.Module(body=_registry_functions(), type_ignores=[]), "app.py", "exec"), ns)

    table = pd.DataFrame([
        {
            "Symbol": "SCCO",
            "Price Target Low": 180.0,
            "Price Target Average": 225.0,
            "Price Target High": 260.0,
            "Price Target Source": "Market Table",
            "Price Target Updated ET": "Sep 02, 2026 10:00 AM EDT",
        }
    ])
    ns["_remember_price_targets"](table, ["SCCO"], source_context="Market Table")

    blank = pd.DataFrame([
        {
            "Symbol": "SCCO",
            "Price Target Low": np.nan,
            "Price Target Average": np.nan,
            "Price Target High": np.nan,
            "Price Target Source": "",
            "Price Target Updated ET": "—",
        }
    ])
    out = ns["_apply_remembered_price_targets"](blank, ["SCCO"])
    row = out.iloc[0]
    assert row["Price Target Low"] == 180.0
    assert row["Price Target Average"] == 225.0
    assert row["Price Target High"] == 260.0
    assert row["Price Target Source"] == "Market Table"


def test_market_table_explicitly_captures_targets_for_pdf_handoff():
    assert '_remember_price_targets(table_df, table_target_symbols, source_context="Market Table")' in APP
    assert "Authoritative PDF handoff" in APP


def test_pdf_enrichment_reuses_market_table_registry_after_hydration():
    assert "lookup_source = _apply_remembered_price_targets(lookup_source, symbols)" in APP
    for token in [
        '("price_target_low", "Price Target Low")',
        '("price_target_average", "Price Target Average")',
        '("price_target_high", "Price Target High")',
    ]:
        assert token in APP
    assert 'f"LOW {low}   AVG/CONS {avg}   HIGH {high}"' in PDF


def test_save_manage_withdrawal_summary_is_preserved_and_inline_for_saved_cards():
    assert "ACTIVE ANNUAL WITHDRAWAL SUMMARY" in APP
    assert "ACTIVE MONTHLY WITHDRAWAL SUMMARY" in APP
    assert "_saved_simulation_withdrawal_inline_html(rec)" in APP
