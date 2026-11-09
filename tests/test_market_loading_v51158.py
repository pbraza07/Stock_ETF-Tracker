import ast
from pathlib import Path
import pandas as pd
import numpy as np
from types import SimpleNamespace
from streamlit.testing.v1 import AppTest

SOURCE=(Path(__file__).parents[1]/'app.py').read_text()


def assembly():
    tree=ast.parse(SOURCE)
    funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('blank_row','assemble_market')]
    ns=dict(pd=pd,np=np,List=list,default_meta={'A':{'Type':'Stock','Sector':'Technology'}},
        ALL_RETURN_COLS=['YTD','2025'],PRICE_TARGET_COLS=['Price Target Low'],
        SIGNAL_COLS=['Short Buy','Long Buy','Fundamental Buy'],
        st=SimpleNamespace(session_state=SimpleNamespace(session_rows={})))
    exec(compile(ast.Module(body=funcs,type_ignores=[]),'app.py','exec'),ns)
    return ns


def test_empty_market_has_full_schema_and_filter_is_safe():
    ns=assembly();frame=ns['assemble_market']([],pd.DataFrame())
    assert frame.empty
    assert {'Type','Symbol','Sector','Price','YTD','Analyst Rating'}.issubset(frame.columns)
    assert frame.loc[frame.Type.astype(str).str.upper().eq('STOCK')].empty


def test_partial_snapshot_merges_metadata_and_missing_values_stay_unknown():
    ns=assembly()
    frame=ns['assemble_market'](['A','UNKNOWN'],pd.DataFrame({'Symbol':['A'],'Price':[100.]})).set_index('Symbol')
    assert frame.loc['A','Type']=='Stock' and frame.loc['A','Price']==100.
    assert frame.loc['UNKNOWN','Type']=='Unknown'
    assert pd.isna(frame.loc['UNKNOWN','Price'])
    assert pd.isna(frame.loc['A','2025'])


def test_partial_session_overlay_preserves_snapshot_evidence():
    ns=assembly();ns['st'].session_state.session_rows={'A':{'Price':120.}}
    frame=ns['assemble_market'](['A'],pd.DataFrame({'Symbol':['A'],'2025':[15.],'Price':[100.]}))
    assert frame.iloc[0]['2025']==15. and frame.iloc[0]['Price']==120.
    assert frame.iloc[0]['Type']=='Stock'


def test_malformed_and_duplicate_snapshot_do_not_crash():
    ns=assembly()
    assert ns['assemble_market'](['A'],pd.DataFrame({'Price':[100.]})).iloc[0]['Type']=='Stock'
    frame=ns['assemble_market'](['A'],pd.DataFrame({'Symbol':['A','A'],'Price':[100.,110.]}))
    assert frame.iloc[0].Price==110.


def test_actual_navigation_controls_data_loading_without_losing_selection():
    start=SOURCE.index('_top_tab_labels = [')
    end=SOURCE.index('if _active_workspace not in',start)
    navigation=SOURCE[start:end]
    app=AppTest.from_string('import streamlit as st\n'+navigation+'''
if _active_workspace not in ('📰 Market News','Recession Indicators'):
    st.session_state.loads=st.session_state.get('loads',0)+1
st.write('Active: '+_active_workspace)
''').run()
    assert not app.exception and 'loads' not in app.session_state
    for label in ['◈ Market Navigator','◫ Portfolio Simulator','Favorite Picks','Future Projection','◈ Sector Performance']:
        app.session_state.workspace_navigation=label
        app.run()
        assert not app.exception
        assert any(m.value=='Active: '+label for m in app.markdown)
    assert app.session_state.loads==5
    app.session_state.workspace_navigation='Recession Indicators';app.run()
    assert app.session_state.loads==5
    app.session_state.future_projection_focus=True;app.run();app.run()
    assert app.session_state.workspace_navigation=='Future Projection'
    assert app.session_state.loads==7
    # No second tabs declaration with a different default/identity.
    assert navigation.count('render_navigation(_top_tab_labels)')==1
    assert SOURCE.index('_workspace_tabs = st.tabs') < SOURCE.index('    snapshot = load_snapshot()',start)
