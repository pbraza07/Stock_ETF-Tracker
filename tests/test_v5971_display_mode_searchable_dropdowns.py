from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'app.py').read_text(encoding='utf-8')


def test_release_version_5971():
    assert (ROOT / 'VERSION.txt').read_text(encoding='utf-8').strip() == '5.9.75'
    assert 'v5.9.75' in APP


def test_card_view_search_is_searchable_multiselect_dropdown():
    assert 'card_local_selection = st.multiselect(' in APP
    assert 'key="card_local_search_selector"' in APP
    assert 'placeholder="Search ticker, company / ETF name, type, or sector…"' in APP
    assert '_card_search_lookup' in APP
    assert "f\"{symbol} — {_card_search_lookup.get(symbol, {}).get('Name', symbol)}\"" in APP
    assert 'card_local_search = st.text_input(' not in APP


def test_table_view_search_is_searchable_multiselect_dropdown():
    assert 'table_local_selection = st.multiselect(' in APP
    assert 'key="table_local_search_selector"' in APP
    assert '_table_search_lookup' in APP
    assert 'table_local_search = st.text_input(' not in APP


def test_card_dropdown_filters_exact_selected_symbols_only_when_nonempty():
    assert '_card_selected_symbols = list(dict.fromkeys' in APP
    assert 'if _card_selected_symbols:' in APP
    assert 'isin(_card_selected_symbols)' in APP
    assert 'Remove selections from the dropdown to return to the full filtered Card View universe.' in APP


def test_table_dropdown_filters_exact_selected_symbols_only_when_nonempty():
    assert '_table_selected_symbols = list(dict.fromkeys' in APP
    assert 'if _table_selected_symbols:' in APP
    assert 'isin(_table_selected_symbols)' in APP
    assert 'Remove selections from the dropdown to return to the full filtered Table View universe.' in APP


def test_stale_dropdown_selections_are_sanitized_after_filters_change():
    assert '_card_valid_set = set(_card_search_options)' in APP
    assert 'st.session_state.card_local_search_selector = _card_saved_selection' in APP
    assert '_table_valid_set = set(_table_search_options)' in APP
    assert 'st.session_state.table_local_search_selector = _table_saved_selection' in APP


def test_search_labels_include_name_type_and_sector_like_comparison_selector():
    for token in [
        "_card_search_lookup.get(symbol, {}).get('Name', symbol)",
        "_card_search_lookup.get(symbol, {}).get('Type')",
        "_card_search_lookup.get(symbol, {}).get('Sector')",
        "_table_search_lookup.get(symbol, {}).get('Name', symbol)",
        "_table_search_lookup.get(symbol, {}).get('Type')",
        "_table_search_lookup.get(symbol, {}).get('Sector')",
    ]:
        assert token in APP


def test_pdf_contract_bumped_to_v29():
    marker = 'MarketScope Portfolio Split Simulator v33 - v5.9.75 persistent Build Simulation withdrawal tabs + annual reset inside withdrawal tabs + annual reset withdrawal factor + annual positive years + display-mode searchable dropdowns + six-month universe change history + saved-card inline withdrawal summary + PDF withdrawal summary + Market Table target transcription + required instrument market data on page 1'
    assert APP.count(marker) >= 2
