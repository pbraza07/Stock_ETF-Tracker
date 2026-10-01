# Acceptance evidence and remaining requirements

| Requirement | Implemented evidence | Remaining limit |
|---|---|---|
| Forward assumptions / no winner extrapolation | Component CMA; historical stock alpha is zero; tests A-C | Market valuation and institutional inputs require dated provider/user data; ERP is an assumption |
| No mechanical return decay / horizon signals | Configurable horizon bands; 10/30-year prefix test; Year-20 momentum zero | Weights need empirical validation |
| Arithmetic / geometric distinction | Economic geometric drift, first-year arithmetic sample mean, median reference CAGR separately reported | Tail truncation, event losses and costs alter realized path moments |
| Fat tails, correlations, scenarios, impairment | Joint monthly paths; nine scenarios; stress correlation and persistent cash recovery after impairment | Hazard/transition probabilities are configured, not fitted or certified |
| Historical bootstrap | Contiguous observed monthly blocks of mixed lengths; historical means centered to forward drift | Falls back explicitly to MC if monthly joint observations unavailable |
| Point-in-time walk-forward / survivor control | Executable planning_backtest.py reconstructs selection and forecasts from filtered vintages; future data inaccessible through provided arguments; realized data separate | Full empirical run BLOCKED on verified point-in-time and delisted datasets. Current holdings alone cannot satisfy this requirement |
| Calibration / forecast bias | Nonoverlapping horizon reports, coverage, sign accuracy, bias and optional volatility error; past-only correction gated | No verified empirical sample supplied; default UNVALIDATED and unscored |
| Inflation / taxes / fees | Net-spending ledger; real/nominal modes; account blend; costs and sale taxes | Average-cost approximation; no exact tax lots, brackets, loss credits or penalties |
| PAL / sequence risk | Interest, variable rates, monthly maintenance calls, forced repayment, early/middle/late shocks | No intraday calls, security eligibility haircuts or lender-specific exceptions |
| Sustainable spending / goals | Bisection against shared widened paths, success target, goal success and ever-depletion tracking | Monte Carlo subset and finite-horizon estimate; not guaranteed lifetime spending |
| RB / NR withdrawal policies | Shared paths, maintenance schedule, proportional/ranked/custom/tax-aware sales; ticker sale table | Tax-aware uses current estimated tax rate; full lot optimization not implemented |
| Concentration / trust / disagreement | HHI, sector allocation, covariance risk contributions, correlation-based independent-holdings approximation, separate model medians and trust fields | Complete factor exposures absent; model agreement does not establish correctness |
| Stress suite | Ten named illustrative templates with endings, drawdowns, depletion, funded years, recovery | Exact historical replay/worst historical result needs actual portfolio history; clearly not claimed |
| PDFs / existing tools / mobile layout | Shared dark PDF theme, dated tables/charts, unchanged legacy regression; responsive Streamlit columns and scrolling tables | AppTest is not full browser/mobile QA; production validation remains open |

Do not represent this release as survivorship-bias-free, empirically calibrated, lender-grade, tax-advice software or a guarantee of investment outcomes. Passing software tests proves the specified implementation properties, not future investment accuracy.
