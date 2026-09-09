"""Daily-ledger YTD simulation; presentation aggregation never changes cash flows."""
import numpy as np
import pandas as pd


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
    if before.empty or current.empty or p.shape[1] == 0:
        raise ValueError("Full YTD requires a shared prior-year closing price and current-year daily prices for every holding.")
    if (start - before.index[-1]).days > 7:
        raise ValueError("Prior-year closing price is stale; refresh daily history.")
    returns = pd.concat([before.tail(1), current]).pct_change(fill_method=None).iloc[1:]
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


def render_ytd(market):
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
                histories = YahooFinanceProvider().download_daily_history(symbols, period="2y")
                prices = pd.concat({s: histories[s]["Close"] for s in symbols}, axis=1)
                # Exclude today's potentially unfinished trading session.
                as_of = pd.Timestamp.now(tz="America/New_York").date() - pd.Timedelta(days=1)
                outputs = {name: simulate_ytd(prices, principal, frequency, amount if enabled else 0,
                           cadence, rb, as_of) for name, rb in [("Rebalanced", True), ("Non-Rebalanced", False)]}
                st.session_state.ytd_output = (outputs, str(as_of))
        except Exception as exc:
            st.error(f"YTD simulation unavailable: {exc}")
    if "ytd_output" in st.session_state:
        outputs, date = st.session_state.ytd_output
        st.caption(f"Last completed run; cutoff {date}. Run again after changing inputs. Missing dates are excluded, not filled with invented returns.")
        for name, (table, daily) in outputs.items():
            st.markdown(f"#### {name}")
            st.caption(f"Actual data through {daily.index[-1].date()}")
            configs = {c: st.column_config.NumberColumn(format="%.2f%%" if c == "Return %" else "$%.2f") for c in table.columns}
            st.dataframe(table, width="stretch", column_config=configs)
            st.line_chart(daily["Ending Balance"])
            st.download_button(f"Download {name} YTD CSV", table.to_csv().encode(), f"YTD_{name}.csv")
