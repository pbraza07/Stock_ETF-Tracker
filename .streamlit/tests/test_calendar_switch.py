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
    app.button[0].click().run()
    assert 'economic calendar' in app.subheader[0].value
    assert 'sslecal2.investing.com' in app.get('iframe')[0].proto.srcdoc
