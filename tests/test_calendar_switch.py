from streamlit.testing.v1 import AppTest

def test_calendar_switch_round_trip():
    app=AppTest.from_string('from economic_calendar import render_economic_calendar\nrender_economic_calendar()').run()
    assert not app.exception
    assert 'economic calendar' in app.subheader[0].value
    assert 'sslecal2.investing.com' in app.get('iframe')[0].proto.srcdoc
    app.button[0].click().run()
    assert not app.exception
    assert app.button[0].label=='← Back to Economic Calendar'
    assert 'https://www.investing.com/earnings-calendar/' in app.get('iframe')[0].proto.srcdoc
    assert 'importance=2%2C3' in app.get('iframe')[0].proto.srcdoc
    assert 'height:520px' in app.get('iframe')[0].proto.srcdoc
    assert 'not applied automatically' in app.caption[0].value
    assert len(app.slider)==2
    app.slider[0].set_value(100).run()
    assert 'top:-100px' in app.get('iframe')[0].proto.srcdoc
    app.button[0].click().run()
    assert 'economic calendar' in app.subheader[0].value
    assert 'sslecal2.investing.com' in app.get('iframe')[0].proto.srcdoc


def test_back_destination_is_idempotent_and_repeated_navigation():
    app=AppTest.from_string('''
import streamlit as st
from economic_calendar import render_economic_calendar, _switch_calendar
if 'initialized' not in st.session_state:
    st.session_state['dashboard_calendar_kind']='earnings'
    _switch_calendar('economic')
    _switch_calendar('economic')
    st.session_state['initialized']=True
with st.tabs(['Market Navigator','Other'])[0]:
    render_economic_calendar()
''').run()
    assert not app.exception
    assert app.session_state['dashboard_calendar_kind']=='economic'
    for _ in range(3):
        app.button(key='dashboard_calendar_to_earnings').click().run()
        assert not app.exception
        assert 'earnings-calendar/' in app.get('iframe')[0].proto.srcdoc
        app.button(key='dashboard_calendar_to_economic').click().run()
        assert not app.exception
        assert len(app.get('iframe'))==1
        html=app.get('iframe')[0].proto.srcdoc
        assert 'sslecal2.investing.com' in html and 'earnings-calendar/' not in html
        assert app.session_state['dashboard_calendar_kind']=='economic'
