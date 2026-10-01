"""Show every current stock with explicit pass/fail/unavailable evidence."""
import pandas as pd
from quality_opportunities import universe

RULES={
    'Quality score':('min_quality','>=','Quality'),
    'Target probability':('min_probability','>=','Target probability'),
    'Loss probability':('max_loss_probability','<=','Loss probability'),
    'Loss >20% probability':('max_severe_probability','<=','Severe loss'),
    'Worst-decile mean return':('max_tail_loss','>=','Worst-decile loss'),
}

def result_table(result,market):
    scored=result['table'];excluded=result['excluded'];cfg=result['settings']
    lookup={r['Ticker']:r for r in scored.to_dict('records')}
    reasons={r['Ticker']:r['Reason'] for r in excluded.to_dict('records')}
    rows=[]
    for _,stock in universe(market).iterrows():
        symbol=stock['Symbol'];row=dict(Ticker=symbol,Company=stock.get('Name',symbol),Sector=stock.get('Sector'),Price=stock.get('Price'))
        if symbol not in lookup:
            row.update(Status='NOT SCORED',Qualifies=False,Notes=reasons.get(symbol,'Evaluation unavailable'),
                **{'Criteria met':None,'Criteria assessed':0,'Failed constraints':'Not assessable — missing/invalid evidence','Why selected':'Not selected; no return estimates invented.'})
        else:
            row.update(lookup[symbol]);notes=[]
            for field,(key,operator,_) in RULES.items():
                actual=row[field];limit=-cfg[key] if field=='Worst-decile mean return' else cfg[key]
                failed=actual<limit if operator=='>=' else actual>limit
                if failed:
                    fmt=(lambda v:f'{v:.1f}') if field=='Quality score' else (lambda v:f'{v:.1%}')
                    notes.append(f'{field}: {fmt(actual)}; required {operator} {fmt(limit)}')
            row.update({'Criteria met':len(RULES)-len(notes),'Criteria assessed':len(RULES)})
            row.update(Status='MEETS ALL CRITERIA' if row['Qualifies'] else 'CRITERIA NOT MET',Notes='; '.join(notes) or 'All configured screening criteria met; probabilities remain uncalibrated.')
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
    if row.get('Status')=='NOT SCORED':
        for key in ('Status','Notes','Failed constraints'):
            if key in colors:colors[key]='background-color: #253244; color: #f8fafc'
        return colors
    for field,(key,operator,_) in RULES.items():
        if field not in row or pd.isna(row[field]):continue
        limit=-cfg[key] if field=='Worst-decile mean return' else cfg[key]
        failed=row[field]<limit if operator=='>=' else row[field]>limit
        if failed:colors[field]='background-color: #54252d; color: #ffb4b4; font-weight: bold'
    for key in ('Status','Notes','Failed constraints'):
        if key in colors:
            colors[key]='color: #4ade80' if row.get('Qualifies') else 'background-color: #49351b; color: #fde68a'
    return colors
