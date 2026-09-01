from __future__ import annotations

import itertools
from pathlib import Path
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
SNAPSHOT_FILE = BASE_DIR / 'data' / 'market_snapshot.csv'
FALLBACK_FILE = BASE_DIR / 'data' / 'portfolio_combo_source_latest.csv'
REBALANCED_OUT = BASE_DIR / 'data' / 'top100_recession_balanced_rebalanced_10y.csv'
NOT_REBALANCED_OUT = BASE_DIR / 'data' / 'top100_recession_balanced_not_rebalanced_10y.csv'

STARTING_VALUE = 300_000.0
TOP_N = 100
SIM_YEARS = [str(y) for y in range(2016, 2026)]
RECESSION_STRESS_YEARS = ['2001', '2008', '2009', '2020']
NBER_SOURCE = 'https://www.nber.org/research/data/us-business-cycle-expansions-and-contractions'
NBER_PERIODS = 'Mar-Nov 2001; Dec 2007-Jun 2009; Feb-Apr 2020'
PROFIT_POOL_SIZE = 20
DEFENSE_POOL_SIZE = 20


def _source_frame() -> pd.DataFrame:
    for path in (SNAPSHOT_FILE, FALLBACK_FILE):
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if df.empty:
            continue
        if 'Symbol' not in df.columns and 'Stock' in df.columns:
            df = df.rename(columns={'Stock': 'Symbol'})
        if 'Name' not in df.columns:
            df['Name'] = df['Symbol']
        if 'Sector' not in df.columns:
            # MarketScope exports may use Industry as the best available category.
            df['Sector'] = df.get('Industry', 'Unknown')
        if 'Type' not in df.columns:
            df['Type'] = 'Stock'
        df['Symbol'] = df['Symbol'].astype(str).str.upper().str.strip()
        df['Sector'] = df['Sector'].fillna('Unknown').astype(str).str.strip()
        df['Name'] = df['Name'].fillna(df['Symbol']).astype(str).str.strip()
        df['Type'] = df['Type'].fillna('').astype(str).str.upper().str.strip()
        return df.drop_duplicates('Symbol', keep='last').reset_index(drop=True)
    raise RuntimeError('No MarketScope annual-return source file is available.')


def _numeric_years(df: pd.DataFrame) -> list[str]:
    cols = [str(c) for c in df.columns if str(c).isdigit() and len(str(c)) == 4]
    return sorted(cols, key=int)


def _compound(values: list[float]) -> float:
    value = 1.0
    for r in values:
        if not np.isfinite(r) or r <= -100.0:
            return np.nan
        value *= 1.0 + r / 100.0
    return value - 1.0


