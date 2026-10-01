from html import unescape
from urllib.parse import parse_qs, urlsplit
from economic_calendar import calendar_url, earnings_calendar_url, earnings_embed


def test_requested_parameters_match_economic():
    economic = parse_qs(urlsplit(calendar_url()).query)
    earnings = parse_qs(urlsplit(earnings_calendar_url()).query)
    assert earnings.pop('importance') == ['3']
    economic.pop('importance')
    assert earnings == economic
    assert urlsplit(earnings_calendar_url()).hostname == 'www.investing.com'
    assert urlsplit(earnings_calendar_url()).path == '/earnings-calendar/'


def test_matching_frame_size_and_dark_filter():
    html = earnings_embed()
    assert 'height:520px' in html and 'width:100%' in html
    assert 'filter:invert(.94) hue-rotate(180deg)' in html
    assert earnings_calendar_url() in unescape(html)
    assert 'width:125%;height:650px' in html
    assert 'transform:scale(.8);transform-origin:top left' in html
    assert '&amp;' in html
