"""Narrow, user-requested deletion; never replace the rest of the saved library."""
import base64
import json
import logging
import os
from pathlib import Path
from threading import Lock, Thread

RETIRED_IDS = frozenset({'SIM-20260909-150352-604'})
_started = False
_lock = Lock()


def active_records(records):
    return [record for record in records if record.get('id') not in RETIRED_IDS]


def _remote_cleanup(base_dir):
    from portfolio_simulations import _headers, DEFAULT_REPO, DEFAULT_BRANCH
    from pdf_storage import delete_pdf_artifact
    import requests
    token = os.getenv('MARKETSCOPE_GITHUB_TOKEN', '').strip()
    if not token:
        return
    headers = _headers(token)
    for path in ('data/saved_portfolio_simulations.json', 'data/saved_portfolio_simulations.bootstrap.json'):
        url = f'https://api.github.com/repos/{DEFAULT_REPO}/contents/{path}'
        response = requests.get(url, headers=headers, params={'ref': DEFAULT_BRANCH}, timeout=8)
        if response.status_code == 404:
            continue
        response.raise_for_status()
        blob = response.json()
        records = json.loads(base64.b64decode(blob['content']))
        if not isinstance(records, list):
            raise ValueError('Refusing cleanup of unrecognized simulation library')
        kept = active_records(records)
        if len(kept) == len(records):
            continue
        # The fetched SHA prevents overwriting concurrent saves; retry next restart.
        response = requests.put(url, headers=headers, timeout=15, json={
            'message': 'Remove requested Simulation 9/9/2026 [skip render]',
            'sha': blob['sha'], 'branch': DEFAULT_BRANCH,
            'content': base64.b64encode((json.dumps(kept, indent=2)+'\n').encode()).decode(),
        })
        response.raise_for_status()
    for record_id in RETIRED_IDS:
        ok, detail = delete_pdf_artifact({'id': record_id}, base_dir, 'Remove requested simulation PDF')
        if not ok:
            logging.warning('Requested simulation PDF cleanup: %s', detail)


def apply_retirements(local_data_dir):
    """Remove only retired records/files locally; remote cleanup cannot block UI."""
    global _started
    root = Path(local_data_dir).parent
    for name in ('saved_portfolio_simulations.json', 'saved_portfolio_simulations.bootstrap.json'):
        path = Path(local_data_dir) / name
        if path.exists():
            try:
                records = json.loads(path.read_text())
                if isinstance(records, list):
                    kept = active_records(records)
                    if len(kept) != len(records):
                        path.write_text(json.dumps(kept, indent=2)+'\n')
            except (ValueError, OSError):
                logging.exception('Could not apply requested local simulation cleanup')
    for record_id in RETIRED_IDS:
        locations = [root/'static'/'generated_pdfs', root/'data'/'generated_pdfs']
        mirror = os.getenv('MARKETSCOPE_PDF_PERSIST_DIR', '').strip()
        if mirror:
            locations.append(Path(mirror).expanduser())
        for directory in locations:
            try:
                (directory / f'{record_id}.pdf').unlink(missing_ok=True)
            except OSError:
                logging.exception('Could not remove retired simulation PDF')
    with _lock:
        if _started:
            return
        _started = True
    def run():
        try:
            _remote_cleanup(root)
        except Exception:
            logging.exception('Requested GitHub simulation cleanup incomplete; retry on restart')
    Thread(target=run, name='simulation-retirement', daemon=True).start()
