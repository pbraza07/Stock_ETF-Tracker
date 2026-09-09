"""Daily-ledger YTD simulation; presentation aggregation never changes cash flows."""
import numpy as np
import pandas as pd
from pathlib import Path


def history_prices(histories, symbols):
    """Align trading dates before joining (provider timezones may differ)."""
    series = {}
    missing = []
    for symbol in symbols:
        frame = histories.get(symbol)
        if frame is None or frame.empty or "Close" not in frame:
            missing.append(symbol)
            continue
        close = frame["Close"].copy()
        close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
        close = close.loc[~close.index.duplicated(keep="last")]
        series[symbol] = close
    if missing:
        raise ValueError("Daily prices unavailable for " + ", ".join(missing) + ". Refresh and retry; no holdings were omitted.")
    return pd.concat(series, axis=1)


def simulate_ytd(prices, principal, frequency="Monthly", withdrawal=0.0,
                 withdrawal_frequency="Monthly", rebalanced=False, as_of=None):
    as_of = pd.Timestamp(as_of or pd.Timestamp.today()).normalize().tz_localize(None)
    if frequency not in {"Daily", "Weekly", "Monthly"} or withdrawal_frequency not in {"Daily", "Weekly", "Monthly"}:
        raise ValueError("Choose Daily, Weekly, or Monthly.")
    if not np.isfinite(principal) or principal <= 0 or not np.isfinite(withdrawal) or withdrawal < 0:
        raise ValueError("Investment must be positive and withdrawal nonnegative.")
    p = prices.copy().sort_index()
    p.index = pd.to_datetime(p.index).tz_localize(None).normalize()
    p = p.loc[~p.index.duplicated(keep="last")]
    p = p.apply(pd.to_numeric, errors="coerce")
    p = p.where(np.isfinite(p) & (p > 0)).dropna()
    p = p.loc[p.index <= as_of]
    start = pd.Timestamp(as_of.year, 1, 1)
    before = p.loc[p.index < start]
    current = p.loc[p.index >= start]
    if current.empty or p.shape[1] == 0:
        raise ValueError("No shared current-year daily prices were returned. Refresh the selected holdings and retry.")
    full_ytd = not before.empty and (start - before.index[-1]).days <= 7
    observations = pd.concat([before.tail(1), current]) if full_ytd else current
    if len(observations) < 2:
        raise ValueError("At least two shared daily closing prices are needed for the selected holdings.")
    returns = observations.pct_change(fill_method=None).iloc[1:]
    balances = np.full(p.shape[1], float(principal) / p.shape[1])
    rows = []
    for i, (date, r) in enumerate(returns.iterrows()):
        begin = balances.sum()
        balances *= 1 + r.to_numpy(float)
        profit = balances.sum() - begin
        next_date = returns.index[i + 1] if i + 1 < len(returns) else None
        period = "W-FRI" if withdrawal_frequency == "Weekly" else "M"
        due = withdrawal_frequency == "Daily"
        if not due:
            end = date.to_period(period).end_time.normalize()
            due = (next_date is not None and next_date.to_period(period) != date.to_period(period)) or (next_date is None and end <= as_of)
        requested = withdrawal if due else 0.0
        actual = min(requested, balances.sum())
        if balances.sum() > 0:
            balances *= (balances.sum() - actual) / balances.sum()
        if rebalanced and due:
            balances[:] = balances.sum() / len(balances)
        rows.append({"Date": date, "Beginning Balance": begin, "Profit": profit,
                     "Return %": profit / begin * 100 if begin else 0.0,
                     "Requested Withdrawal": requested, "Actual Withdrawal": actual,
                     "Shortfall": requested - actual, "Ending Balance": balances.sum()})
    daily = pd.DataFrame(rows).set_index("Date")
    daily.attrs.update(start_date=str(observations.index[0].date()), full_ytd=full_ytd)
    if frequency == "Daily":
        result = daily.copy()
    else:
        groups = daily.groupby(daily.index.to_period("W-FRI" if frequency == "Weekly" else "M"))
        result = groups.agg({"Beginning Balance": "first", "Profit": "sum", "Requested Withdrawal": "sum",
                             "Actual Withdrawal": "sum", "Shortfall": "sum", "Ending Balance": "last"})
        result["Return %"] = groups["Return %"].apply(lambda x: ((1 + x / 100).prod() - 1) * 100)
    result.index = result.index.astype(str)
    result["Cumulative Withdrawals"] = result["Actual Withdrawal"].cumsum()
    result["Net Profit incl. Withdrawals"] = result["Ending Balance"] + result["Cumulative Withdrawals"] - principal
    return result, daily


def snapshot(daily):
    months = daily.groupby(daily.index.to_period("M"))["Return %"].apply(lambda x: (1 + x / 100).prod() - 1)
    return {"Beginning Balance": float(daily.iloc[0]["Beginning Balance"]),
            "Current Balance": float(daily.iloc[-1]["Ending Balance"]),
            "Positive Days": int((daily["Return %"] > 0).sum()), "Days": len(daily),
            "Positive Months": int((months > 0).sum()), "Months": len(months),
            "Withdrawn": float(daily["Actual Withdrawal"].sum())}


def show_snapshot(values):
    import streamlit as st
    columns = st.columns(4)
    columns[0].metric("Beginning balance", f"${values['Beginning Balance']:,.2f}")
    columns[1].metric("Current balance after withdrawals", f"${values['Current Balance']:,.2f}")
    columns[2].metric("Positive days", f"{values['Positive Days']}/{values['Days']}")
    columns[3].metric("Positive months", f"{values['Positive Months']}/{values['Months']}")


