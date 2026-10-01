# MarketScope v5.9.75 — Persistent Build Simulation Withdrawal Tabs

## Regression fixed

In v5.9.74, the requested four-tab row was correctly moved inside Build Simulation, but the actual `st.tabs()` creation lived inside the successful Yearly Withdrawal calculation branch.

That meant when:

- Yearly Withdrawal was OFF,
- Withdrawal/year was $0,
- allocation was unresolved, or
- annual withdrawal data was unavailable,

the entire tab row disappeared.

## New behavior

The row is now always visible inside a valid Build Simulation:

1. **↻ Rebalanced annually**
2. **↝ Not rebalanced**
3. **⚖ Side-by-side**
4. **📅 Annual Reset**

When Yearly Withdrawal is ON and the calculation succeeds, the tabs show the full live schedules exactly as before.

When Yearly Withdrawal is OFF or cannot yet be calculated, the same tabs remain visible and show contextual instructions instead of disappearing.

## Annual Reset

The Annual Reset tab remains in the exact fourth position beside Side-by-Side.

When Yearly Withdrawal is active, it continues using:

- current starting investment
- current allocation
- current annual withdrawal
- current completed-year simulation window
- only years where every selected instrument has a valid annual return

When Yearly Withdrawal is OFF, the Annual Reset tab stays visible and explains that the Yearly Withdrawal toggle must be enabled to apply the Withdrawal/year amount.

## No calculation changes

This release changes visibility/state handling only.

No changes were made to:

- annual-return calculations
- withdrawal ordering
- Rebalanced calculations
- Not-Rebalanced calculations
- Annual Reset formulas
- monthly withdrawals
- price targets
- ranking datasets
- saved simulation persistence

PDF layout is bumped to **v33** so rebuilt saved PDFs identify MarketScope v5.9.75.
