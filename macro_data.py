"""Bounded public-data downloads with explicit, durable last-valid fallback."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import requests

CACHE_DIR = Path(__file__).parent / 'data' / 'macro_cache'


def cached_download(key, url, parse, ttl, force=False, cache_dir=None):
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
        response = requests.get(url, timeout=(4,10), headers={'User-Agent':'MarketScope economic dashboard', 'Accept':'text/csv,text/html;q=0.9'})
        response.raise_for_status()
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
        message = f'{type(exc).__name__}: {str(exc)[:160]}'
        if previous is not None:
            return {**previous, 'status':'Stale cache', 'error':message}
        return {'data':[], 'retrieved_at':None, 'source':url, 'status':'Unavailable', 'error':message}
