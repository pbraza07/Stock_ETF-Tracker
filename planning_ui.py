"""Native responsive planning controls and transparent results."""
import json
import pandas as pd
import streamlit as st
from planning_assumptions import DEFAULTS

PERCENTILE_HELP='P10: weak outcome threshold; P25: below median; P50: median; P75: strong; P90: very strong. About 10% of modeled outcomes exceed P90. These are model percentiles, not guaranteed probabilities.'

def controls():
    mode=st.radio('Projection engine',['Forward Planning','Existing projection profiles'],horizontal=True,key='planning_mode',
        help='Forward Planning separates historical risk from forward returns. Existing profiles preserve Historical-Calibrated and earlier runs.')
    if mode!='Forward Planning':return None,[]
    cfg={};errors=[]
    with st.expander('Financial planning settings',expanded=True):
        st.caption('Use Future Years above for 10, 20, 25, 30 or up to 50 years. A lifetime-style horizon is a finite planning choice; mortality is not modeled.')
        st.caption('Expected Investment Return is the central economic estimate. Planning Return is a lower-percentile scenario; sustainable spending is solved using full paths, not a flat return.')
        a,b,c=st.columns(3)
        with a:
            cfg['inflation_adjusted']=st.selectbox('Spending basis',['Inflation-Adjusted Withdrawal','Nominal Dollar Withdrawal'])=='Inflation-Adjusted Withdrawal'
            cfg['inflation']=st.number_input('Planning inflation (%)',0.,15.,2.5,.1)/100
            cfg['desired_survival']=st.selectbox('Spending success target (%)',[50,70,80,90,95],index=3)/100
            cfg['planning_percentile']=st.number_input('Planning return percentile',1,49,25,help=PERCENTILE_HELP)
            cfg['solve_withdrawal']=st.checkbox('Calculate sustainable initial annual spending',value=True,
                help='Maximum initial net spending supported by a deterministic subset of paths at the chosen success target and forecast horizon. Not a guarantee.')
        with b:
            cfg['tax_enabled']=st.checkbox('Estimate taxes')
            cfg['account']=st.selectbox('Account type',['Taxable','Tax-deferred','Roth','Blended'])
            cfg['federal_rate']=st.number_input('Estimated federal ordinary rate (%)',0.,60.,22.)/100
            cfg['state_rate']=st.number_input('Estimated state rate (%)',0.,30.,0.)/100
            cfg['capital_gains_rate']=st.number_input('Long-term capital-gains rate (%)',0.,50.,15.)/100
            cfg['basis_fraction']=st.number_input('Current average cost basis (% of value)',0.,99.9,90.)/100
            if cfg['account']=='Blended':
                cfg['taxable_weight']=st.number_input('Taxable account share (%)',0.,100.,50.)/100
                cfg['deferred_weight']=st.number_input('Tax-deferred share (%)',0.,100.,50.)/100
                st.caption('Remaining share is Roth; simplified uniform account mix across holdings.')
        with c:
            cfg['expense_ratio']=st.number_input('Fund expense ratio (%)',0.,5.,.10,.05)/100
            cfg['advisory_fee']=st.number_input('Additional advisory fee (%)',0.,5.,0.,.05)/100
            cfg['trading_friction']=st.number_input('Trading friction (%)',0.,2.,.05,.01)/100
            cfg['bid_ask']=st.number_input('Bid/ask cost (%)',0.,2.,.05,.01)/100
            cfg['tax_drag']=st.number_input('Additional annual tax drag (%)',0.,5.,0.,.05,help='Optional drag for distributions not captured by sale taxes; avoid double counting.')/100
            cfg['sale_method']=st.selectbox('Securities funding withdrawals',['Proportional','Overweight first','Strongest first','Weakest first','Tax-aware','Custom order'])
            if cfg['sale_method']=='Custom order':cfg['custom_order']=[s.strip().upper() for s in st.text_input('Ticker sale order (comma separated)').split(',') if s.strip()]
        cfg['goal']=st.selectbox('Planning goal',['Fully fund spending','Maintain principal','Never below floor','Reach target'])
        cfg['goal_amount']=st.number_input('Goal value / minimum floor ($)',0.,1e9,250000.,10000.)
        cfg['goal_real']=st.checkbox('Goal expressed in today’s purchasing power',value=True)
        with st.expander('PAL / securities-backed borrowing'):
            cfg['pal_balance']=st.number_input('Existing PAL liability ($)',0.,1e9,0.,1000.)
            cfg['pal_rate']=st.number_input('Fixed PAL annual interest (%)',0.,30.,8.)/100
            cfg['pal_variable']=st.checkbox('Variable PAL rate')
            cfg['pal_spread']=st.number_input('PAL spread over scenario short rate (%)',0.,20.,3.)/100
            cfg['pal_interest']=st.selectbox('Interest payment method',['Portfolio','Capitalize'])
            cfg['pal_ltv']=st.number_input('Repayment target LTV (%)',1.,90.,50.)/100
            cfg['pal_maintenance']=st.number_input('Maintenance trigger LTV (%)',2.,99.,65.)/100
            st.caption('Monthly maintenance checks. Borrowed proceeds remain outside portfolio wealth; lender haircuts and immediate calls may be stricter.')
        with st.expander('Forward assumptions and advanced configuration'):
            st.caption('FRED Treasury data supply the rates component. Missing valuation/institutional components are disclosed and excluded. No fixed 7% fallback. Override JSON rates are decimal fractions.')
            raw=st.text_area('Dated market assumptions / model overrides (JSON)',value='{}',key='planning_overrides',
                help='Example: {"cma_inputs":{"treasury_yield":0.04,"as_of":"2026-09-20"},"equity_risk_premium":0.035}. Institutional entries require source, as_of and nominal geometric return.')
            try:
                override=json.loads(raw)
                if not isinstance(override,dict):raise ValueError('Expected a JSON object.')
                cfg.update(override)
            except (ValueError,TypeError) as exc:errors.append('Planning overrides: '+str(exc))
            st.json({'cma_weights':DEFAULTS['cma_weights'],'signal_weights':DEFAULTS['signal_weights'],
                     'return_bounds':DEFAULTS['return_bounds'],'block_months':DEFAULTS['block_months']})
    return cfg,errors

