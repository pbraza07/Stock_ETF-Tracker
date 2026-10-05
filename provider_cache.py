"""Reusable per-symbol source cache; never silently return an expired quote."""
from functools import wraps
import time,os
from performance_store import get,put,key_for,lease,unlock
from shared_cache import cached

def acquire_provider_slot():
    cooldown=get('provider:yahoo:cooldown')
    if cooldown and cooldown[2]>time.time():raise RuntimeError('Yahoo source cooling down after an unavailable response')
    interval=float(os.getenv('MARKETSCOPE_PROVIDER_INTERVAL','0.25'))
    end=time.monotonic()+30
    while not lease('provider:yahoo:rate',max(.01,interval)):
        if time.monotonic()>end:raise TimeoutError('Provider request budget is busy')
        time.sleep(.05)

def symbol_cache(ttl):
    def decorate(fn):
        @wraps(fn)
        def wrapped(self,symbol,*args,**kwargs):
            symbol=str(symbol).strip().upper()
            def fetch():
                acquire_provider_slot()
                return fn(self,symbol,*args,**kwargs)
            return cached('yahoo:'+fn.__name__,(symbol,args,kwargs),
                fetch,ttl=ttl,default={},
                valid=lambda value:bool(value))
        return wrapped
    return decorate

def histories_cache(fn):
    @wraps(fn)
    def wrapped(self,symbols,*args,**kwargs):
        symbols=sorted(set(self._clean_symbols(symbols)));out={};missing=[]
        keys={s:key_for('adjusted-daily:'+fn.__name__,(s,args,kwargs)) for s in symbols}
        for symbol in symbols:
            row=get(keys[symbol])
            if row and row[2]>time.time():out[symbol]=row[0]
            else:missing.append(symbol)
        if missing:
            # Dataset lock coalesces identical sets across users, with bounded wait.
            lock=key_for('history-request',(fn.__name__,tuple(missing),args,kwargs))
            acquired=lease(lock,120)
            if not acquired:
                until=time.monotonic()+30
                while time.monotonic()<until:
                    rows={s:get(keys[s]) for s in missing}
                    if all(r and r[2]>time.time() for r in rows.values()):
                        out.update({s:r[0] for s,r in rows.items()});return out
                    time.sleep(.1)
                return out
            try:
                acquire_provider_slot()
                rows=fn(self,missing,*args,**kwargs)
                if not rows:put("provider:yahoo:cooldown",True,60)
                for symbol,value in rows.items():
                    if value is not None and not value.empty:
                        put(keys[symbol],value,1800);out[symbol]=value
            finally:unlock(lock,acquired)
        return out
    return wrapped
