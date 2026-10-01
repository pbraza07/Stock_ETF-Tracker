import os
import tomllib
from pathlib import Path
from production_runtime import configure
from start_marketscope import command

def test_resource_limits_apply_before_start(monkeypatch):
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
        monkeypatch.setenv(key,'32')
    monkeypatch.delenv('MARKETSCOPE_NUMERIC_THREADS',raising=False)
    assert configure()=='1'
    assert os.environ['OPENBLAS_NUM_THREADS']=='1'
    monkeypatch.setenv('MARKETSCOPE_NUMERIC_THREADS','2')
    assert configure()=='2'

def test_production_reconnect_and_watcher_config():
    cfg=tomllib.loads(Path('.streamlit/config.toml').read_text())['server']
    assert not cfg['runOnSave'] and cfg['fileWatcherType']=='none'
    assert cfg['disconnectedSessionTTL']==1800
    assert cfg['websocketPingInterval']==30
    assert '--server.disconnectedSessionTTL=1800' in command()
    assert 'startCommand: python start_marketscope.py' in Path('render.yaml').read_text()

def test_connection_probe_stops_on_rate_limit(monkeypatch):
    from scripts import check_connection as probe
    from urllib.error import HTTPError
    from email.message import Message
    calls=[];headers=Message();headers['Retry-After']='60';headers['Set-Cookie']='secret'
    def fail(req,timeout):
        calls.append(req.full_url)
        raise HTTPError(req.full_url,429,'Too Many Requests',headers,None)
    monkeypatch.setattr(probe,'urlopen',fail)
    rows=probe.check('https://example.com')
    assert len(calls)==1 and rows[0]['status']==429
    assert rows[0]['headers']=={'Retry-After':'60'}