def render(result):
    import plotly.graph_objects as go
    st.subheader('Forward financial planning')
    advanced=st.radio('Detail level',['Basic View','Advanced View'],horizontal=True)=='Advanced View'
    st.caption(PERCENTILE_HELP)
    visible=st.multiselect('Visible planning percentiles',[10,25,50,75,90],default=[10,25,50,75,90],help=PERCENTILE_HELP)
    show_reference=st.checkbox('Show no-withdrawal reference',value=True)
    st.info('Research planning estimates. Calibration is unvalidated until verified point-in-time tests are available. A funded P50 outcome does not establish retirement safety.')
    cma=result['cma'];st.metric('Forward U.S. Equity Return Assumption',f"{cma['geometric_return']:.1%}")
    st.caption(f"Assumption sensitivity range {cma['assumption_range'][0]:.1%} to {cma['assumption_range'][1]:.1%}; confidence {cma['confidence']}. {cma['range_definition']}.")
    for name,case in result['strategies'].items():
        st.subheader(name);summary=case['summary'];cols=st.columns(2)
        cols[0].metric('Expected Investment Return',f"{summary['Expected Investment Return']:.1%}",help='First-year weighted economic geometric-return estimate before event losses and costs; distinct from mean arithmetic return and simulated CAGR.')
        cols[1].metric('Planning Return',f"{summary['Planning Return']:.1%}",help=result['audit']['planning_return_definition'])
        metrics=['Portfolio Survival Probability','Probability Principal Is Preserved','Probability Spending Is Fully Funded','Probability of Depletion','Median Ending Balance','P10 Ending Balance']
        for i in range(0,len(metrics),3):
            columns=st.columns(3)
            for col,label in zip(columns,metrics[i:i+3]):
                value=summary[label];col.metric(label,f'{value:.0%}' if 'Probability' in label else f'${value:,.0f}')
        sustainable=case['sustainable'];st.write('**Sustainable initial annual net spending:**',f"${sustainable['initial_annual_withdrawal']:,.0f}" if 'initial_annual_withdrawal' in sustainable else 'Not requested')
        st.caption(str(sustainable))
        fig=go.Figure();frame=case['table']
        for p,color in zip([10,25,50,75,90],['#ef4444','#f59e0b','#2f80ed','#14b8a6','#a855f7']):
            if p in visible:fig.add_scatter(x=frame.Date,y=frame[f'P{p} Ending Balance'],name=f'P{p}',line={'color':color})
        if show_reference:
            ref=result['references'][name]
            fig.add_scatter(x=ref.Date,y=ref['P50 Ending Balance'],name='P50 no-withdrawal reference',line={'color':'#94a3b8','dash':'dot'})
        fig.update_layout(template='plotly_dark',paper_bgcolor='#07121c',plot_bgcolor='#07121c',yaxis_title='Net portfolio equity ($)',xaxis_title='Forecast date',height=390)
        st.plotly_chart(fig,width='stretch',key='planning_chart_'+name)
        st.caption('Balances are after configured fees, estimated taxes, spending and PAL liabilities. Principal-preservation probability uses inflation-adjusted initial equity.')
        st.dataframe(frame,width='stretch',hide_index=True)
        if advanced:
            st.json(summary)
            with st.expander('Which securities fund spending?'):
                st.caption('Mean and median gross sales across paths; excludes rebalancing, fees, interest and mandatory PAL repayments. Custom-order missing holdings are appended.')
                st.dataframe(case['funding'],width='stretch',hide_index=True)
    for label,key in [('Planning cases','planning_cases'),('Sequence risk','sequence_tests'),('Stress tests — illustrative','stress_tests')]:
        with st.expander(label,expanded=advanced):st.dataframe(result[key],width='stretch',hide_index=True)
    with st.expander('Model Trust & Data Quality',expanded=True):
        st.json(result['trust']);st.dataframe(result['agreement'],width='stretch',hide_index=True)
        st.json(result['current_market_state'].get('data_freshness',{}))
    with st.expander('How MarketScope Calculated This',expanded=advanced):
        st.write(result['methodology']);st.dataframe(pd.DataFrame(cma['components']),width='stretch',hide_index=True)
        st.dataframe(result['decomposition'],width='stretch',hide_index=True)
        st.json(result['concentration']);st.json(result['audit'])
        for warning in result['warnings']:st.caption(warning)
    from planning_exports import excel_export,pdf_export
    with st.expander('Export planning report'):
        if st.button('Prepare planning PDF and Excel'):
            st.session_state['planning_export_bytes']=(id(result),pdf_export(result),excel_export(result))
        cached=st.session_state.get('planning_export_bytes')
        if cached and cached[0]==id(result):
            st.download_button('Download planning PDF',cached[1],'MarketScope_Forward_Planning.pdf','application/pdf')
            st.download_button('Download planning Excel',cached[2],'MarketScope_Forward_Planning.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
