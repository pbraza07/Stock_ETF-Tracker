"""Scheduled shared data collection: python collect_public_data.py."""
from performance_store import put,key_for,lease
import persistence

def main():
    jobs=[('load_remote_snapshot',{}),('load_remote_metadata',{}),('load_remote_universe_metadata',{}),
          ('load_remote_universe_change_history',{'timeout':10}),('load_remote_favorite_picks_history',{'timeout':10})]
    for name,kwargs in jobs:
        loader=getattr(persistence,name)
        try:
            value=loader(**kwargs)
            valid=value is not None and (not value.empty if hasattr(value,'empty') else bool(value))
            if valid:put(key_for('remote:'+name,((),kwargs)),value,900)
        except Exception:pass  # Retain prior observations and their original timestamps.
    from news_background import collect_now
    token=lease('news:refresh',300)
    if token:collect_now(token)
if __name__=='__main__':main()
