"""Observed-only joint bootstrap with past-only recency-weight selection."""
import numpy as np
import pandas as pd


def prepare_history(model, weights):
    frequency = 'Monthly' if model.period_frequency == 'Monthly' else 'Annual'
    per_year = 12 if frequency == 'Monthly' else 1
    h = model.historical_returns
    h = h[h['Frequency'].eq(frequency) & h['Data Status'].eq('Observed')]
    pivot = h.pivot_table(index='Period', columns='Ticker', values='Return', aggfunc='last')
    pivot = pivot.reindex(columns=model.symbols).sort_index().dropna()
    if len(pivot) < 5 * per_year:
        raise ValueError('Historical-Calibrated requires five years of shared observed history. Use the existing model for shorter histories.')
    dates = pd.PeriodIndex(pivot.index, freq='M' if per_year == 12 else 'Y')
    # Do not stitch separated observations into a supposedly continuous block.
    if len(dates)>1 and np.any(np.diff(dates.asi8)!=1):
        raise ValueError('Historical-Calibrated requires contiguous shared observed periods; history contains gaps.')
    matrix = pivot.to_numpy(dtype=float)
    logs = np.log1p(np.clip(matrix @ weights, -.999999, None))
    candidates = (0., .25, .5)
    errors = {c: [] for c in candidates}
    audit = []
    for origin in range(5*per_year, len(matrix)-per_year+1, per_year):
        chosen = min(candidates, key=lambda c: np.mean(errors[c]) if errors[c] else 0.)
        train = logs[:origin]
        for horizon in (1,3,5):
            stop = origin+horizon*per_year
            if stop>len(matrix): continue
            actual = float(np.mean(logs[origin:stop])*per_year)
            forecasts = {c: float(((1-c)*np.mean(train)+c*np.mean(train[-5*per_year:]))*per_year) for c in candidates}
            audit.append({'Training through':str(pivot.index[origin-1]),'Outcome through':str(pivot.index[stop-1]),'Horizon':horizon,'Recent weight':chosen,'Absolute log-growth error':abs(forecasts[chosen]-actual)})
        # Only one-year outcomes are used for sequential tuning, so future
        # multi-year outcomes cannot leak into the next origin's choice.
        actual = float(np.mean(logs[origin:origin+per_year])*per_year)
        for c in candidates:
            forecast = ((1-c)*np.mean(train)+c*np.mean(train[-5*per_year:]))*per_year
            errors[c].append(abs(forecast-actual))
    chosen = min(candidates,key=lambda c: np.mean(errors[c]) if errors[c] else 0.)
    return matrix, {'recent_weight':chosen,'periods_per_year':per_year,'shared_periods':len(matrix),
                    'walk_forward':audit,'status':'Historical calibration only; not proof of predictive superiority. Current holdings introduce selection bias.'}


def sample_indices(periods, simulations, rows, per_year, recent_weight, seed):
    rng=np.random.default_rng(seed)
    block=min(6 if per_year==12 else 2,rows)
    starts=np.arange(rows-block+1)
    p=np.full(len(starts),(1-recent_weight)/len(starts))
    recent=starts>=max(0,rows-5*per_year)
    p[recent]+=recent_weight/recent.sum()
    out=np.empty((periods,simulations),dtype=int)
    for offset in range(0,periods,block):
        begin=rng.choice(starts,size=simulations,p=p)
        size=min(block,periods-offset)
        out[offset:offset+size]=begin[None,:]+np.arange(size)[:,None]
    return out
