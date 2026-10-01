"""Bounded public-data downloads with explicit, durable last-valid fallback."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import requests

CACHE_DIR = Path(__file__).parent / 'data' / 'macro_cache'


def cached_download(key, url, parse, ttl, force=False, cache_dir=None, params=None,
                    timeout=(4,10), attempts=1):
    directory = Path(cache_dir) if cache_dir is not None else CACHE_DIR
    path = directory / f'{key}.json'
    previous = None
    try:
        previous = json.loads(path.read_text())
        age = (datetime.now(timezone.utc)-datetime.fromisoformat(previous['retrieved_at'])).total_seconds()
        if age < ttl and not force:
            return {**previous, 'status':'Cached', 'error':None}
    except (OSError, ValueError, KeyError, TypeError):
        previous = None
    try:
        for attempt in range(max(1, attempts)):
            try:
                response = requests.get(url, params=params, timeout=timeout, headers={'User-Agent':'MarketScope economic dashboard', 'Accept':'application/json,text/csv,text/html;q=0.9'})
                response.raise_for_status()
                break
            except requests.RequestException as failure:
                status = getattr(getattr(failure, 'response', None), 'status_code', None)
                transient = isinstance(failure, (requests.Timeout, requests.ConnectionError)) or status in (429,500,502,503,504)
                if not transient or attempt + 1 >= max(1, attempts):
                    raise
        data = parse(response.text)
        result = {'data':data, 'retrieved_at':datetime.now(timezone.utc).isoformat(), 'source':url}
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', dir=directory, delete=False, suffix='.tmp') as file:
                json.dump(result, file, allow_nan=False)
                temp = file.name
            os.replace(temp, path)
        except OSError:
            pass  # Successful live data remain usable on read-only storage.
        return {**result, 'status':'Updated', 'error':None}
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        code = getattr(getattr(exc, 'response', None), 'status_code', None)
        message = f'HTTP {code}' if code else type(exc).__name__
        if isinstance(exc, ValueError): message = 'Invalid or changed provider response'
        # Never expose exception URLs: API query strings can contain credentials.
        if previous is not None:
            return {**previous, 'status':'Stale cache', 'error':message}
        return {'data':[], 'retrieved_at':None, 'source':url, 'status':'Unavailable', 'error':message}
