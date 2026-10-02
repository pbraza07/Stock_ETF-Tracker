"""Show every current stock with explicit pass/fail/unavailable evidence."""
import pandas as pd
from quality_opportunities import universe,quality_table

RULES={
    'Quality score':('min_quality','>=','Quality'),
    'Target probability':('min_probability','>=','Target probability'),
    'Loss probability':('max_loss_probability','<=','Loss probability'),
    'Loss >20% probability':('max_severe_probability','<=','Severe loss'),
    'Worst-decile mean return':('max_tail_loss','>=','Worst-decile loss'),
}

def result_table(result,market,context=None):
    scored=result['table'];excluded=result['excluded'];cfg=result['settings']
    lookup={r['Ticker']:r for r in scored.to_dict('records')}
    reasons={r['Ticker']:r['Reason'] for r in excluded.to_dict('records')}
    quality={r['Ticker']:r for r in quality_table(market,context or {}).to_dict('records')}
    rows=[]
    for _,stock in universe(market).iterrows():
        symbol=stock['Symbol'];row=dict(Ticker=symbol,Company=stock.get('Name',symbol),Sector=stock.get('Sector'),Price=stock.get('Price'))
        if symbol not in lookup:
            row.update(quality[symbol])
            row.update(Qualifies=False,**{'Data status':'LIMITED','Evaluation notes':reasons.get(symbol,'No completed forecast; run evaluation to calculate return/risk estimates'),
                'Failed constraints':'Required evidence unavailable','Why selected':'Available quality evidence evaluated; no return estimates invented.'})
        else:row.update(lookup[symbol])
        notes=[];met=0;assessed=0
        for field,(key,operator,_) in RULES.items():
            actual=row.get(field);limit=-cfg[key] if field=='Worst-decile mean return' else cfg[key]
            if pd.isna(actual) or (field=='Quality score' and row.get('Evidence coverage',1)==0):
                notes.append(field+': unavailable evidence');continue
            assessed+=1
            failed=actual<limit if operator=='>=' else actual>limit
            if failed:
                fmt=(lambda v:f'{v:.1f}') if field=='Quality score' else (lambda v:f'{v:.1%}')
                notes.append(f'{field}: {fmt(actual)}; required {operator} {fmt(limit)}')
            else:met+=1
        extra=row.get('Evaluation notes','')
        if isinstance(extra,str) and extra:notes.append(extra)
        row.update({'Criteria met':met,'Criteria assessed':assessed})
        limited=assessed<len(RULES) or row.get('Data status')=='LIMITED'
        row['Qualifies']=bool(row.get('Qualifies',False)) and not limited and met==len(RULES)
        row.update(Status='EVALUATED — LIMITED DATA' if limited else 'MEETS ALL CRITERIA' if row['Qualifies'] else 'CRITERIA NOT MET',Notes='; '.join(notes) or 'All configured screening criteria met; probabilities remain uncalibrated.')
        rows.append(row)
    out=pd.DataFrame(rows)
    if not out.empty:
        # Most criteria met first; ties retain target-probability/quality ranking.
        ranks={s:i for i,s in enumerate(scored.get('Ticker',[]))}
        out['_order']=out.Ticker.map(ranks).fillna(len(ranks))
        out=out.sort_values(['Criteria met','_order','Ticker'],ascending=[False,True,True],na_position='last').drop(columns='_order').reset_index(drop=True)
        out.insert(0,'Rank',range(1,len(out)+1))
        out['Criteria met']=out['Criteria met'].astype('Int64')
    return out

def highlight(row,cfg):
    colors=pd.Series('',index=row.index)
    for field,(key,operator,_) in RULES.items():
        if field=='Quality score' and row.get('Evidence coverage',1)==0:
            if field in colors:colors[field]='background-color: #49351b; color: #fde68a'
            continue
        if field not in row or pd.isna(row[field]):continue
        limit=-cfg[key] if field=='Worst-decile mean return' else cfg[key]
        failed=row[field]<limit if operator=='>=' else row[field]>limit
        if failed:colors[field]='background-color: #54252d; color: #ffb4b4; font-weight: bold'
    for key in ('Status','Notes','Failed constraints'):
        if key in colors:
            colors[key]='color: #4ade80' if row.get('Qualifies') else 'background-color: #49351b; color: #fde68a'
    return colors
