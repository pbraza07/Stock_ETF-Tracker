"""Dashboard-shaped vector PDF from the completed projection and UI chart."""
from io import BytesIO
from xml.sax.saxutils import escape
import math
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate,Table,Paragraph,Spacer,PageBreak,Flowable,KeepTogether
from marketscope_pdf_theme import build_styles,document_kwargs,page_decorator,table_style,CARD,BORDER,TEXT,MUTED,ACCENT
from projection_presentation import _format_summary_value,_summary_metrics


def array(value):
    # Plotly 6 may encode numpy arrays in its figure dictionary.
    if isinstance(value,dict) and 'bdata' in value:
        import base64
        return np.frombuffer(base64.b64decode(value['bdata']),dtype=value['dtype']).tolist()
    return list(value) if value is not None else []


def chart_color(value):
    import re
    match = re.match(r"rgba?\(([^)]+)\)", str(value))
    if match:
        parts = [float(part) for part in match.group(1).split(',')]
        return colors.Color(*(part/255 for part in parts[:3]))
    try:
        return colors.toColor(value)
    except (ValueError, TypeError):
        return colors.HexColor('#94A3B8')


class ProjectionChart(Flowable):
    def __init__(self,figure):
        super().__init__();self.figure=figure;self.width=775;self.height=390
    def draw(self):
        c=self.canv; traces=self.figure.get('data',[])
        traces=[t for t in traces if t.get('visible',True) not in (False,'legendonly') and len(array(t.get('y')))]
        if not traces:
            c.setFillColor(TEXT);c.drawString(10,200,'No chart lines selected.');return
        labels=list(dict.fromkeys(str(x) for t in traces for x in array(t.get('x'))))
        x0,y0,w,h=65,45,635,240
        def limits(axis):
            vals=[float(v) for t in traces if t.get('yaxis','y')==axis for v in array(t.get('y')) if v is not None and np.isfinite(float(v))]
            lo=min([0]+vals);hi=max([0]+vals)
            return lo,hi if hi!=lo else lo+1
        bounds={axis:limits(axis) for axis in ['y','y2']}
        def point(x,v,axis):
            lo,hi=bounds[axis]
            return x0+w*labels.index(str(x))/max(1,len(labels)-1),y0+h*(float(v)-lo)/(hi-lo)
        c.setFont('Helvetica',7);c.setStrokeColor(BORDER);c.setFillColor(MUTED)
        for j in range(6):
            y=y0+h*j/5;c.line(x0,y,x0+w,y)
            lo,hi=bounds['y'];v=lo+(hi-lo)*j/5
            c.drawRightString(x0-8,y,f'{v:,.1f}' if self.figure.get('view')=='Annual Return %' else f'${v:,.0f}')
            if any(t.get('yaxis')=='y2' for t in traces):
                lo,hi=bounds['y2'];c.drawString(x0+w+5,y,f'${lo+(hi-lo)*j/5:,.0f}')
        for j in sorted(set(round(i*(len(labels)-1)/min(7,max(1,len(labels)-1))) for i in range(min(8,len(labels))))):
            c.drawCentredString(x0+w*j/max(1,len(labels)-1),y0-15,labels[j])
        c.drawCentredString(x0+w/2,9,'Forecast period')
        previous=None
        for t in traces:
            line=t.get('line',{});color=line.get('color','#94A3B8')
            color=chart_color(color)
            axis=t.get('yaxis','y');points=[point(x,v,axis) for x,v in zip(array(t.get('x')),array(t.get('y'))) if v is not None and math.isfinite(float(v))]
            if t.get('fill')=='tonexty' and previous and points:
                c.saveState();c.setFillColor(chart_color(t.get('fillcolor',color)));c.setFillAlpha(.15)
                path=c.beginPath();path.moveTo(*points[0])
                for xy in points[1:]+list(reversed(previous)):path.lineTo(*xy)
                path.close();c.drawPath(path,fill=1,stroke=0);c.restoreState()
            previous=points
            c.setStrokeColor(color);c.setLineWidth(max(.7,float(line.get('width',2))*.65))
            c.setDash([5,3] if line.get('dash')=='dash' else [1,3] if line.get('dash')=='dot' else [])
            if points and line.get('width',1) != 0:
                path=c.beginPath();path.moveTo(*points[0])
                for xy in points[1:]:path.lineTo(*xy)
                c.drawPath(path)
                if 'markers' in t.get('mode',''):
                    c.setFillColor(color)
                    for px,py in points:c.circle(px,py,1.6,fill=1,stroke=0)
        c.setDash([])
        legend=[t for t in traces if t.get('showlegend',True)]
        for i,t in enumerate(legend):
            x=12+(i%4)*190;y=365-(i//4)*14
            line=t.get('line',{});c.setStrokeColor(chart_color(line.get('color',t.get('fillcolor','#94A3B8'))))
            c.setDash([5,3] if line.get('dash')=='dash' else [1,3] if line.get('dash')=='dot' else [])
            c.line(x,y+2,x+18,y+2);c.setDash([])
            c.setFillColor(TEXT);c.setFont('Helvetica',6.5);c.drawString(x+22,y,str(t.get('name',''))[:46])
        for shape in self.figure.get('layout',{}).get('shapes',[]):
            if shape.get('y0')==shape.get('y1') and isinstance(shape.get('y0'),(int,float)):
                v=shape['y0'];lo,hi=bounds['y']
                if lo<=v<=hi:
                    y=y0+h*(v-lo)/(hi-lo);c.setStrokeColor(MUTED);c.setDash([1,3]);c.line(x0,y,x0+w,y);c.setDash([])
                    c.setFillColor(TEXT);c.drawRightString(x0+w,y+5,'Starting investment')


def default_chart(result):
    traces=[];palette={10:'#EF4444',25:'#F59E0B',50:'#2F80ED',75:'#14B8A6',90:'#A855F7'}
    for name,payload in result.get('strategies',{}).items():
        frame=payload.get('chart',payload.get('table',pd.DataFrame()))
        for q,color in palette.items():
            col=f'P{q} Ending Balance'
            if col in frame:
                traces.append({'x':frame.Period.astype(str).tolist(),'y':frame[col].tolist(),'name':f'{name} P{q}','line':{'color':color,'dash':'dash' if name=='Non-Rebalanced' else 'solid'}})
    return {'data':traces,'view':'Portfolio Balance'}


def build_dashboard_pdf(result,title):
    out=BytesIO();doc=SimpleDocTemplate(out,**document_kwargs(title));styles=build_styles();story=[];width=doc.width
    def p(value,style='MSBody'):return Paragraph(escape(str(value if value is not None else 'N/A')),styles[style])
    def cards(items,cols=3,total_width=None):
        rows=[]
        for start in range(0,len(items),cols):
            row=[]
            for label,value in items[start:start+cols]:
                row.append([p(label,'MSCellMuted'),Spacer(1,5),p(value)])
            row+=['']*(cols-len(row));rows.append(row)
        t=Table(rows,colWidths=[(total_width or width)/cols]*cols,hAlign='LEFT')
        t.setStyle(table_style(header=False,font_size=8));t.setStyle([('BACKGROUND',(0,0),(-1,-1),CARD),('BOX',(0,0),(-1,-1),.5,BORDER),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)])
        return t
    state=result.get('current_market_state') or {};meta=result.get('metadata') or {};inputs=result.get('inputs') or {};probs=state.get('regime_probabilities') or {}
    story+=[p('Current market environment','Heading1'),p(f"Live adaptive status: {meta.get('live_data_status','Unknown')} - regime score {state.get('regime_score','N/A')}/100 - retrieved {state.get('retrieved_at') or 'Not available'}",'MSMuted'),Spacer(1,10)]
    items=[(f'{k} probability',f"{float(probs[k]):.2f}%" if k in probs else 'N/A') for k in ['Bear','Normal','Bull']]
    items += [(label,state.get(key,'Unknown')) for label,key in [('Market trend','market_trend'),('Volatility','volatility_environment'),('Valuation','valuation_environment'),('Earnings trend','earnings_trend'),('Interest-rate environment','interest_rate_environment'),('Portfolio correlation risk','portfolio_correlation_risk')]]
    items += [('Projection confidence',meta.get('projection_confidence','Unknown')),('Calibration score',str(meta.get('projection_calibration_score','N/A'))+'/100'),('Breadth above 200-day MA',(f"{float(state['breadth_above_200_day']):.1f}%" if state.get('breadth_above_200_day') is not None else 'N/A'))]
    story+=[cards(items,6),Spacer(1,12),p('Portfolio-specific risk','Heading2')]
    for k,v in (state.get('portfolio_risk') or {}).items():story.append(p(f"{k.replace('_',' ')}: {v}",'MSMuted'))
    story+=[Spacer(1,10),p('Live data status and freshness','Heading2')]
    for k,v in (state.get('data_freshness') or {}).items():story.append(p(f"{k}: {v.get('status')} - {v.get('updated')}",'MSMuted'))
    strategies=result.get('strategies') or {};include=bool(inputs.get('include_no_withdrawal_comparison'))
    metrics={name:[(k,_format_summary_value(k,payload.get('summary',{}).get(k))) for k in _summary_metrics(payload.get('summary',{}),include)] for name,payload in strategies.items()}
    names=list(metrics)
    for offset in range(0,max((len(v) for v in metrics.values()),default=0),15):
        story+=[PageBreak(),p('Projection results','Heading1')]
        blocks=[]
        for name in names:
            block=[p(name,'Heading2'),Spacer(1,5),cards(metrics[name][offset:offset+15],3,(width-12)/max(1,len(names))) if metrics[name][offset:offset+15] else Spacer(1,1)]
            blocks.append(block)
        t=Table([blocks],colWidths=[width/max(1,len(names))]*len(names));t.setStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0)])
        story.append(t)
    figure=result.get('export_chart') if 'export_chart' in result else default_chart(result)
    story+=[PageBreak(),p('Performance projection','Heading1')]
    if figure:story+=[p(figure.get('view','Selected graph'),'Heading2'),ProjectionChart(figure)]
    else:story.append(p('No graph selected in the application.'))
    for name,payload in strategies.items():
        frame=payload.get('table',pd.DataFrame())
        if frame.empty:continue
        period='Period' if 'Period' in frame else frame.columns[0]
        story += [PageBreak(),p(f'Detailed projection tables - {name}','Heading1')]
        columns=[c for c in frame if c!=period]
        for start in range(0,len(columns),6):
            cols=[period]+columns[start:start+6]
            for row_start in range(0,len(frame),18):
                heading=p(f'{name} - {frame.iloc[row_start][period]} to {frame.iloc[min(row_start+17,len(frame)-1)][period]}','Heading2')
                data=[[p(c,'MSCell') for c in cols]]
                for _,row in frame.iloc[row_start:row_start+18].iterrows():
                    values=[]
                    for col in cols:
                        v=row[col]
                        if col in (period,'Year','Month'):
                            values.append(p(str(int(v)) if isinstance(v,(int,float,np.number)) and np.isfinite(v) else v,'MSCell'))
                        elif isinstance(v,(int,float,np.number)):
                            text=f'{v:,.2f}%' if '%' in col or 'Probability' in col else f'${v:,.2f}'
                            color='#4ADE80' if v>0 else '#FB7185' if v<0 else '#F2F7FB'
                            values.append(Paragraph(f'<font color="{color}">{text}</font>',styles['MSCell']))
                        else:values.append(p(v,'MSCell'))
                    data.append(values)
                t=Table(data,colWidths=[width/len(cols)]*len(cols),repeatRows=1);t.setStyle(table_style(font_size=7));story.append(KeepTogether([heading,t,Spacer(1,12)]))
    story+=[PageBreak(),p('Inputs, assumptions and limitations','Heading1')]
    for k,v in inputs.items():story.append(p(f'{k}: {v}','MSMuted'))
    for field in ['warnings','limitations']:
        for value in result.get(field) or []:story.append(p(value,'MSMuted'))
    assumptions=result.get('model_assumptions',pd.DataFrame())
    if isinstance(assumptions,pd.DataFrame):
        for row in assumptions.to_dict('records'):story.append(p(' | '.join(f'{k}: {v}' for k,v in row.items()),'MSMuted'))
    story.append(p(f"Data as of: {meta.get('data_as_of')} - Model as of: {meta.get('model_as_of')} - Seed: {meta.get('random_seed')}",'MSMuted'))
    decorator=page_decorator(title,'Populated dashboard, selected graph and complete period tables')
    doc.build(story,onFirstPage=decorator,onLaterPages=decorator)
    return out.getvalue()
