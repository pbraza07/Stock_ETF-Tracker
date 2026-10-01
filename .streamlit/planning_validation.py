"""Strict point-in-time snapshot protocol; missing evidence is never certified."""
from copy import deepcopy
import numpy as np
import pandas as pd

REQUIRED={'universe','prices','fundamentals','macro','sectors'}

def freeze_snapshot(records,cutoff):
    cutoff=pd.Timestamp(cutoff)
    eligible=[]
    for record in records:
        if not all(k in record for k in ('available_at','observation_date','kind','key','value')):
            raise ValueError('Point-in-time rows require available_at, observation_date, kind, key and value.')
        available=pd.Timestamp(record['available_at']);observed=pd.Timestamp(record['observation_date'])
        if available<=cutoff and observed<=cutoff:eligible.append(deepcopy(record))
    # Retain latest vintage as known at cutoff, not the latest revised value today.
    latest={}
    for row in sorted(eligible,key=lambda r:pd.Timestamp(r['available_at'])):latest[(row['kind'],row['key'],row['observation_date'])]=row
    return sorted(latest.values(),key=lambda r:(pd.Timestamp(r['observation_date']),pd.Timestamp(r['available_at'])))

def walk_forward(records,cutoffs,select,forecast,realize,horizons=(1,3,5,10),delisted_coverage=False):
    """Selection and prediction receive only cutoff-frozen rows; realization is separate.

    Caller must supply a verified historical membership universe and terminal
    delisted returns. Timestamps alone cannot verify vendor data provenance.
    """
    output=[]
    for cutoff in cutoffs:
        frozen=freeze_snapshot(records,cutoff)
        kinds={r['kind'] for r in frozen}
        integrity='FULL' if REQUIRED<=kinds and delisted_coverage else 'PARTIAL' if len(kinds)>=3 else 'LIMITED'
        selected=select(deepcopy(frozen),cutoff)
        for horizon in horizons:
            prediction=forecast(deepcopy(frozen),list(selected),cutoff,horizon)
            actual=realize(list(selected),cutoff,horizon)
            if actual is None:continue
            output.append({'Cutoff':str(cutoff),'Horizon':horizon,'End':str(pd.Timestamp(cutoff)+pd.DateOffset(years=horizon)),
                'Selected':selected,'Integrity':integrity,'Survivorship complete':bool(delisted_coverage),
                **prediction,'Realized CAGR':actual['cagr'],'Realized volatility':actual.get('volatility')})
    return output

def calibration(records):
    if not records:return {'Point-in-Time Integrity':'LIMITED','Survivorship Status':'Historical calibration contains survivorship limitations.',
        'Independent Test Periods':0,'Calibration Confidence':'UNVALIDATED','Projection Bias':None,
        'Bias interpretation':'No verified out-of-sample forecast records; no bias correction applied.'}
    # Nonoverlapping tests per horizon; multiple portfolios on one date are not independent evidence.
    reports=[]
    for horizon in sorted({r['Horizon'] for r in records}):
        independent=[];end=None
        for r in sorted([r for r in records if r['Horizon']==horizon],key=lambda x:x['Cutoff']):
            if end is None or pd.Timestamp(r['Cutoff'])>=end:independent.append(r);end=pd.Timestamp(r['End'])
        if not independent:continue
        actual=np.array([r['Realized CAGR'] for r in independent]);median=np.array([r['P50'] for r in independent])
        covered=lambda low,high:float(np.mean([(r[low]<=r['Realized CAGR']<=r[high]) for r in independent]))
        full=all(r['Integrity']=='FULL' and r['Survivorship complete'] for r in independent)
        reports.append({'Horizon':horizon,'Independent Test Periods':len(independent),'P10-P90 Coverage':covered('P10','P90'),
            'P25-P75 Coverage':covered('P25','P75'),'Projection Bias':float(np.mean(actual-median)),
            'Median forecast error':float(np.median(actual-median)), 'Directional accuracy':float(np.mean(np.sign(actual)==np.sign(median))),
            'Volatility error':float(np.mean([r['Realized volatility']-r['Projected volatility'] for r in independent if r.get('Realized volatility') is not None and r.get('Projected volatility') is not None])) if any(r.get('Realized volatility') is not None and r.get('Projected volatility') is not None for r in independent) else None,
            'Point-in-Time Integrity':'FULL' if full else 'PARTIAL' if all(r['Integrity']!='LIMITED' for r in independent) else 'LIMITED',
            'Calibration Confidence':'MODERATE' if full and len(independent)>=20 else 'LOW',
            'Survivorship Status':'Verified by supplied dataset manifest' if full else 'Historical calibration contains survivorship limitations.'})
    return {'by_horizon':reports,'Point-in-Time Integrity': 'FULL' if all(x['Point-in-Time Integrity']=='FULL' for x in reports) else 'LIMITED',
        'Independent Test Periods':max([r['Independent Test Periods'] for r in reports],default=0),
        'Calibration Confidence':'LOW','Projection Bias':reports[0]['Projection Bias'] if reports else None,
        'Bias interpretation':'Realized minus projected P50; negative means overprediction. Horizons are not pooled as independent tests.'}

def past_bias_adjustment(records,forecast_date,horizon):
    available=[r for r in records if r['Horizon']==horizon and pd.Timestamp(r['End'])<pd.Timestamp(forecast_date)
               and r.get('Integrity')=='FULL' and r.get('Survivorship complete')]
    report=calibration(available)
    if report['Independent Test Periods']<10:return 0.
    return float(np.clip(report['Projection Bias'],-.03,.03))
