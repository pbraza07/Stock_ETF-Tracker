"""Lazy dashboard tab; uses the shared single-job scheduler, never auto-runs."""
import json
import streamlit as st
from quality_opportunities import MODES,screen,portfolio,universe
from projection_jobs import submit,poll,release

def _json(value):
    import numpy as np
    import pandas as pd
    if isinstance(value,pd.DataFrame):return json.loads(value.to_json(orient='records'))
    if isinstance(value,np.generic):return value.item()
    return str(value)

def render(market,years,monthly_loader,live_loader):
    st.header('Quality Growth & Return Opportunities')
    st.warning('Research estimates, not promised returns. This strategy is not yet calibrated. A high simulated probability is not verified real-world confidence.')
    st.caption('Every eligible stock in the current MarketScope universe is considered; ETFs are excluded. Quality and valuation are separate. No candidates are forced into the results.')
    with st.form('quality_opportunity_inputs'):
        c=st.columns(3)
        target=c[0].number_input('Target return (%)',1.,200.,25.)/100
        mode=c[1].selectbox('Return target definition',MODES)
        horizon=c[2].selectbox('Horizon (years; 12-month mode always uses 1)',[1,3,5,10])
        c=st.columns(3)
        minquality=c[0].slider('Minimum quality score',0,100,60)
        minp=c[1].slider('Minimum model target probability (%)',0,99,60)/100
        maxloss=c[2].slider('Maximum probability of any loss (%)',0,99,35)/100
        c=st.columns(3)
        severe=c[0].slider('Maximum probability of losing >20% (%)',0,99,15)/100
        tail=c[1].slider('Maximum worst-decile mean loss (%)',0,99,45)/100
        count=c[2].selectbox('Paths per stock / portfolio',[1000,2000,5000],index=1)
        c=st.columns(3)
        fee=c[0].number_input('Annual investment costs (%)',0.,10.,.1)/100
        trade=c[1].number_input('One-way trading cost (%)',0.,5.,.1)/100
        use_rate=c[2].checkbox('Use explicit Treasury assumption if desired',False)
        rate=st.number_input('Explicit Treasury yield (%) — ignored unless checked',0.,20.,4.)/100
        assumption_date=st.date_input('Explicit assumption date')
        st.caption('Costs apply to entry, final sale and RB trades. Taxes are excluded. Loss probabilities describe terminal capital losses, not interim drawdowns. Worst-decile return uses the selected total/annualized return basis. Every-year mode uses each anniversary year, not calendar years.')
        run=st.form_submit_button('Evaluate current stock universe',disabled=bool(st.session_state.get('qo_job')))
    if run:
        cfg=dict(target=target,mode=mode,years=horizon,count=count,min_quality=minquality,min_probability=minp,
            max_loss_probability=maxloss,max_severe_probability=severe,max_tail_loss=tail,annual_fee=fee,trade_cost=trade)
        planning={'cma_inputs':{'treasury_yield':rate,'as_of':assumption_date.isoformat()}} if use_rate else {}
        def task(progress):
            stocks=tuple(universe(market)['Symbol'])
            progress(0,3,'Loading existing fundamental and macro sources')
            context=live_loader(stocks)
            progress(1,3,'Loading actual monthly history')
            monthly=monthly_loader(stocks,tuple(years))
            result=screen(market,years,monthly,context,cfg,planning,progress)
            return dict(result=result,market=market.copy(),monthly=monthly,context=context,years=list(years))
        try:st.session_state.qo_job=submit(task);st.session_state.qo_job_kind='screen';st.rerun()
        except Exception as exc:st.error(str(exc))
    if st.session_state.get('qo_job'):
        @st.fragment(run_every=3)
        def status():
            token=st.session_state.qo_job;job=poll(token)
            if not job:
                st.session_state.pop('qo_job',None);st.session_state.qo_error='Worker expired or server restarted. Run the screen again.';st.rerun()
            if job['future'].done():
                try:
                    completed=job['future'].result()
                    if st.session_state.get('qo_job_kind')=='portfolio':st.session_state.qo_portfolio=completed
                    else:
                        st.session_state.qo_bundle=completed;st.session_state.pop('qo_portfolio',None)
                        st.session_state.pop('qo_holdings',None)
                except Exception as exc:st.session_state.qo_error=str(exc)
                finally:release(token);st.session_state.pop('qo_job',None)
                st.rerun()
            done,total,label=job['progress'];st.progress(min(.99,done/max(1,total)),text=f'{label}: {done}/{total}')
            st.caption('One background computation at a time on this server. Changing the form does not alter a running screen.')
        status();return
    if st.session_state.get('qo_error'):st.error(st.session_state.pop('qo_error'))
    bundle=st.session_state.get('qo_bundle')
    if not bundle:
        st.info('Choose your constraints and evaluate the universe. No rankings are calculated automatically.');return
    r=bundle['result']
    st.caption(f"Completed run: {r['generated_at']} • Data through: {r['data_through']} • Model {r['model_version']} • Stock universe: {r['universe_count']} • Scored: {len(r['table'])} • Excluded: {len(r['excluded'])}")
    st.caption('Results retain the last completed run settings. Submit again after changing inputs or refreshing data.')
    with st.expander('Completed run settings and data-source warnings'):
        st.json(r['settings']);st.write(r['context_failures'])
    if r['leaders'].empty:st.info('No stocks currently meet your return target and risk constraints. No substitute list has been fabricated.')
    else:
        st.subheader('Up to five qualified opportunities per sector')
        _table(r['leaders'])
    with st.expander('All evaluated stocks and failed constraints'):_table(r['table'])
    with st.expander('Excluded stocks and missing evidence'):st.dataframe(r['excluded'],width='stretch',hide_index=True)
    with st.expander('How these estimates were calculated'):
        st.write('Quality uses sector-relative ranks when at least five observed peers exist per metric; otherwise explicit absolute heuristic scales. Missing fields score zero. Financials omit debt/equity and cash-flow yield; this is not a full bank capital model. Growth durability, competitive advantages, credit ratings and revision histories are not fully verified.')
        st.write('Risk uses actual monthly history. Forward returns reuse the governed Forward Planning CMA, fundamentals, signal-horizon weights, fat tails, regime correlations and impairment assumptions—not extrapolated stock CAGR. Probabilities are conditional on these assumptions. Expected Investment Return is the first-year geometric drift before modeled impairments, gap events and costs; Planning Return is the net-path P25 CAGR. Neither is a sustainable withdrawal rate.')
        st.write('MC sampling intervals measure finite-simulation noise only. They do not include model error. Model disagreement is the spread of component mean CAGRs; historical mean return is removed from bootstrap sequences.')
        st.json(r['cma']);st.json(r['decomposition'])
    st.subheader('Joint portfolio evaluation')
    qualified=[] if r['table'].empty else r['table'].loc[r['table'].Qualifies,'Ticker'].tolist()
    selected=st.multiselect('Qualified portfolio holdings',qualified,key='qo_holdings')
    c=st.columns(2)
    maxweight=c[0].slider('Maximum position weight (%)',5,100,25)/100
    maxsector=c[1].slider('Maximum sector weight (%)',10,100,35)/100
    st.caption('Equal weight. Correlations are estimated jointly with stress-regime adjustments. Four stocks in different sectors can still share significant risks.')
    if st.button('Evaluate selected portfolio',disabled=not selected):
        try:
            def task(progress):
                progress(0,1,'Evaluating joint portfolio paths and correlations')
                return portfolio(bundle['market'],bundle['years'],bundle['monthly'],bundle['context'],selected,r,maxweight,maxsector)
            st.session_state.qo_job=submit(task);st.session_state.qo_job_kind='portfolio';st.rerun()
        except Exception as exc:st.session_state.pop('qo_portfolio',None);st.error(str(exc))
    p=st.session_state.get('qo_portfolio')
    if p:
        st.caption('Last completed portfolio: '+', '.join(p['holdings'])+'. Re-evaluate after changing selections or limits.')
        import pandas as pd
        st.dataframe(pd.DataFrame(p['metrics']).T,width='stretch')
        if not any(x['Meets constraints'] for x in p['metrics'].values()):st.warning('Neither evaluated portfolio strategy meets all of your constraints.')
        st.json({'Sector allocation':p['sector_allocation'],'Effective independent holdings':p['effective_independent_holdings'],'Common months':p['common_months']})
        st.caption(p['limitations'])
    st.subheader('Validation & forward paper record')
    st.warning(r['validation'])
    st.write('No high-probability certification is issued. Download this timestamped research snapshot to begin a forward paper record. Historical testing must use dated universe, fundamentals and macro vintages—not today’s selected winners. The accompanying walk-forward runner accepts those records; no empirical backtest history is bundled.')
    st.download_button('Download dated research audit (JSON)',json.dumps(dict(screen=r,portfolio=p),default=_json,indent=2),file_name='quality_opportunities_audit.json',mime='application/json')
    st.caption('Optional paper record contains selected tickers, model estimates and timestamps. Saving uses the configured GitHub repository when its existing token permits writes; repository readers can see the record. It does not place trades or certify subsequent performance.')
    if st.button('Save timestamped paper research record'):
        from opportunity_paper import save_record
        try:
            payload=json.loads(json.dumps(dict(screen=r,portfolio=p),default=_json))
            record_id,durable,message=save_record(payload)
            st.success('Paper record '+record_id+' • '+message) if durable else st.warning('Paper record '+record_id+' • '+message)
        except Exception as exc:st.error('Paper record could not be saved: '+str(exc))
    if not r['table'].empty:st.download_button('Download all stock results (CSV)',r['table'].to_csv(index=False),file_name='quality_opportunities.csv',mime='text/csv')

def _table(df):
    if df.empty:st.write('No results.');return
    columns=['Ticker','Company','Sector','Price','Quality score','Evidence coverage','Expected Investment Return','Planning return (P25 CAGR)',
        'Target probability','Loss probability','Loss >20% probability','Median return','P10 return','Worst-decile mean return',
        'Model disagreement (CAGR spread)','Fundamentals retrieved','Confidence','Qualifies','Failed constraints','Why selected']
    config={k:st.column_config.NumberColumn(k,format='percent') for k in columns if any(v in k for v in ['probability','return','Return','coverage','CAGR'])}
    config['Price']=st.column_config.NumberColumn('Price',format='dollar')
    st.dataframe(df[[k for k in columns if k in df]],column_config=config,width='stretch',hide_index=True)
