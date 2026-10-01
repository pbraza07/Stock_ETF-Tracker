"""Observed-history joint bootstrap with disclosed smoothing and recency tuning."""
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


class SmoothedHistory:
    """Moment-matched log-return kernel around each sampled historical block.

    The mixture's log mean/covariance at each block position are preserved in
    expectation. This does not promise identical arithmetic returns or tails.
    """
    def __init__(self, matrix, per_year, recent_weight, seed):
        if not np.isfinite(matrix).all() or np.any(matrix <= -1):
            raise ValueError('Smoothed history requires finite returns greater than -100%.')
        self.logs=np.log1p(matrix)
        self.block=min(6 if per_year==12 else 2,len(matrix))
        starts=np.arange(len(matrix)-self.block+1)
        p=np.full(len(starts),(1-recent_weight)/len(starts))
        recent=starts>=max(0,len(matrix)-5*per_year)
        p[recent]+=recent_weight/recent.sum()
        # Explicit conservative bandwidth policy, not an optimized accuracy claim.
        self.bandwidth=min(.25, len(matrix)**(-.2))
        self.rng=np.random.default_rng(np.random.SeedSequence([int(seed),734]))
        self.moments=[]
        for offset in range(self.block):
            values=self.logs[starts+offset]
            mean=p @ values
            residual=values-mean
            cov=(residual*p[:,None]).T @ residual
            eigenvectors_values, vectors=np.linalg.eigh(cov)
            root=vectors @ np.diag(np.sqrt(np.maximum(eigenvectors_values,0)))
            self.moments.append((mean,root))

    def draw(self, indices, period):
        mean,root=self.moments[period % self.block]
        h=self.bandwidth
        shocks=self.rng.normal(size=(len(indices),self.logs.shape[1])) @ root.T
        logs=mean+np.sqrt(1-h*h)*(self.logs[indices]-mean)+h*shocks
        return np.expm1(logs)
