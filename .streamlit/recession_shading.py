"""Historical recession context, independent of indicator/model signals."""
import pandas as pd

# NBER peak/trough chronology; FRED USREC convention excludes the peak month.
# Covers all three indicator series (the earliest starts in 1959).
# Frozen reference checked 2026-09-15; not a real-time recession detector.
PERIODS = (
    ('1960-05-01', '1961-02-28'), ('1970-01-01', '1970-11-30'),
    ('1973-12-01', '1975-03-31'), ('1980-02-01', '1980-07-31'),
    ('1981-08-01', '1982-11-30'), ('1990-08-01', '1991-03-31'),
    ('2001-04-01', '2001-11-30'), ('2008-01-01', '2009-06-30'),
    ('2020-03-01', '2020-04-30'),
)
SOURCE = 'https://fred.stlouisfed.org/series/USREC'
NOTE = ('Red shaded bands mark historically dated U.S. recessions (NBER chronology, '
        'FRED USREC convention: month after the peak through the trough). '
        'These are retrospective dates, not indicator signals or forecasts. '
        'Bundled chronology checked September 15, 2026; new recession declarations require a chronology update.')


def shade_recessions(fig, start, end):
    """Clip bands to observed history without expanding the chart's date axis."""
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    visible = []
    for left, right in PERIODS:
        left, right = pd.Timestamp(left), pd.Timestamp(right)
        if right < start or left > end:
            continue
        label = f'{left:%b %Y} – {right:%b %Y}'
        fig.add_shape(type='rect', xref='x', yref='paper',
                      x0=max(start,left), x1=min(end,right), y0=0, y1=1,
                      fillcolor='rgba(248,113,113,0.20)', line_width=0,
                      layer='below', name=label)
        visible.append(label)
    return visible
