"""Descriptive period statistics from completed daily ledgers, never cash outflows."""
from html import escape
import numpy as np
import pandas as pd


def reporting_frequency(record):
    frequency = record.get('inputs', {}).get('reporting_frequency')
    if frequency in ('Daily', 'Weekly', 'Monthly'):
        return frequency
    # Older saves predate the input field. Their table retains the period labels.
    payload = next(iter(record.get('strategies', {}).values()), {})
    table = payload.get('table') or []
    label = str(table[0].get('Date', '')) if table else ''
    return 'Weekly' if '/' in label else 'Monthly' if len(label) == 7 else 'Daily'


def period_metrics(daily, frequency):
    """Zero/invalid returns break streaks; earliest occurrence wins equal ties.

    Ranges use observed ledger dates (not unobserved period boundaries). Weekends
    are not observations and do not break daily trading-session streaks.
    """
    if frequency not in ('Daily', 'Weekly', 'Monthly'):
        raise ValueError('Unknown reporting frequency')
    frame = pd.DataFrame(daily).copy()
    result = dict(frequency=frequency, positive=dict(count=0, start=None, end=None),
                  negative=dict(count=0, start=None, end=None), max_profit=None, max_loss=None)
    if frame.empty or not {'Profit', 'Return %'} <= set(frame):
        return result
    if 'Date' in frame:
        frame = frame.set_index('Date')
    frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    frame = frame.sort_index()
    rows = []
    groups = [(d, frame.loc[[d]]) for d in frame.index] if frequency == 'Daily' else frame.groupby(frame.index.to_period('W-FRI' if frequency == 'Weekly' else 'M'))
    for _, group in groups:
        returns = pd.to_numeric(group['Return %'], errors='coerce').to_numpy(float)
        profits = pd.to_numeric(group['Profit'], errors='coerce').to_numpy(float)
        rows.append(dict(start=str(group.index[0].date()), end=str(group.index[-1].date()),
                         return_pct=float((np.prod(1 + returns / 100) - 1) * 100) if np.isfinite(returns).all() else None,
                         profit=float(profits.sum()) if np.isfinite(profits).all() else None))
    for key, direction in [('positive', 1), ('negative', -1)]:
        run = 0
        for row in rows:
            value = row['return_pct']
            if value is not None and value * direction > 1e-10:
                if run == 0:
                    start = row['start']
                run += 1
                if run > result[key]['count']:
                    result[key] = dict(count=run, start=start, end=row['end'])
            else:
                run = 0
    for key, direction in [('max_profit', 1), ('max_loss', -1)]:
        valid = [r for r in rows if r['profit'] is not None and r['profit'] * direction > 1e-10]
        if valid:
            result[key] = max(valid, key=lambda r: direction * r['profit'])
    return result


def metric_rows(stats):
    unit = {'Daily': 'days', 'Weekly': 'weeks', 'Monthly': 'months'}[stats['frequency']]
    def dates(item):
        if not item or not item.get('start'):
            return 'No qualifying period'
        return item['start'] if item['start'] == item['end'] else item['start'] + ' to ' + item['end']
    output = []
    for key, label, color in [('positive', 'Longest positive streak', '#22C55E'), ('negative', 'Longest negative streak', '#EF4444')]:
        item = stats[key]
        count_unit = unit[:-1] if item['count'] == 1 else unit
        output.append((label, f"{item['count']} {count_unit}", dates(item), color))
    for key, label, color in [('max_profit', 'Maximum period profit', '#22C55E'), ('max_loss', 'Maximum period loss', '#EF4444')]:
        item = stats[key]
        output.append((label, f"${item['profit']:+,.2f}" if item else 'None', dates(item), color))
    return output


def stats_html(stats, name=''):
    title = (name + ' - ' if name else '') + stats['frequency'] + ' performance statistics'
    tiles = []
    for label, value, dates, color in metric_rows(stats):
        tiles.append("<div style='min-width:0;padding:12px;background:#0F1B2D;border:1px solid #294252;border-radius:9px'>"
                     f"<small style='color:#9DB3C8'>{escape(label)}</small><div style='color:{color};font-size:18px;font-weight:700'>{escape(value)}</div>"
                     f"<small style='color:#E2E8F0;overflow-wrap:anywhere'>{escape(dates)}</small></div>")
    return ("<div style='grid-column:1/-1;width:100%;margin-top:14px'>"
            f"<b style='color:#E2E8F0'>{escape(title)}</b>"
            "<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin-top:8px'>"
            + ''.join(tiles) + "</div><small style='color:#9DB3C8'>Streaks use returns before withdrawals; profit/loss uses period investment profit. Zero-return periods break streaks. Earliest tie shown. Dates are observed trading dates; partial periods included.</small></div>")
