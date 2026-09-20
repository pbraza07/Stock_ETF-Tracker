"""Shared dark PDF theme; Excel includes full assumptions and monthly date tables."""
from io import BytesIO
import json
import pandas as pd

def excel_export(result):
    out=BytesIO()
    with pd.ExcelWriter(out,engine='openpyxl') as writer:
        for name,case in result['strategies'].items():
            short='RB' if name=='Rebalanced' else 'NR'
            case['table'].to_excel(writer,sheet_name=short+' Monthly',index=False)
            case['funding'].to_excel(writer,sheet_name=short+' Funding',index=False)
            pd.DataFrame(list(case['summary'].items()),columns=['Metric','Value']).to_excel(writer,sheet_name=short+' Summary',index=False)
            pd.DataFrame(list(case['sustainable'].items()),columns=['Metric','Value']).to_excel(writer,sheet_name=short+' Sustainable',index=False)
        for key in ('decomposition','agreement','stress_tests','planning_cases','sequence_tests'):
            result[key].to_excel(writer,sheet_name=key,index=False)
        pd.DataFrame(result['cma']['components']).to_excel(writer,sheet_name='Forward CMA',index=False)
        for key in ('audit','trust','settings','concentration'):
            pd.DataFrame([(k,json.dumps(v,default=str)) for k,v in result[key].items()],columns=['Field','Value']).to_excel(writer,sheet_name=key,index=False)
        pd.DataFrame({'Notes':[result['methodology'],*result['warnings']]}).to_excel(writer,sheet_name='Methodology',index=False)
    return out.getvalue()

def pdf_export(result):
    from reportlab.platypus import SimpleDocTemplate,Table,Spacer,PageBreak
    from marketscope_pdf_theme import document_kwargs,page_decorator,build_styles,paragraph,table_style
    from projection_dashboard_pdf import ProjectionChart
    out=BytesIO();title='MarketScope Forward Planning';doc=SimpleDocTemplate(out,**document_kwargs(title));styles=build_styles();story=[]
    p=lambda text,style='MSBody':paragraph(text,styles,style)
    def table(frame,columns=None):
        frame=frame[columns] if columns else frame
        if frame.empty:return
        rows=[[p(c,'MSCell') for c in frame.columns]]
        for _,row in frame.iterrows():
            rows.append([p(f'{v:,.3f}' if isinstance(v,float) else str(v),'MSCell') for v in row])
        t=Table(rows,colWidths=[doc.width/len(frame.columns)]*len(frame.columns),repeatRows=1,hAlign='LEFT');t.setStyle(table_style(font_size=7));story.append(t);story.append(Spacer(1,10))
    story+=[p(title,'Title'),p(result['methodology']),p('Research planning estimates; no guarantee of future return or spending sustainability.','MSWarning'),Spacer(1,10)]
    story.append(p('Holdings: '+', '.join(result['inputs']['holdings'])+f" | Starting assets ${result['inputs']['starting_investment']:,.0f} | Forecast {result['inputs']['forecast_start_year']}-{result['inputs']['forecast_start_year']+result['inputs']['future_years']-1}"))
    story+=[p('Projection Methodology & Reliability','Heading1'),p(f"Forward expected market return {result['cma']['geometric_return']:.1%}. Refreshed {result['cma']['refreshed_at']}. Missing components: {', '.join(result['cma']['missing_components'])}.")]
    for k,v in result['trust'].items():story.append(p(f'{k}: {v}','MSMuted'))
    for name,case in result['strategies'].items():
        story+=[PageBreak(),p(name,'Heading1'),p('Values are net of configured spending, costs, estimated taxes and PAL liabilities.')]
        formatted=[]
        for metric,value in case['summary'].items():
            if isinstance(value,(float,int)):
                if any(word in metric for word in ('Probability','Return','CAGR','Drawdown')):value=f'{value:.1%}'
                elif any(word in metric for word in ('Balance','Taxes','Fees','Spending','value')):value=f'${value:,.0f}'
                else:value=f'{value:,.1f}'
            formatted.append((metric,value))
        table(pd.DataFrame(formatted,columns=['Metric','Value']))
        story.append(p('Sustainable initial net spending: '+str(case['sustainable'])))
        frame=case['table'];traces=[]
        for q,color in zip([10,25,50,75,90],['#ef4444','#f59e0b','#2f80ed','#14b8a6','#a855f7']):
            traces.append({'x':frame.Date.tolist(),'y':frame[f'P{q} Ending Balance'].tolist(),'name':f'{name} P{q}','line':{'color':color}})
        story+=[PageBreak(),p('Portfolio equity by forecast date','Heading1'),ProjectionChart({'data':traces})]
        # Annual checkpoints keep 50-year PDF readable; Excel preserves every month and sale.
        annual=frame.iloc[11::12]
        story+=[PageBreak(),p('Annual checkpoints (full monthly ledger in Excel)','Heading1')]
        table(annual,['Date',*[f'P{p} Ending Balance' for p in [10,25,50,75,90]]])
        flows=frame.copy();flows['Year']=flows.Date.str[:4]
        flows=flows.groupby('Year',as_index=False)[['Median investment profit before costs','Gross withdrawal','Estimated withdrawal taxes','Net spendable income','Requested spending']].sum()
        story.append(p('Annual sums of monthly median cash flows (not pathwise annual medians)','Heading2'));table(flows)
    story+=[PageBreak(),p('Forward CMA component assumptions','Heading1')]
    table(pd.DataFrame(result['cma']['components']))
    for label,key in [('Model agreement','agreement'),('Planning cases','planning_cases'),('Sequence risk','sequence_tests'),('Stress tests (illustrative)','stress_tests')]:
        story+=[PageBreak(),p(label,'Heading1')];table(result[key])
    story+=[PageBreak(),p('Expected return decomposition','Heading1')]
    decom=result['decomposition'];first=decom[decom.Year==1]
    for _,row in first.iterrows():
        story.append(p(str(row['Ticker']),'Heading2'));table(pd.DataFrame([(k,str(v)) for k,v in row.items()],columns=['Component','Value']))
    story+=[PageBreak(),p('Assumptions and limitations','Heading1')]
    for k,v in result['settings'].items():story.append(p(f'{k}: {v}','MSMuted'))
    for warning in result['warnings']:story.append(p(warning,'MSBody'))
    decor=page_decorator(title);doc.build(story,onFirstPage=decor,onLaterPages=decor)
    return out.getvalue()