def make_saved_record(outputs, inputs, name):
    from portfolio_simulations import simulation_id
    from persistence import now_et
    return {"id": simulation_id(), "name": name or "YTD Portfolio", "simulation_type": "ytd_daily",
            "created_at_et": now_et().isoformat(), "inputs": inputs,
            "strategies": {key: {"snapshot": snapshot(daily), "start_date": daily.attrs['start_date'],
                          "full_ytd": daily.attrs['full_ytd'], "through": str(daily.index[-1].date()),
                          "table": table.reset_index().to_dict('records'),
                          "daily": daily.rename_axis('Date').reset_index().assign(Date=lambda d: d.Date.astype(str)).to_dict('records')}
                           for key, (table, daily) in outputs.items()}}


def render_saved_ytd(record):
    import streamlit as st
    with st.expander(record.get('name', 'Saved YTD simulation')):
        st.caption(str(record['inputs']))
        for name, payload in record['strategies'].items():
            st.markdown(f"**{name}**")
            st.caption(f"{payload['start_date']} through {payload['through']}; positive months include the current partial month.")
            show_snapshot(payload['snapshot'])
            table = pd.DataFrame(payload['table'])
            st.dataframe(table, width='stretch')
            st.download_button('Download saved ' + name, table.to_csv(index=False).encode(),
                               f"{record['id']}_{name}.csv", key=record['id'] + name)


def render_ytd(market, on_saved=None):
    import streamlit as st
    from providers.yahoo import YahooFinanceProvider
    st.subheader("Year-to-date portfolio simulation")
    st.caption("Actual adjusted daily closes; equal starting weights. Daily withdrawals occur on trading days. Weekly/monthly withdrawals occur at completed period ends. Incomplete periods have no withdrawal. Rebalanced strategy resets equal weights at the chosen cash-flow cadence, even with withdrawals disabled.")
    symbols = st.multiselect("YTD holdings", market.Symbol.drop_duplicates().tolist(), key="ytd_holdings")
    principal = st.number_input("YTD starting investment", min_value=1000.0, value=300000.0)
    frequency = st.selectbox("YTD table periods", ["Daily", "Weekly", "Monthly"], index=2)
    cadence = st.selectbox("Withdrawal / rebalance cadence", ["Daily", "Weekly", "Monthly"], index=2)
    enabled = st.checkbox("Enable YTD withdrawals")
    amount = st.number_input("Withdrawal per selected cadence", min_value=0.0, value=0.0, disabled=not enabled)
    if st.button("Run YTD simulation"):
        if not symbols:
            st.error("Select at least one holding.")
            return
        try:
            with st.spinner("Loading adjusted daily history…"):
                # Exclude today's potentially unfinished trading session.
                as_of = (pd.Timestamp.now(tz="America/New_York") - pd.Timedelta(days=1)).date()
                histories = YahooFinanceProvider().download_daily_history_since(symbols, start=f"{as_of.year - 1}-12-01")
                prices = history_prices(histories, symbols)
                outputs = {name: simulate_ytd(prices, principal, frequency, amount if enabled else 0,
                           cadence, rb, as_of) for name, rb in [("Rebalanced", True), ("Non-Rebalanced", False)]}
                st.session_state.ytd_output = (outputs, str(as_of))
                st.session_state.ytd_completed_inputs = dict(holdings=symbols, principal=principal,
                    reporting_frequency=frequency, cadence=cadence, withdrawal=amount if enabled else 0)
        except Exception as exc:
            st.error(f"YTD simulation unavailable: {exc}")
    if "ytd_output" in st.session_state:
        outputs, date = st.session_state.ytd_output
        st.caption(f"Last completed run; cutoff {date}. Run again after changing inputs. Missing dates are excluded, not filled with invented returns.")
        for name, (table, daily) in outputs.items():
            st.markdown(f"#### {name}")
            st.caption(f"Actual data through {daily.index[-1].date()}")
            if not daily.attrs.get('full_ytd', False):
                st.warning(f"Partial YTD: available shared history starts {daily.attrs.get('start_date')}. Earlier returns are not assumed or fabricated.")
            show_snapshot(snapshot(daily))
            st.caption("Positive periods measure investment returns before withdrawals; months include the current partial month.")
            configs = {c: st.column_config.NumberColumn(format="%.2f%%" if c == "Return %" else "$%.2f") for c in table.columns}
            st.dataframe(table, width="stretch", column_config=configs)
            st.line_chart(daily["Ending Balance"])
            st.download_button(f"Download {name} YTD CSV", table.to_csv().encode(), f"YTD_{name}.csv")
        name = st.text_input('YTD simulation name', value='YTD Portfolio')
        if st.button('Save YTD simulation', key='save_ytd_simulation'):
            from portfolio_simulations import load_saved_simulations, persist_saved_simulations
            try:
                folder = Path(__file__).resolve().parent / 'data'
                record = make_saved_record(outputs, st.session_state.get('ytd_completed_inputs', {}), name)
                records = load_saved_simulations(folder)
                records.append(record)
                ok, message = persist_saved_simulations(records, folder, f"data: save YTD simulation {record['id']}")
                if on_saved:
                    on_saved()
                (st.success if ok else st.warning)(message)
                st.info('Find this snapshot in Saved / Manage → Saved simulations.')
            except Exception as exc:
                st.error(f'Could not save YTD simulation: {exc}')
