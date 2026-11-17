"""Non-blocking display downloads; calculation inputs remain unchanged."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import RLock
import time

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='workspace-display')
_lock = RLock()
_entries = {}


def request(key, loader, fallback, *, ttl=21600, force=False):
    """Single-flight refresh, returning last-good data immediately.

    Public display data only. No Streamlit calls in loader/fallback. A failed
    refresh retains observations and retries after 60 seconds, not every rerun.
    """
    with _lock:
        entry = _entries.get(key)
        if entry is None:
            entry = {'value': fallback(), 'expires': 0, 'future': None}
            _entries[key] = entry
        future = entry['future']
        if future is not None and future.done():
            try:
                result = future.result()
                if result.get('data'):
                    entry['value'] = result
                else:
                    entry['value'] = {**entry['value'], 'error': result.get('error'),
                        'status': 'Stale cache' if entry['value'].get('data') else 'Unavailable'}
                success = result.get('status') in ('Updated', 'Cached')
                entry['expires'] = time.monotonic() + (ttl if success else 60)
            except Exception:
                entry['value'] = {**entry['value'], 'error': 'Background refresh failed',
                    'status': 'Stale cache' if entry['value'].get('data') else 'Unavailable'}
                entry['expires'] = time.monotonic() + 60
            entry['future'] = None
        if entry['future'] is None and (force or time.monotonic() >= entry['expires']):
            entry['future'] = _pool.submit(loader)
        return deepcopy(entry['value']), entry['future'] is not None


def local_recession_snapshot(series):
    """Read verified disk data only: never contact a provider during navigation."""
    import json
    from macro_data import CACHE_DIR
    from macro_snapshots import ROOT, validate_snapshot
    values = []
    for directory in (CACHE_DIR, ROOT):
        try:
            value = json.loads((directory / f'{series}.json').read_text())
            value = validate_snapshot({**value, 'key': series}, series)
            values.append(value)
        except (OSError, ValueError, KeyError, TypeError, AssertionError):
            pass
    if values:
        return {**max(values, key=lambda v: v['retrieved_at']), 'status': 'Saved snapshot', 'error': None}
    return {'data': [], 'retrieved_at': None, 'status': 'Loading', 'error': None}


def reuse_market(state, inputs, loader):
    """One exact-input assembly per session, never cache calculations or quotes.

    Inputs include the entire snapshot, universe metadata and session overrides.
    Copy on read prevents view styling/enrichment from altering the saved frame.
    """
    import hashlib
    import pickle
    signature = hashlib.sha256(pickle.dumps(inputs, protocol=5)).digest()
    previous = state.get('_assembled_market_view')
    if previous is None or previous[0] != signature:
        previous = (signature, loader().copy(deep=True))
        state['_assembled_market_view'] = previous
    return previous[1].copy(deep=True)
