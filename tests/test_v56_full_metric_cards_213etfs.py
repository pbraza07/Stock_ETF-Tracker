from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_every_requested_metric_is_rendered_inside_cards():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "def _performance_cells" in app
    assert "for metric in PERF_COLS" in app
    assert "performance-grid" in app
    assert "full-metrics-card" in app


def test_every_metric_and_rating_is_sortable_by_clickable_button():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'SORT_OPTIONS = ["Market Cap", *PERF_COLS, "Rating"]' in app
    assert 'key=f"sort_card_{option}"' in app
    assert '"↓ High → Low"' in app
    assert '"↑ Low → High"' in app


def test_supplied_universe_and_allowlist_use_exactly_213_etfs():
    generated = pd.read_csv(ROOT / "data" / "default_universe.csv")
    bootstrap = pd.read_csv(ROOT / "data" / "default_universe.bootstrap.csv")
    allow = pd.read_csv(ROOT / "data" / "etf_allowlist.csv")
    generated_etfs = set(generated.loc[generated["Type"].eq("ETF"), "Symbol"].astype(str).str.upper())
    bootstrap_etfs = set(bootstrap.loc[bootstrap["Type"].eq("ETF"), "Symbol"].astype(str).str.upper())
    allow_etfs = set(allow["Symbol"].astype(str).str.upper())
    assert len(generated_etfs) == 213
    assert len(bootstrap_etfs) == 213
    assert len(allow_etfs) == 213
    assert generated_etfs == bootstrap_etfs == allow_etfs


def test_card_css_supports_full_metric_grid_and_mobile():
    css = (ROOT / "styles.css").read_text(encoding="utf-8")
    for token in [".performance-grid", ".perf-cell", ".full-metrics-card", "@media (max-width: 480px)"]:
        assert token in css
