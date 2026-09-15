import base64
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import numpy as np
from pypdf import PdfReader
from future_projection import build_pdf_export, run_future_projection
from projection_dashboard_pdf import array, chart_color
from test_v510_future_projection import market_fixture, base_inputs, YEARS
import simulation_retirements as retirement


def test_dashboard_contains_populated_results_and_selected_graph():
    result = run_future_projection(market_fixture(), base_inputs(), YEARS)
    result['export_chart'] = {'view':'Portfolio Balance', 'data':[
        {'x':['2026','2027'], 'y':[10,20], 'name':'Selected P75', 'line':{'color':'#14B8A6','dash':'dash'}},
        {'x':['2026','2027'], 'y':[30,40], 'name':'Hidden P90', 'visible':'legendonly'},
    ]}
    text = '\n'.join(p.extract_text() for p in PdfReader(BytesIO(build_pdf_export(result))).pages)
    for label in ['Current market environment','Projection results','Selected Holdings','Allocation',
                  'Projection Confidence Explanation','Selected P75','Detailed projection tables',
                  'Rebalanced','Non-Rebalanced','2026','2027']:
        assert label in text
    assert 'Hidden P90' not in text
    for payload in result['strategies'].values():
        for col in payload['table'].columns:
            assert col in text.replace('\n',' ') or col == 'Period'


def test_plotly_binary_arrays_and_band_colors():
    a=np.array([1.,2.])
    assert array({'dtype':'f8','bdata':base64.b64encode(a.tobytes()).decode()}) == [1.,2.]
    color=chart_color('rgba(0,128,255,0.1)')
    assert (color.red,color.green,color.blue)==(0,128/255,1)


def test_retirement_removes_only_requested_record_and_pdf(tmp_path,monkeypatch):
    monkeypatch.setattr(retirement,'_started',True)
    retired={'id':next(iter(retirement.RETIRED_IDS)),'name':'Simulation 9/9/2026'}
    kept={'id':'unrelated','name':'Simulation 9/9/2026','nested':{'value':23}}
    data=tmp_path/'data';data.mkdir()
    for name in ['saved_portfolio_simulations.json','saved_portfolio_simulations.bootstrap.json']:
        (data/name).write_text(json.dumps([retired,kept]))
    pdf=tmp_path/'static'/'generated_pdfs';pdf.mkdir(parents=True)
    (pdf/f"{retired['id']}.pdf").write_bytes(b'old')
    (pdf/'unrelated.pdf').write_bytes(b'keep')
    retirement.apply_retirements(data)
    for path in data.glob('*.json'):
        assert json.loads(path.read_text()) == [kept]
    assert not (pdf/f"{retired['id']}.pdf").exists()
    assert (pdf/'unrelated.pdf').read_bytes()==b'keep'
    assert retirement.active_records([retired,kept])==[kept]


def test_remote_retirement_uses_current_sha_and_preserves_other_records(tmp_path,monkeypatch):
    import requests
    import pdf_storage
    retired={'id':next(iter(retirement.RETIRED_IDS))}
    kept={'id':'newer-remote-save','nested':[1,2,3]}
    blob={'sha':'current-sha','content':base64.b64encode(json.dumps([retired,kept]).encode()).decode()}
    response=Mock(status_code=200);response.json.return_value=blob
    missing=Mock(status_code=404)
    monkeypatch.setenv('MARKETSCOPE_GITHUB_TOKEN','test')
    monkeypatch.setattr(requests,'get',Mock(side_effect=[response,missing]))
    put=Mock(return_value=Mock(status_code=200));monkeypatch.setattr(requests,'put',put)
    delete=Mock(return_value=(True,'removed'));monkeypatch.setattr(pdf_storage,'delete_pdf_artifact',delete)
    retirement._remote_cleanup(tmp_path)
    body=put.call_args.kwargs['json']
    assert body['sha']=='current-sha'
    assert json.loads(base64.b64decode(body['content']))==[kept]
    assert delete.call_args.args[0] == retired
