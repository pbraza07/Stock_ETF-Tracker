"""Immutable, explicitly requested paper research snapshots; no trade execution."""
import json
import os
from pathlib import Path
from uuid import uuid4

def save_record(payload,root=None):
    from persistence import _put_text_file
    root=Path(root) if root else Path(__file__).resolve().parent/'data'/'quality_paper_records'
    root.mkdir(parents=True,exist_ok=True)
    record_id=uuid4().hex
    text=json.dumps(payload,indent=2,allow_nan=False)
    path=root/(record_id+'.json')
    with path.open('x',encoding='utf-8') as f:f.write(text)
    token=os.environ.get('MARKETSCOPE_GITHUB_TOKEN','').strip()
    if not token:return record_id,False,'Saved on this server only; download a backup because hosted local storage may be ephemeral.'
    ok,message=_put_text_file('data/quality_paper_records/'+path.name,text,'data: immutable quality opportunity paper snapshot',token)
    return record_id,ok,message