def _candidate_scores(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    annual_cols = _numeric_years(df)
    for col in annual_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    mask = df['Type'].eq('STOCK') & ~df['Sector'].str.lower().isin({'', 'unknown', 'nan', 'none'})
    mask &= df[SIM_YEARS].notna().all(axis=1)
    eligible = df.loc[mask].copy()
    if eligible.empty:
        raise RuntimeError('No stocks have complete 2016-2025 annual returns.')

    # Profit engines: strong full 10Y compounded outcome plus repeated positive years.
    profit_rows = []
    for idx, row in eligible.iterrows():
        vals = [float(row[y]) for y in SIM_YEARS]
        growth = _compound(vals)
        if not np.isfinite(growth):
            continue
        positive = sum(v > 0 for v in vals)
        worst = min(vals)
        cagr = (1.0 + growth) ** (1.0 / len(vals)) - 1.0 if growth > -1 else np.nan
        if positive < 6 or not np.isfinite(cagr) or cagr <= 0:
            continue
        profit_rows.append((idx, growth, cagr, positive, worst))
    profit_score = pd.DataFrame(profit_rows, columns=['idx','growth','cagr','positive','worst'])
    profit_score = profit_score.sort_values(['growth','positive','worst'], ascending=[False,False,False]).head(PROFIT_POOL_SIZE)
    profit = eligible.loc[profit_score['idx'].tolist()].copy()
    profit['Role Score'] = profit_score.set_index('idx').reindex(profit.index)['growth']
    profit['Role'] = 'Profit Engine'

    # Recession defense: use official NBER recession years represented by annual data.
    stress_years = [y for y in RECESSION_STRESS_YEARS if y in eligible.columns]
    defense_rows = []
    for idx, row in eligible.iterrows():
        vals = [float(row[y]) for y in stress_years if pd.notna(row.get(y))]
        if len(vals) < 2:
            continue
        worst = min(vals)
        avg = float(np.mean(vals))
        positive = sum(v > 0 for v in vals)
        # Maximin first, then average recession result, then number of positive recession years.
        defense_rows.append((idx, worst, avg, positive, len(vals)))
    defense_score = pd.DataFrame(defense_rows, columns=['idx','worst','avg','positive','count'])
    defense_score = defense_score.sort_values(['worst','avg','positive'], ascending=[False,False,False]).head(DEFENSE_POOL_SIZE)
    defense = eligible.loc[defense_score['idx'].tolist()].copy()
    defense['Recession Worst %'] = defense_score.set_index('idx').reindex(defense.index)['worst']
    defense['Recession Avg %'] = defense_score.set_index('idx').reindex(defense.index)['avg']
    defense['Recession Positive Years'] = defense_score.set_index('idx').reindex(defense.index)['positive']
    defense['Recession Observations'] = defense_score.set_index('idx').reindex(defense.index)['count']
    defense['Role'] = 'Recession Defense'
    return profit, defense, stress_years


def _simulate(indices: tuple[int,int,int,int], frame: pd.DataFrame, rebalance: bool) -> dict:
    rows = frame.loc[list(indices)]
    annual_returns = {}
    year_balances = {}
    if rebalance:
        balance = STARTING_VALUE
        for year in SIM_YEARS:
            year_ret = float(rows[year].mean())
            annual_returns[year] = year_ret
            balance *= 1.0 + year_ret / 100.0
            year_balances[year] = balance
        ending = balance
    else:
        holdings = np.full(4, STARTING_VALUE / 4.0, dtype='float64')
        for year in SIM_YEARS:
            start = float(holdings.sum())
            rets = rows[year].to_numpy(dtype='float64') / 100.0
            holdings *= 1.0 + rets
            ending_year = float(holdings.sum())
            annual_returns[year] = ((ending_year / start) - 1.0) * 100.0 if start > 0 else np.nan
            year_balances[year] = ending_year
        ending = float(holdings.sum())
    vals = [annual_returns[y] for y in SIM_YEARS]
    worst_i = int(np.nanargmin(vals))
    best_i = int(np.nanargmax(vals))
    return {
        'ending': ending,
        'annual_returns': annual_returns,
        'year_balances': year_balances,
        'worst_year': SIM_YEARS[worst_i],
        'worst_pct': vals[worst_i],
        'best_year': SIM_YEARS[best_i],
        'best_pct': vals[best_i],
    }


def _recession_metrics(indices: tuple[int,int], frame: pd.DataFrame, stress_years: list[str]) -> tuple[float,float,int,int]:
    # Recession metrics intentionally score only the two stocks assigned the Recession Defense role.
    values=[]
    for year in stress_years:
        vals=pd.to_numeric(frame.loc[list(indices), year], errors='coerce').dropna()
        if len(vals)==2:
            values.append(float(vals.mean()))
    if not values:
        return (np.nan,np.nan,0,0)
    return (min(values), float(np.mean(values)), sum(v>0 for v in values), len(values))


def _build(strategy_rebalanced: bool, frame: pd.DataFrame, profit: pd.DataFrame, defense: pd.DataFrame, stress_years: list[str]) -> pd.DataFrame:
    profit_indices=list(profit.index)
    defense_indices=list(defense.index)
    candidates=[]
    seen=set()
    for p1,p2 in itertools.combinations(profit_indices,2):
        for d1,d2 in itertools.combinations(defense_indices,2):
            combo=(p1,p2,d1,d2)
            if len(set(combo))<4:
                continue
            sectors=[str(frame.loc[i,'Sector']) for i in combo]
            if len(set(sectors))<4:
                continue
            key=tuple(sorted(str(frame.loc[i,'Symbol']) for i in combo))
            if key in seen:
                continue
            seen.add(key)
            sim=_simulate(combo,frame,strategy_rebalanced)
            rec_worst,rec_avg,rec_positive,rec_obs=_recession_metrics((d1,d2),frame,stress_years)
            if rec_obs < 2:
                continue
            candidates.append((sim['ending'],rec_worst,rec_avg,rec_positive,rec_obs,combo,sim))
    candidates.sort(key=lambda x:(x[0],x[1],x[2]), reverse=True)
    candidates=candidates[:TOP_N]
    rows=[]
    strategy='Rebalanced annually' if strategy_rebalanced else 'Not rebalanced'
    for rank,(_,rec_worst,rec_avg,rec_positive,rec_obs,combo,sim) in enumerate(candidates,1):
        row={'Rank':rank,'Combo':' + '.join(str(frame.loc[i,'Symbol']) for i in combo),'Strategy':strategy}
        for pos,i in enumerate(combo,1):
            role='Profit Engine' if pos<=2 else 'Recession Defense'
            row[f'Stock {pos}']=str(frame.loc[i,'Symbol'])
            row[f'Sector {pos}']=str(frame.loc[i,'Sector'])
            row[f'Name {pos}']=str(frame.loc[i,'Name'])
            row[f'Role {pos}']=role
        for year in reversed(SIM_YEARS):
            row[year]=sim['annual_returns'][year]
        row.update({
            'Worst Year':sim['worst_year'],'Worst Year %':sim['worst_pct'],
            'Best Year':sim['best_year'],'Best Year %':sim['best_pct'],
            'Defense Recession Worst %':rec_worst,'Defense Recession Avg %':rec_avg,
            'Defense Recession Positive Years':rec_positive,'Defense Recession Observations':rec_obs,
            'Recession Stress Years':','.join(stress_years),
            'Starting Value ($)':STARTING_VALUE,'Annual Withdrawal ($)':0.0,'Total Withdrawn ($)':0.0,
            'Remaining Balance ($)':sim['ending'],'Net Value incl. Withdrawals ($)':sim['ending'],
            'Net Profit incl. Withdrawals ($)':sim['ending']-STARTING_VALUE,
            'NBER Recession Periods':NBER_PERIODS,'NBER Source':NBER_SOURCE,
        })
        for year in SIM_YEARS:
            row[f'{year} Balance After Withdrawal ($)']=sim['year_balances'][year]
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    raw=_source_frame()
    profit,defense,stress_years=_candidate_scores(raw)
    # Use only rows present in either candidate pool, preserving original indexes for role selection.
    eligible=raw.copy()
    rb=_build(True,eligible,profit,defense,stress_years)
    nr=_build(False,eligible,profit,defense,stress_years)
    if len(rb)<TOP_N or len(nr)<TOP_N:
        raise RuntimeError(f'Expected {TOP_N} recession-balanced combinations, got {len(rb)} and {len(nr)}.')
    rb.to_csv(REBALANCED_OUT,index=False)
    nr.to_csv(NOT_REBALANCED_OUT,index=False)
    print(f'Profit engines considered: {len(profit)}; recession defenses: {len(defense)}; stress years: {stress_years}')
    print(f'Rebalanced #1: {rb.iloc[0]["Combo"]} -> ${rb.iloc[0]["Remaining Balance ($)"]:,.2f}')
    print(f'Not rebalanced #1: {nr.iloc[0]["Combo"]} -> ${nr.iloc[0]["Remaining Balance ($)"]:,.2f}')

if __name__=='__main__':
    main()
