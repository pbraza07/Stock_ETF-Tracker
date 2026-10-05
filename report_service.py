"""Prepare only requested report formats. Persist by complete result content."""
from performance_store import get,put,key_for
import time

def report_key(result,kind):
    identity=result.get("_report_identity")
    return key_for("report-v51156-"+kind,(identity,result.get("export_chart"))) if identity else key_for("report-v51156-"+kind,result)

def export(result,kind,progress):
    key=report_key(result,kind)
    prior=get(key)
    if prior and prior[2]>time.time():return prior[0]
    progress(0,1,'Preparing '+kind.upper())
    from future_projection import build_pdf_export,build_excel_export,build_csv_export
    if result.get('planning_engine'):
        from planning_exports import pdf_export,excel_export
        data={'pdf':pdf_export,'xlsx':excel_export}[kind](result)
    else:data={'pdf':build_pdf_export,'xlsx':build_excel_export,'csv':build_csv_export}[kind](result)
    put(key,data,86400)
    return data

def render_projection_downloads(result):
    import streamlit as st
    from functools import partial
    from projection_jobs import submit,poll
    columns=st.columns(3)
    for col,kind,label,mime in zip(columns,['xlsx','csv','pdf'],['Excel','CSV','PDF'],[
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','text/csv','application/pdf']):
        if result.get('planning_engine') and kind=='csv':continue
        with col:
            key=report_key(result,kind)
            data=get(key)
            if data and data[2]>time.time():
                st.download_button('Download '+label,data[0],file_name='MarketScope_Future_Projection.'+kind,mime=mime,key=key,width='stretch')
            elif st.button('Prepare '+label,key=key,width='stretch'):
                try:
                    st.session_state['export_job_'+kind]=submit(partial(export,result,kind),priority=0);st.rerun()
                except Exception as exc:st.warning(str(exc))
            token=st.session_state.get('export_job_'+kind)
            if token:
                # Each format owns a poll fragment and does not block page rendering.
                _status(token,kind)

def _status(token,kind):
    import streamlit as st
    from projection_jobs import poll
    @st.fragment(run_every=3)
    def status():
        job=poll(token)
        if not job:
            st.session_state.pop('export_job_'+kind,None);st.warning('Report job expired. Prepare again.');return
        if job['future'].done():
            try:job['future'].result()
            except Exception as exc:st.error(str(exc))
            st.session_state.pop('export_job_'+kind,None);st.rerun()
        st.caption(job['progress'][2])
    status()
