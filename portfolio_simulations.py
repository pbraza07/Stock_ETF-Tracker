from __future__ import annotations

import base64
import json
import os
import re
from io import BytesIO
from pathlib import Path
from typing import Iterable

import requests
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from persistence import DEFAULT_BRANCH, DEFAULT_REPO, format_et, now_et

SIMULATION_PATH = "data/saved_portfolio_simulations.json"
BOOTSTRAP_PATH = "data/saved_portfolio_simulations.bootstrap.json"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "MarketScope-Render",
    }


def _raw_url(path: str) -> str:
    return f"https://raw.githubusercontent.com/{DEFAULT_REPO}/{DEFAULT_BRANCH}/{path}"


def _normalize_records(payload) -> list[dict]:
    if not isinstance(payload, list):
        return []
    records = [dict(x) for x in payload if isinstance(x, dict) and x.get("id")]
    records.sort(key=lambda x: str(x.get("created_at_et") or ""), reverse=True)
    return records


def load_saved_simulations(local_data_dir: Path, timeout: int = 8) -> list[dict]:
    """Load durable saved simulations, falling back to local/bootstrap storage."""
    local_path = Path(local_data_dir) / Path(SIMULATION_PATH).name
    try:
        if local_path.exists():
            local = _normalize_records(json.loads(local_path.read_text(encoding="utf-8")))
            if local:
                return local
    except Exception:
        pass

    try:
        response = requests.get(_raw_url(SIMULATION_PATH), timeout=timeout)
        if response.status_code == 200:
            remote = _normalize_records(response.json())
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(json.dumps(remote, indent=2) + "\n", encoding="utf-8")
            return remote
    except Exception:
        pass

    bootstrap = Path(local_data_dir) / Path(BOOTSTRAP_PATH).name
    try:
        if bootstrap.exists():
            return _normalize_records(json.loads(bootstrap.read_text(encoding="utf-8")))
    except Exception:
        pass
    return []


def persist_saved_simulations(records: list[dict], local_data_dir: Path, message: str) -> tuple[bool, str]:
    """Persist the simulation library locally and, when configured, durably to GitHub."""
    records = _normalize_records(records)
    local_path = Path(local_data_dir) / Path(SIMULATION_PATH).name
    local_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(records, indent=2) + "\n"
    local_path.write_text(text, encoding="utf-8")

    token = os.getenv("MARKETSCOPE_GITHUB_TOKEN", "").strip()
    if not token:
        return False, (
            "Saved in the current app session/server. For permanent cross-device storage, "
            "configure MARKETSCOPE_GITHUB_TOKEN in Render."
        )

    url = f"https://api.github.com/repos/{DEFAULT_REPO}/contents/{SIMULATION_PATH}"
    headers = _headers(token)
    try:
        current = requests.get(url, headers=headers, params={"ref": DEFAULT_BRANCH}, timeout=15)
        sha = (current.json() or {}).get("sha") if current.status_code == 200 else None
        if current.status_code not in (200, 404):
            return False, f"GitHub read failed ({current.status_code})"
        commit_message = message if "[skip render]" in message.lower() else f"{message} [skip render]"
        body = {
            "message": commit_message,
            "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            "branch": DEFAULT_BRANCH,
        }
        if sha:
            body["sha"] = sha
        saved = requests.put(url, headers=headers, json=body, timeout=30)
        if saved.status_code not in (200, 201):
            return False, f"GitHub save failed ({saved.status_code}): {saved.text[:220]}"
        return True, "Saved permanently to the in-app simulation library."
    except Exception as exc:
        return False, f"GitHub persistence error: {exc}"


def simulation_id() -> str:
    stamp = now_et().strftime("%Y%m%d-%H%M%S-%f")[:-3]
    return f"SIM-{stamp}"


def safe_filename(record: dict) -> str:
    name = str(record.get("name") or record.get("id") or "Portfolio-Simulation")
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "Portfolio_Simulation"
    created = str(record.get("created_date") or now_et().date().isoformat())
    return f"MarketScope_{safe}_{created}.pdf"


def _money(value: float, signed: bool = False) -> str:
    value = float(value or 0)
    return f"${value:+,.2f}" if signed else f"${value:,.2f}"


def _pct(value: float) -> str:
    return f"{float(value or 0):+.2f}%"


def _maybe_pct(value) -> str:
    try:
        if value is None:
            return "-"
        return f"{float(value):+.2f}%"
    except (TypeError, ValueError):
        return "-"


def _yield_pct(value) -> str:
    try:
        if value is None:
            return "-"
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "-"


def _best_worst(year, value) -> str:
    if not year or value is None:
        return "-"
    try:
        return f"{year} {float(value):+.2f}%"
    except (TypeError, ValueError):
        return "-"


def _as_float_or_none(value):
    try:
        if value is None:
            return None
        value = float(value)
        if value != value:  # NaN
            return None
        return value
    except (TypeError, ValueError):
        return None


def _combined_portfolio_metrics(record: dict) -> dict:
    """Calculate allocation-weighted portfolio analytics from the saved instrument rows.

    Short-horizon and calendar-year returns are combined as a static-weight portfolio:
    sum(allocation_weight * instrument_return).  A combined period is shown only when
    every positive-weight instrument has a saved value for that period, avoiding a
    deceptively optimistic/partial portfolio result.
    """
    instruments = [dict(x) for x in (record.get("instruments") or []) if isinstance(x, dict)]
    active = []
    for item in instruments:
        weight = _as_float_or_none(item.get("weight"))
        if weight is None or weight <= 0:
            allocated = _as_float_or_none(item.get("allocated"))
            total = _as_float_or_none(record.get("total_invested"))
            weight = (allocated / total * 100.0) if allocated is not None and total and total > 0 else 0.0
        if weight > 0:
            active.append((item, weight))

    weight_total = sum(weight for _, weight in active)
    if not active or weight_total <= 0:
        return {
            "cagr_10y_pct": None,
            "positive_years": 0,
            "available_years": 0,
            "worst_year": None,
            "worst_year_pct": None,
            "best_year": None,
            "best_year_pct": None,
            "regular_yield_pct": None,
            "est_annual_dividend": None,
            "performance": {},
        }

    weights = [(item, weight / weight_total) for item, weight in active]

    def weighted_metric(metric: str):
        combined = 0.0
        for item, fraction in weights:
            value = _as_float_or_none((item.get("performance") or {}).get(metric))
            if value is None:
                return None
            combined += fraction * value
        return combined

    preferred = ["1D", "1M", "3M", "6M", "YTD"]
    year_keys = sorted(
        {
            str(key)
            for item, _ in weights
            for key in (item.get("performance") or {}).keys()
            if str(key).isdigit() and len(str(key)) == 4
        },
        reverse=True,
    )
    performance = {metric: weighted_metric(metric) for metric in [*preferred, *year_keys]}

    annual = [(year, performance.get(year)) for year in year_keys if performance.get(year) is not None]
    positive_years = sum(1 for _, value in annual if value is not None and value > 0)
    worst = min(annual, key=lambda pair: pair[1]) if annual else None
    best = max(annual, key=lambda pair: pair[1]) if annual else None

    cagr = None
    ten_years = year_keys[:10]
    if len(ten_years) == 10 and all(performance.get(year) is not None for year in ten_years):
        compound = 1.0
        valid = True
        for year in reversed(ten_years):
            factor = 1.0 + float(performance[year]) / 100.0
            if factor <= 0:
                valid = False
                break
            compound *= factor
        if valid and compound > 0:
            cagr = (compound ** (1.0 / 10.0) - 1.0) * 100.0

    yields = []
    dividends = []
    all_yields_available = True
    all_dividends_available = True
    for item, fraction in weights:
        yld = _as_float_or_none(item.get("regular_yield_pct"))
        if yld is None:
            all_yields_available = False
        else:
            yields.append((fraction, yld))
        div = _as_float_or_none(item.get("est_annual_dividend"))
        if div is None:
            all_dividends_available = False
        else:
            dividends.append(div)

    regular_yield = sum(fraction * yld for fraction, yld in yields) if all_yields_available else None
    est_dividend = sum(dividends) if all_dividends_available else None

    return {
        "cagr_10y_pct": cagr,
        "positive_years": positive_years,
        "available_years": len(annual),
        "worst_year": worst[0] if worst else None,
        "worst_year_pct": worst[1] if worst else None,
        "best_year": best[0] if best else None,
        "best_year_pct": best[1] if best else None,
        "regular_yield_pct": regular_yield,
        "est_annual_dividend": est_dividend,
        "performance": performance,
    }


def _marketscope_version() -> str:
    try:
        return (Path(__file__).resolve().parent / "VERSION.txt").read_text(encoding="utf-8").strip() or "unknown"
    except Exception:
        return "unknown"


def build_portfolio_simulation_pdf(record: dict) -> bytes:
    """Build the MarketScope saved portfolio PDF with a legible combined first page."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))

    bg = HexColor("#06101A")
    card = HexColor("#0C1824")
    card2 = HexColor("#0B1621")
    border = HexColor("#27465A")
    accent = HexColor("#56E58B")
    cyan = HexColor("#68D7FF")
    text = HexColor("#F2F7FB")
    muted = HexColor("#A5B5C3")
    positive = HexColor("#4ADE80")
    negative = HexColor("#FB7185")
    line = HexColor("#20394A")

    instruments = list(record.get("instruments") or [])
    combined = _combined_portfolio_metrics(record)

    def color_for_number(value):
        numeric = _as_float_or_none(value)
        if numeric is None:
            return muted
        if numeric > 0:
            return positive
        if numeric < 0:
            return negative
        return text

    def draw_page_background(width, height, wash_height=116):
        c.setFillColor(bg)
        c.rect(0, 0, width, height, fill=1, stroke=0)
        c.setFillColor(HexColor("#081E25"))
        c.rect(0, height - wash_height, width, wash_height, fill=1, stroke=0)

    def draw_footer(width, page_no: int, note: str | None = None):
        c.setFillColor(muted)
        c.setFont("Helvetica", 6.8)
        footer_note = note or "Historical simulation based on MarketScope saved adjusted-return data. Not a forecast or investment recommendation."
        c.drawString(26, 18, footer_note[:155])
        c.drawRightString(width - 26, 18, f"Page {page_no}")

    # ------------------------------------------------------------------
    # Page 1: combined portfolio analytics and combined timeframe returns.
    # Landscape is intentional; completed annual returns are dynamically paginated into legible timeframe bands.
    # ------------------------------------------------------------------
    lwidth, lheight = landscape(A4)
    c.setPageSize((lwidth, lheight))
    draw_page_background(lwidth, lheight, wash_height=112)

    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(lwidth / 2, lheight - 36, "PORTFOLIO SPLIT SIMULATOR")
    pdf_version = str(record.get("app_version") or _marketscope_version())
    c.setFillColor(muted)
    c.setFont("Helvetica-Bold", 7.2)
    c.drawRightString(lwidth - 26, lheight - 36, f"MarketScope v{pdf_version}")
    c.setFillColor(muted)
    c.setFont("Helvetica", 8.5)
    meta = (
        f"{record.get('name') or record.get('id')}  |  Period {record.get('period', 'YTD')}  |  "
        f"{record.get('allocation_mode', 'Equal split')}  |  {record.get('created_at_display_et', '')}"
    )
    c.drawCentredString(lwidth / 2, lheight - 55, meta[:165])

    # Four main portfolio result cards. v5.9.68 keeps the withdrawal context
    # inside TOTAL INVESTED so page 1 shows the income assumptions/results at a
    # glance without adding a separate large section.
    labels = [
        ("TOTAL INVESTED", _money(record.get("total_invested", 0)), text),
        ("EST. ENDING VALUE", _money(record.get("ending_value", 0)), text),
        ("PROFIT / LOSS", _money(record.get("profit_loss", 0), signed=True), color_for_number(record.get("profit_loss"))),
        ("TOTAL RETURN", _pct(record.get("total_return", 0)), color_for_number(record.get("total_return"))),
    ]

    def _page1_withdrawal_lines():
        if bool(record.get("monthly_withdrawals_enabled")):
            amount = _as_float_or_none(record.get("monthly_withdrawal_amount")) or 0.0
            rb = dict(record.get("monthly_withdrawal_rebalanced") or {})
            nr = dict(record.get("monthly_withdrawal_not_rebalanced") or {})
            rb_end = _as_float_or_none(rb.get("ending_balance"))
            nr_end = _as_float_or_none(nr.get("ending_balance"))
            if rb_end is None:
                rb_end = _as_float_or_none(record.get("monthly_withdrawal_rebalanced_ending_balance")) or 0.0
            if nr_end is None:
                nr_end = _as_float_or_none(record.get("monthly_withdrawal_ending_balance")) or 0.0
            rb_schedule = [dict(x) for x in (record.get("monthly_withdrawal_rebalanced_schedule") or rb.get("schedule") or []) if isinstance(x, dict)]
            nr_schedule = [dict(x) for x in (record.get("monthly_withdrawal_not_rebalanced_schedule") or nr.get("schedule") or []) if isinstance(x, dict)]
            rb_pos = int(record.get("monthly_positive_months_rebalanced") if record.get("monthly_positive_months_rebalanced") is not None else rb.get("positive_months") or sum(1 for row in rb_schedule if float(row.get("portfolio_return_pct") or 0.0) > 0.0))
            nr_pos = int(record.get("monthly_positive_months_not_rebalanced") if record.get("monthly_positive_months_not_rebalanced") is not None else nr.get("positive_months") or sum(1 for row in nr_schedule if float(row.get("portfolio_return_pct") or 0.0) > 0.0))
            rb_total = int(record.get("monthly_months_modeled_rebalanced") if record.get("monthly_months_modeled_rebalanced") is not None else rb.get("months_modeled") or len(rb_schedule))
            nr_total = int(record.get("monthly_months_modeled_not_rebalanced") if record.get("monthly_months_modeled_not_rebalanced") is not None else nr.get("months_modeled") or len(nr_schedule))
            return [
                f"MONTHLY WITHDRAWAL {_money(amount)}",
                f"REBALANCED {_money(rb_end)}  |  NOT-REBAL {_money(nr_end)}",
                f"REBALANCE DIFF {_money(rb_end - nr_end, signed=True)}  |  POSITIVE RB {rb_pos}/{rb_total} NR {nr_pos}/{nr_total}",
            ]

        if bool(record.get("annual_withdrawals_enabled")):
            amount = _as_float_or_none(record.get("annual_withdrawal_amount")) or 0.0
            rb = dict(record.get("withdrawal_rebalanced") or {})
            nr = dict(record.get("withdrawal_not_rebalanced") or {})
            rb_end = _as_float_or_none(rb.get("ending_balance")) or 0.0
            nr_end = _as_float_or_none(nr.get("ending_balance"))
            if nr_end is None:
                nr_end = _as_float_or_none(record.get("withdrawal_ending_balance")) or 0.0
            rb_schedule = [dict(x) for x in (record.get("withdrawal_rebalanced_schedule") or rb.get("schedule") or []) if isinstance(x, dict)]
            nr_schedule = [dict(x) for x in (record.get("withdrawal_not_rebalanced_schedule") or nr.get("schedule") or []) if isinstance(x, dict)]

            def _positive_years(saved_key, modeled_key, result, schedule):
                saved = record.get(saved_key)
                modeled = record.get(modeled_key)
                if saved is not None:
                    positive = int(saved)
                elif result.get("positive_years") is not None:
                    positive = int(result.get("positive_years"))
                else:
                    positive = sum(
                        1
                        for row in schedule
                        if str(row.get("year") or "").strip().lower() != "ytd (partial)"
                        and float(row.get("portfolio_return_pct") or 0.0) > 0.0
                    )
                if modeled is not None:
                    total = int(modeled)
                elif result.get("years_modeled") is not None:
                    total = int(result.get("years_modeled"))
                else:
                    total = sum(
                        1
                        for row in schedule
                        if str(row.get("year") or "").strip().lower() != "ytd (partial)"
                    )
                return positive, total

            rb_pos, rb_years = _positive_years(
                "annual_positive_years_rebalanced",
                "annual_years_modeled_rebalanced",
                rb,
                rb_schedule,
            )
            nr_pos, nr_years = _positive_years(
                "annual_positive_years_not_rebalanced",
                "annual_years_modeled_not_rebalanced",
                nr,
                nr_schedule,
            )
            return [
                f"ANNUAL WITHDRAWAL {_money(amount)}",
                f"REBALANCED {_money(rb_end)}  |  NOT-REBAL {_money(nr_end)}",
                f"REBALANCE DIFF {_money(rb_end - nr_end, signed=True)}  |  POSITIVE YRS RB {rb_pos}/{rb_years} NR {nr_pos}/{nr_years}",
            ]
        return []

    withdrawal_lines = _page1_withdrawal_lines()
    x0 = 24
    gap = 10
    box_w = (lwidth - 2 * x0 - 3 * gap) / 4
    box_y = lheight - (132 if withdrawal_lines else 128)
    box_h = 70 if withdrawal_lines else 54
    for i, (label, value, value_color) in enumerate(labels):
        x = x0 + i * (box_w + gap)
        c.setFillColor(card)
        c.setStrokeColor(border)
        c.setLineWidth(0.8)
        c.roundRect(x, box_y, box_w, box_h, 7, fill=1, stroke=1)
        c.setFillColor(muted)
        c.setFont("Helvetica-Bold", 7.4 if withdrawal_lines else 7.6)
        c.drawCentredString(x + box_w / 2, box_y + (52 if withdrawal_lines else 36), label)
        c.setFillColor(value_color)
        c.setFont("Helvetica-Bold", 12.4 if withdrawal_lines else 13.5)
        c.drawCentredString(x + box_w / 2, box_y + (31 if withdrawal_lines else 15), value)
        if i == 0 and withdrawal_lines:
            c.setFillColor(muted)
            c.setFont("Helvetica-Bold", 4.65)
            c.drawCentredString(x + box_w / 2, box_y + 18, withdrawal_lines[0][:72])
            c.setFont("Helvetica", 4.15)
            c.drawCentredString(x + box_w / 2, box_y + 10.5, withdrawal_lines[1][:82])
            c.setFillColor(cyan)
            c.setFont("Helvetica-Bold", 4.05)
            c.drawCentredString(x + box_w / 2, box_y + 3.5, withdrawal_lines[2][:92])

    # Combined portfolio performance statistics.
    section_y = box_y - 28
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(24, section_y, "COMBINED PORTFOLIO PERFORMANCE")
    c.setFillColor(muted)
    c.setFont("Helvetica", 7.0)
    c.drawRightString(lwidth - 24, section_y, "Allocation-weighted combination of all instruments")

    pos_years = f"{int(combined.get('positive_years') or 0)}/{int(combined.get('available_years') or 0)}"
    page1_positive_months = "-"
    if bool(record.get("monthly_withdrawals_enabled")):
        _page1_rb = dict(record.get("monthly_withdrawal_rebalanced") or {})
        _page1_nr = dict(record.get("monthly_withdrawal_not_rebalanced") or {})
        _page1_rb_schedule = [dict(x) for x in (record.get("monthly_withdrawal_rebalanced_schedule") or _page1_rb.get("schedule") or []) if isinstance(x, dict)]
        _page1_nr_schedule = [dict(x) for x in (record.get("monthly_withdrawal_not_rebalanced_schedule") or _page1_nr.get("schedule") or []) if isinstance(x, dict)]
        _page1_rb_pos = int(_page1_rb.get("positive_months") if _page1_rb.get("positive_months") is not None else sum(1 for row in _page1_rb_schedule if float(row.get("portfolio_return_pct") or 0) > 0))
        _page1_nr_pos = int(_page1_nr.get("positive_months") if _page1_nr.get("positive_months") is not None else sum(1 for row in _page1_nr_schedule if float(row.get("portfolio_return_pct") or 0) > 0))
        _page1_rb_total = int(_page1_rb.get("months_modeled") if _page1_rb.get("months_modeled") is not None else len(_page1_rb_schedule))
        _page1_nr_total = int(_page1_nr.get("months_modeled") if _page1_nr.get("months_modeled") is not None else len(_page1_nr_schedule))
        page1_positive_months = f"RB {_page1_rb_pos}/{_page1_rb_total} | NR {_page1_nr_pos}/{_page1_nr_total}"
    stat_cells = [
        ("10Y CAGR", _maybe_pct(combined.get("cagr_10y_pct")), color_for_number(combined.get("cagr_10y_pct"))),
        ("POS YEARS", pos_years, text),
        ("POS MONTHS", page1_positive_months, cyan),
        ("WORST YEAR", _best_worst(combined.get("worst_year"), combined.get("worst_year_pct")), color_for_number(combined.get("worst_year_pct"))),
        ("BEST YEAR", _best_worst(combined.get("best_year"), combined.get("best_year_pct")), color_for_number(combined.get("best_year_pct"))),
        ("REG. YIELD", _yield_pct(combined.get("regular_yield_pct")), cyan),
        ("EST. ANNUAL DIV.", _money(combined.get("est_annual_dividend") or 0) if combined.get("est_annual_dividend") is not None else "-", cyan),
    ]
    stat_x = 24
    stat_y = section_y - 64
    stat_gap = 7
    stat_w = (lwidth - 48 - stat_gap * (len(stat_cells) - 1)) / len(stat_cells)
    stat_h = 50
    for i, (label, value, value_color) in enumerate(stat_cells):
        x = stat_x + i * (stat_w + stat_gap)
        c.setFillColor(card2)
        c.setStrokeColor(border)
        c.setLineWidth(0.65)
        c.roundRect(x, stat_y, stat_w, stat_h, 5, fill=1, stroke=1)
        c.setFillColor(muted)
        c.setFont("Helvetica-Bold", 7.4)
        c.drawCentredString(x + stat_w / 2, stat_y + 33, label)
        c.setFillColor(value_color)
        # Long best/worst values need slightly smaller text than CAGR/yield.
        value_font = 8.0 if label == "POS MONTHS" else (9.2 if label in {"WORST YEAR", "BEST YEAR"} else 11.2)
        c.setFont("Helvetica-Bold", value_font)
        c.drawCentredString(x + stat_w / 2, stat_y + 13, str(value)[:22])

    # First-page instrument snapshot requested by the portfolio workflow.
    # Two compact columns allow up to 20 instruments to show symbol/name, current price,
    # sector, analyst rating and low/average/high analyst price targets without shrinking
    # the portfolio KPI cards above. Older saved records safely render dashes.
    overview_title_y = stat_y - 28
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(24, overview_title_y, "PORTFOLIO INSTRUMENT SNAPSHOT")
    c.setFillColor(muted)
    c.setFont("Helvetica", 7.0)
    c.drawRightString(lwidth - 24, overview_title_y, "Name • sector • analyst rating • current price • low / average-consensus / high targets")

    def target_text(value):
        numeric = _as_float_or_none(value)
        return _money(numeric) if numeric is not None and numeric > 0 else "-"

    def rating_color(value):
        rating = str(value or "Not Rated")
        if rating in {"Strong Buy", "Buy"}:
            return positive
        if rating in {"Sell", "Strong Sell"}:
            return negative
        if rating == "Hold":
            return HexColor("#FDE68A")
        return muted

    shown = instruments[:20]
    split_at = (len(shown) + 1) // 2
    left = shown[:split_at]
    right = shown[split_at:]
    column_gap = 12
    overview_x = 24
    overview_w = (lwidth - 48 - column_gap) / 2
    row_h = 27
    top_y = overview_title_y - 12

    for column_no, column_items in enumerate((left, right)):
        x = overview_x + column_no * (overview_w + column_gap)
        y = top_y
        for ridx, item in enumerate(column_items):
            c.setFillColor(card if ridx % 2 == 0 else card2)
            c.setStrokeColor(line)
            c.setLineWidth(0.45)
            c.roundRect(x, y - row_h, overview_w, row_h - 2, 3, fill=1, stroke=1)

            symbol = str(item.get("symbol") or "-")[:10]
            name = str(item.get("name") or symbol)[:38]
            sector = str(item.get("sector") or item.get("industry") or "-")[:21]
            rating = str(item.get("analyst_rating") or "Not Rated")[:13]
            current_price = target_text(item.get("current_price"))
            low = target_text(item.get("price_target_low"))
            avg = target_text(item.get("price_target_average"))
            high = target_text(item.get("price_target_high"))

            c.setFillColor(text)
            c.setFont("Helvetica-Bold", 7.2)
            c.drawString(x + 6, y - 10, symbol)
            c.setFillColor(muted)
            c.setFont("Helvetica", 6.4)
            c.drawString(x + 48, y - 10, name)
            c.setFillColor(cyan)
            c.setFont("Helvetica-Bold", 6.2)
            c.drawRightString(x + overview_w - 6, y - 10, f"PRICE {current_price}")

            c.setFillColor(cyan)
            c.setFont("Helvetica-Bold", 5.9)
            c.drawString(x + 6, y - 21, sector)
            c.setFillColor(rating_color(rating))
            c.setFont("Helvetica-Bold", 5.9)
            c.drawString(x + 116, y - 21, rating)
            c.setFillColor(muted)
            c.setFont("Helvetica", 5.8)
            c.drawRightString(x + overview_w - 6, y - 21, f"LOW {low}   AVG/CONS {avg}   HIGH {high}")
            y -= row_h

    if len(instruments) > 20:
        c.setFillColor(muted)
        c.setFont("Helvetica", 6.4)
        c.drawString(24, 45, f"First page shows 20 of {len(instruments)} instruments; remaining instruments continue in the allocation detail pages.")
    else:
        c.setFillColor(muted)
        c.setFont("Helvetica", 6.4)
        c.drawString(24, 45, "ETF analyst rating/targets may be unavailable when stock-style consensus data is not published.")
    draw_footer(lwidth, 1)
    c.showPage()

    # ------------------------------------------------------------------
    # Combined timeframe performance. v5.9.58 grows with the annual-history
    # baseline instead of assuming exactly 25 completed years. Additional
    # completed years automatically spill onto continuation pages.
    # ------------------------------------------------------------------
    combined_perf = combined.get("performance") or {}
    preferred_timeframes = ["1D", "1M", "3M", "6M", "YTD"]
    saved_years = sorted(
        [str(key) for key in combined_perf if str(key).isdigit() and len(str(key)) == 4],
        reverse=True,
    )

    # First row combines short horizons plus five newest completed years.
    # Every later row contains up to ten annual-return columns. Three rows fit
    # comfortably per landscape page, so the PDF can expand indefinitely.
    timeframe_groups: list[list[str]] = []
    timeframe_groups.append(preferred_timeframes + saved_years[:5])
    remaining_years = saved_years[5:]
    for start_index in range(0, len(remaining_years), 10):
        timeframe_groups.append(remaining_years[start_index:start_index + 10])

    groups_per_page = 3
    combined_page_number = 2
    for page_group_start in range(0, len(timeframe_groups), groups_per_page):
        page_groups = timeframe_groups[page_group_start:page_group_start + groups_per_page]

        c.setPageSize((lwidth, lheight))
        draw_page_background(lwidth, lheight, wash_height=92)
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 17)
        c.drawCentredString(lwidth / 2, lheight - 36, "COMBINED TIMEFRAME PERFORMANCE")
        c.setFillColor(muted)
        c.setFont("Helvetica", 8)
        page_label = (
            "Allocation-weighted saved returns • actual completed calendar-year returns • not a forecast"
            if page_group_start == 0
            else "Historical annual-return continuation • automatically expands as each calendar year completes"
        )
        c.drawCentredString(lwidth / 2, lheight - 54, page_label)

        table_x = 24
        table_w = lwidth - 48
        header_h = 26
        value_h = 42

        def draw_timeframe_band(columns, header_y):
            if not columns:
                return header_y
            cell_w = table_w / len(columns)
            c.setFillColor(HexColor("#0A1A20"))
            c.setStrokeColor(accent)
            c.setLineWidth(0.8)
            c.roundRect(table_x, header_y, table_w, header_h, 4, fill=1, stroke=1)
            for i, label in enumerate(columns):
                x = table_x + i * cell_w
                if i:
                    c.setStrokeColor(line)
                    c.line(x, header_y, x, header_y + header_h)
                c.setFillColor(accent)
                c.setFont("Helvetica-Bold", 7.4)
                c.drawCentredString(x + cell_w / 2, header_y + 9.5, label)

            values_y = header_y - value_h - 3
            c.setFillColor(card)
            c.setStrokeColor(border)
            c.roundRect(table_x, values_y, table_w, value_h, 4, fill=1, stroke=1)
            for i, label in enumerate(columns):
                x = table_x + i * cell_w
                if i:
                    c.setStrokeColor(line)
                    c.line(x, values_y, x, values_y + value_h)
                value = _as_float_or_none(combined_perf.get(label))
                c.setFillColor(color_for_number(value))
                c.setFont("Helvetica-Bold", 8.5)
                c.drawCentredString(x + cell_w / 2, values_y + 15, _maybe_pct(value))
            return values_y

        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 10.5)
        heading = "RECENT / COMPLETED YEARS" if page_group_start == 0 else "EARLIER COMPLETED CALENDAR YEARS"
        c.drawString(24, lheight - 92, heading)

        values_y = lheight - 132
        for local_index, group in enumerate(page_groups):
            if local_index:
                c.setFillColor(muted)
                c.setFont("Helvetica-Bold", 7.2)
                c.drawString(24, values_y - 28, "OLDER COMPLETED CALENDAR YEARS")
                values_y = draw_timeframe_band(group, values_y - 67)
            else:
                values_y = draw_timeframe_band(group, values_y)

        notes_y = values_y - 42
        c.setFillColor(muted)
        c.setFont("Helvetica", 7.2)
        c.drawString(24, notes_y, "Method: each portfolio return is the saved instrument return weighted by its simulation allocation.")
        c.drawString(
            24,
            notes_y - 14,
            f"Completed-year history contains {len(saved_years)} annual columns on this saved simulation and expands automatically after future year-end refreshes.",
        )
        draw_footer(lwidth, combined_page_number)
        c.showPage()
        combined_page_number += 1

    # ------------------------------------------------------------------
    # Annual-withdrawal PDF results. v5.9.40 mirrors the in-app strategy
    # comparison: Rebalanced annually vs Not rebalanced, plus a side-by-side
    # yearly balance table. Legacy records still fall back to withdrawal_schedule.
    # ------------------------------------------------------------------
    legacy_schedule = [dict(x) for x in (record.get("withdrawal_schedule") or []) if isinstance(x, dict)]
    rb_result = dict(record.get("withdrawal_rebalanced") or {})
    nr_result = dict(record.get("withdrawal_not_rebalanced") or {})
    rb_schedule = [dict(x) for x in (record.get("withdrawal_rebalanced_schedule") or rb_result.get("schedule") or []) if isinstance(x, dict)]
    nr_schedule = [dict(x) for x in (record.get("withdrawal_not_rebalanced_schedule") or nr_result.get("schedule") or legacy_schedule) if isinstance(x, dict)]
    page_no = combined_page_number

    def _withdrawal_metric(result: dict, key: str, fallback=None):
        value = result.get(key)
        return fallback if value is None else value

    def _draw_withdrawal_detail_pages(
        title: str,
        subtitle: str,
        result: dict,
        schedule: list[dict],
        start_page_number: int,
    ) -> int:
        """Render every annual-withdrawal year, including dynamically growing full-history schedules."""
        rows_per_page = 20
        page_number = start_page_number
        total_rows = len(schedule)
        total_pages = max(1, (total_rows + rows_per_page - 1) // rows_per_page)

        for page_index, start in enumerate(range(0, max(1, total_rows), rows_per_page), start=1):
            rows = schedule[start:start + rows_per_page]
            c.setPageSize((lwidth, lheight))
            draw_page_background(lwidth, lheight, wash_height=92)
            c.setFillColor(accent)
            c.setFont("Helvetica-Bold", 17)
            c.drawCentredString(lwidth / 2, lheight - 36, title)
            c.setFillColor(muted)
            c.setFont("Helvetica", 7.8)
            page_suffix = f" | Annual page {page_index}/{total_pages}" if total_pages > 1 else ""
            c.drawCentredString(lwidth / 2, lheight - 54, (subtitle + page_suffix)[:175])

            metric_values = [
                ("ANNUAL WITHDRAWAL", _money(record.get("annual_withdrawal_amount") or 0), text),
                ("TOTAL WITHDRAWN", _money(_withdrawal_metric(result, "total_withdrawn", record.get("withdrawal_total") or 0)), text),
                ("PORTFOLIO REMAINING", _money(_withdrawal_metric(result, "ending_balance", record.get("withdrawal_ending_balance") or 0)), cyan),
                ("REMAINING + WITHDRAWALS", _money(_withdrawal_metric(result, "net_value_including_withdrawals", record.get("withdrawal_net_value") or 0)), cyan),
            ]
            mx, my, mgap = 24, lheight - 124, 8
            mw = (lwidth - 48 - 3 * mgap) / 4
            for i, (label, value, value_color) in enumerate(metric_values):
                x = mx + i * (mw + mgap)
                c.setFillColor(card)
                c.setStrokeColor(border)
                c.roundRect(x, my, mw, 45, 5, fill=1, stroke=1)
                c.setFillColor(muted)
                c.setFont("Helvetica-Bold", 6.8)
                c.drawCentredString(x + mw / 2, my + 29, label)
                c.setFillColor(value_color)
                c.setFont("Helvetica-Bold", 10.5)
                c.drawCentredString(x + mw / 2, my + 11, value)

            headers = ["YEAR", "START", "RETURN", "GAIN / LOSS", "BEFORE WITHDRAWAL", "WITHDRAWAL", "REMAINING"]
            widths = [72, 110, 78, 105, 125, 105, 125]
            tx0 = (lwidth - sum(widths)) / 2
            y = my - 22
            c.setFillColor(HexColor("#0A1A20"))
            c.setStrokeColor(accent)
            c.roundRect(tx0, y - 22, sum(widths), 22, 4, fill=1, stroke=1)
            x = tx0
            c.setFillColor(accent)
            c.setFont("Helvetica-Bold", 6.2)
            for label, w in zip(headers, widths):
                c.drawCentredString(x + w / 2, y - 14, label)
                x += w
            y -= 24

            for ridx, row in enumerate(rows):
                h = 19
                c.setFillColor(card if ridx % 2 == 0 else card2)
                c.setStrokeColor(line)
                c.rect(tx0, y - h, sum(widths), h, fill=1, stroke=1)
                values = [
                    str(row.get("year") or "-"),
                    _money(row.get("starting_balance") or 0),
                    _maybe_pct(row.get("portfolio_return_pct")),
                    _money(row.get("gain_loss") or 0, signed=True),
                    _money(row.get("balance_before_withdrawal") or 0),
                    _money(row.get("withdrawal") or 0),
                    _money(row.get("ending_balance") or 0),
                ]
                x = tx0
                for idx, (value, w) in enumerate(zip(values, widths)):
                    c.setFillColor(text if idx not in (2, 3) else color_for_number(row.get("portfolio_return_pct") if idx == 2 else row.get("gain_loss")))
                    c.setFont("Helvetica-Bold" if idx in (0, 2, 6) else "Helvetica", 6.2)
                    c.drawCentredString(x + w / 2, y - 12.5, str(value)[:24])
                    x += w
                y -= h

            depleted = str(_withdrawal_metric(result, "depleted_year", record.get("withdrawal_depleted_year") or "") or "").strip()
            c.setFillColor(negative if depleted else muted)
            c.setFont("Helvetica", 6.8)
            note = (
                f"Portfolio depleted during {depleted}; later annual withdrawals cannot be funded."
                if depleted else
                "Annual returns come directly from Market Table. Maximum-history simulations use every completed year shared by the selected portfolio."
            )
            c.drawString(24, 35, note[:155])
            draw_footer(
                lwidth,
                page_number,
                "Withdrawal schedule uses Market Table completed annual returns; taxes, fees and future returns are not modeled.",
            )
            c.showPage()
            page_number += 1

        return page_number

    if bool(record.get("annual_withdrawals_enabled")) and (rb_schedule or nr_schedule):
        # Strategy comparison summary page.
        c.setPageSize((lwidth, lheight))
        draw_page_background(lwidth, lheight, wash_height=92)
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 17)
        c.drawCentredString(lwidth / 2, lheight - 36, "ANNUAL WITHDRAWALS - STRATEGY COMPARISON")
        c.setFillColor(muted)
        c.setFont("Helvetica", 7.8)
        c.drawCentredString(
            lwidth / 2, lheight - 54,
            "Same starting portfolio and annual cash withdrawal. Rebalanced restores target weights after each withdrawal; Not rebalanced lets weights drift.",
        )

        rb_end = _as_float_or_none(_withdrawal_metric(rb_result, "ending_balance", 0)) or 0.0
        nr_end = _as_float_or_none(_withdrawal_metric(nr_result, "ending_balance", record.get("withdrawal_ending_balance") or 0)) or 0.0
        rb_total = _as_float_or_none(_withdrawal_metric(rb_result, "total_withdrawn", 0)) or 0.0
        nr_total = _as_float_or_none(_withdrawal_metric(nr_result, "total_withdrawn", record.get("withdrawal_total") or 0)) or 0.0
        difference = rb_end - nr_end
        summary_metrics = [
            ("ANNUAL WITHDRAWAL", _money(record.get("annual_withdrawal_amount") or 0), text),
            ("REBALANCED REMAINING", _money(rb_end), cyan),
            ("NOT REBALANCED REMAINING", _money(nr_end), cyan),
            ("REBALANCE DIFFERENCE", _money(difference, signed=True), color_for_number(difference)),
        ]
        mx, my, mgap = 24, lheight - 124, 8
        mw = (lwidth - 48 - 3 * mgap) / 4
        for i, (label, value, value_color) in enumerate(summary_metrics):
            x = mx + i * (mw + mgap)
            c.setFillColor(card)
            c.setStrokeColor(border)
            c.roundRect(x, my, mw, 45, 5, fill=1, stroke=1)
            c.setFillColor(muted)
            c.setFont("Helvetica-Bold", 6.8)
            c.drawCentredString(x + mw / 2, my + 29, label)
            c.setFillColor(value_color)
            c.setFont("Helvetica-Bold", 10.2)
            c.drawCentredString(x + mw / 2, my + 11, value)

        # Side-by-side yearly balances. Match rows by year so YTD/common-start adjustments are safe.
        rb_by_year = {str(r.get("year")): r for r in rb_schedule}
        nr_by_year = {str(r.get("year")): r for r in nr_schedule}
        ordered_years = []
        for row in nr_schedule + rb_schedule:
            key = str(row.get("year") or "-")
            if key not in ordered_years:
                ordered_years.append(key)
        headers = ["YEAR", "REBAL. RETURN", "REBAL. REMAINING", "NOT REBAL. RETURN", "NOT REBAL. REMAINING", "DIFFERENCE"]
        widths = [70, 100, 130, 110, 140, 120]
        tx0 = (lwidth - sum(widths)) / 2
        y = my - 24
        c.setFillColor(HexColor("#0A1A20"))
        c.setStrokeColor(accent)
        c.roundRect(tx0, y - 22, sum(widths), 22, 4, fill=1, stroke=1)
        x = tx0
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 6.2)
        for label, w in zip(headers, widths):
            c.drawCentredString(x + w / 2, y - 14, label)
            x += w
        y -= 24
        for ridx, year in enumerate(ordered_years[:21]):
            rbr = rb_by_year.get(year, {})
            nrr = nr_by_year.get(year, {})
            rb_bal = _as_float_or_none(rbr.get("ending_balance"))
            nr_bal = _as_float_or_none(nrr.get("ending_balance"))
            diff = (rb_bal - nr_bal) if rb_bal is not None and nr_bal is not None else None
            h = 19
            c.setFillColor(card if ridx % 2 == 0 else card2)
            c.setStrokeColor(line)
            c.rect(tx0, y - h, sum(widths), h, fill=1, stroke=1)
            vals = [
                year,
                _maybe_pct(rbr.get("portfolio_return_pct")) if rbr else "-",
                _money(rb_bal) if rb_bal is not None else "-",
                _maybe_pct(nrr.get("portfolio_return_pct")) if nrr else "-",
                _money(nr_bal) if nr_bal is not None else "-",
                _money(diff, signed=True) if diff is not None else "-",
            ]
            x = tx0
            for idx, (value, w) in enumerate(zip(vals, widths)):
                if idx in (1, 3):
                    src = rbr.get("portfolio_return_pct") if idx == 1 else nrr.get("portfolio_return_pct")
                    c.setFillColor(color_for_number(src))
                elif idx == 5:
                    c.setFillColor(color_for_number(diff))
                elif idx in (2, 4):
                    c.setFillColor(cyan)
                else:
                    c.setFillColor(text)
                c.setFont("Helvetica-Bold" if idx in (0, 2, 4, 5) else "Helvetica", 6.2)
                c.drawCentredString(x + w / 2, y - 12.5, str(value)[:24])
                x += w
            y -= h

        c.setFillColor(muted)
        c.setFont("Helvetica", 6.7)
        c.drawString(24, 35, f"Total withdrawn - Rebalanced: {_money(rb_total)} | Not rebalanced: {_money(nr_total)}")
        draw_footer(lwidth, page_no, "Strategy comparison uses identical saved annual returns and withdrawal amount; only the annual rebalancing rule differs.")
        c.showPage()
        page_no += 1

        if rb_schedule:
            page_no = _draw_withdrawal_detail_pages(
                "ANNUAL WITHDRAWAL SCHEDULE - REBALANCED",
                "After each Market Table completed-year return and withdrawal, the remaining portfolio is restored to the saved target allocation.",
                rb_result,
                rb_schedule,
                page_no,
            )
        if nr_schedule:
            page_no = _draw_withdrawal_detail_pages(
                "ANNUAL WITHDRAWAL SCHEDULE - NOT REBALANCED",
                "After each Market Table completed-year return and withdrawal, holdings retain their post-return weights and are allowed to drift.",
                nr_result,
                nr_schedule,
                page_no,
            )

    # ------------------------------------------------------------------
    # Monthly-withdrawal PDF results. v5.9.46 records the full real month-by-
    # month path. New simulations use actual adjusted month-end market returns.
    # Older saved simulations retain their original methodology label so a PDF
    # rebuild never misrepresents legacy equivalent-rate results as actual data.
    # ------------------------------------------------------------------
    mrb_result = dict(record.get("monthly_withdrawal_rebalanced") or {})
    mnr_result = dict(record.get("monthly_withdrawal_not_rebalanced") or {})
    mrb_schedule = [dict(x) for x in (record.get("monthly_withdrawal_rebalanced_schedule") or mrb_result.get("schedule") or []) if isinstance(x, dict)]
    mnr_schedule = [dict(x) for x in (record.get("monthly_withdrawal_not_rebalanced_schedule") or mnr_result.get("schedule") or []) if isinstance(x, dict)]

    monthly_method = str(
        record.get("monthly_return_method")
        or mrb_result.get("monthly_return_method")
        or mnr_result.get("monthly_return_method")
        or ""
    ).strip()
    monthly_is_actual = "actual adjusted month-end return" in monthly_method.lower()
    monthly_method_note = (
        "Actual adjusted month-end returns from Yahoo/yfinance daily market history. The monthly path uses the same adjusted daily history as Market Table and each completed year is reconciled to the displayed annual return."
        if monthly_is_actual
        else "Legacy equivalent monthly rates derived from saved annual returns."
    )

    def _draw_monthly_withdrawal_detail_pages(title: str, subtitle: str, result: dict, schedule: list[dict], start_page_number: int) -> int:
        rows_per_page = 20
        page_number = start_page_number
        total_rows = len(schedule)
        total_pages = max(1, (total_rows + rows_per_page - 1) // rows_per_page)
        for page_index, start in enumerate(range(0, max(1, total_rows), rows_per_page), start=1):
            rows = schedule[start:start + rows_per_page]
            c.setPageSize((lwidth, lheight))
            draw_page_background(lwidth, lheight, wash_height=92)
            c.setFillColor(accent)
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(lwidth / 2, lheight - 34, title)
            c.setFillColor(muted)
            c.setFont("Helvetica", 7.2)
            c.drawCentredString(lwidth / 2, lheight - 50, f"{subtitle[:145]}  |  Monthly page {page_index}/{total_pages}")

            metric_values = [
                ("MONTHLY WITHDRAWAL", _money(record.get("monthly_withdrawal_amount") or 0), text),
                ("TOTAL WITHDRAWN", _money(_withdrawal_metric(result, "total_withdrawn", record.get("monthly_withdrawal_total") or 0)), text),
                ("PORTFOLIO REMAINING", _money(_withdrawal_metric(result, "ending_balance", record.get("monthly_withdrawal_ending_balance") or 0)), cyan),
                ("MONTHS MODELED", str(len(schedule)), cyan),
            ]
            mx, my, mgap = 24, lheight - 116, 8
            mw = (lwidth - 48 - 3 * mgap) / 4
            for i, (label, value, value_color) in enumerate(metric_values):
                x = mx + i * (mw + mgap)
                c.setFillColor(card)
                c.setStrokeColor(border)
                c.roundRect(x, my, mw, 40, 5, fill=1, stroke=1)
                c.setFillColor(muted)
                c.setFont("Helvetica-Bold", 6.4)
                c.drawCentredString(x + mw / 2, my + 25, label)
                c.setFillColor(value_color)
                c.setFont("Helvetica-Bold", 9.6)
                c.drawCentredString(x + mw / 2, my + 9, str(value))

            headers = ["MONTH", "START", "MONTH RETURN", "GAIN / LOSS", "BEFORE WITHDRAWAL", "WITHDRAWAL", "REMAINING"]
            widths = [72, 105, 90, 102, 122, 100, 120]
            tx0 = (lwidth - sum(widths)) / 2
            y = my - 18
            c.setFillColor(HexColor("#0A1A20"))
            c.setStrokeColor(accent)
            c.roundRect(tx0, y - 20, sum(widths), 20, 4, fill=1, stroke=1)
            x = tx0
            c.setFillColor(accent)
            c.setFont("Helvetica-Bold", 5.9)
            for label, w in zip(headers, widths):
                c.drawCentredString(x + w / 2, y - 13, label)
                x += w
            y -= 22
            for ridx, row in enumerate(rows):
                h = 18
                c.setFillColor(card if ridx % 2 == 0 else card2)
                c.setStrokeColor(line)
                c.rect(tx0, y - h, sum(widths), h, fill=1, stroke=1)
                values = [
                    str(row.get("period") or f"{row.get('year','-')}-{int(row.get('month') or 0):02d}"),
                    _money(row.get("starting_balance") or 0),
                    _maybe_pct(row.get("portfolio_return_pct")),
                    _money(row.get("gain_loss") or 0, signed=True),
                    _money(row.get("balance_before_withdrawal") or 0),
                    _money(row.get("withdrawal") or 0),
                    _money(row.get("ending_balance") or 0),
                ]
                x = tx0
                for cidx, (value, w) in enumerate(zip(values, widths)):
                    if cidx in (2, 3):
                        source = row.get("portfolio_return_pct") if cidx == 2 else row.get("gain_loss")
                        c.setFillColor(color_for_number(source))
                    elif cidx == 6:
                        c.setFillColor(cyan)
                    else:
                        c.setFillColor(text)
                    c.setFont("Helvetica-Bold" if cidx in (0, 2, 6) else "Helvetica", 5.8)
                    c.drawCentredString(x + w / 2, y - 11.8, str(value)[:23])
                    x += w
                y -= h

            depleted = str(_withdrawal_metric(result, "depleted_period", record.get("monthly_withdrawal_depleted_period") or "") or "").strip()
            c.setFillColor(negative if depleted else muted)
            c.setFont("Helvetica", 6.2)
            if depleted:
                note = f"Portfolio depleted during {depleted}; later monthly withdrawals cannot be funded."
            else:
                note = monthly_method_note
            c.drawString(24, 33, note[:170])
            draw_footer(lwidth, page_number, "Monthly cash-flow schedule applies return first, then withdrawal; taxes, fees and future returns are not modeled.")
            c.showPage()
            page_number += 1
        return page_number

    if bool(record.get("monthly_withdrawals_enabled")) and (mrb_schedule or mnr_schedule):
        c.setPageSize((lwidth, lheight))
        draw_page_background(lwidth, lheight, wash_height=92)
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 17)
        c.drawCentredString(lwidth / 2, lheight - 36, "MONTHLY WITHDRAWALS - STRATEGY COMPARISON")
        c.setFillColor(muted)
        c.setFont("Helvetica", 7.4)
        c.drawCentredString(
            lwidth / 2, lheight - 53,
            (
                "Same starting portfolio and monthly cash withdrawal. Actual adjusted month-end returns are used; Rebalanced resets weights monthly."
                if monthly_is_actual
                else "Same starting portfolio and monthly cash withdrawal. Legacy saved schedules use equivalent monthly rates; Rebalanced resets weights monthly."
            ),
        )

        mrb_end = _as_float_or_none(_withdrawal_metric(mrb_result, "ending_balance", 0)) or 0.0
        mnr_end = _as_float_or_none(_withdrawal_metric(mnr_result, "ending_balance", record.get("monthly_withdrawal_ending_balance") or 0)) or 0.0
        mrb_total = _as_float_or_none(_withdrawal_metric(mrb_result, "total_withdrawn", 0)) or 0.0
        mnr_total = _as_float_or_none(_withdrawal_metric(mnr_result, "total_withdrawn", record.get("monthly_withdrawal_total") or 0)) or 0.0
        difference = mrb_end - mnr_end
        monthly_withdrawal = _as_float_or_none(record.get("monthly_withdrawal_amount")) or 0.0
        annual_cash_target = monthly_withdrawal * 12.0
        mrb_positive = int(_withdrawal_metric(mrb_result, "positive_months", sum(1 for row in mrb_schedule if float(row.get("portfolio_return_pct") or 0) > 0)) or 0)
        mnr_positive = int(_withdrawal_metric(mnr_result, "positive_months", sum(1 for row in mnr_schedule if float(row.get("portfolio_return_pct") or 0) > 0)) or 0)
        mrb_months = int(_withdrawal_metric(mrb_result, "months_modeled", len(mrb_schedule)) or len(mrb_schedule))
        mnr_months = int(_withdrawal_metric(mnr_result, "months_modeled", len(mnr_schedule)) or len(mnr_schedule))
        summary_metrics = [
            ("MONTHLY WITHDRAWAL", _money(monthly_withdrawal), text),
            ("FULL-YEAR CASH TARGET", _money(annual_cash_target), text),
            ("REBALANCED REMAINING", _money(mrb_end), cyan),
            ("NOT REBALANCED REMAINING", _money(mnr_end), cyan),
            ("REMAINING DIFFERENCE", _money(difference, signed=True), color_for_number(difference)),
            ("POSITIVE MONTHS", f"RB {mrb_positive}/{mrb_months} | NR {mnr_positive}/{mnr_months}", positive),
        ]
        mx, my, mgap = 18, lheight - 122, 6
        mw = (lwidth - 36 - (len(summary_metrics) - 1) * mgap) / len(summary_metrics)
        for i, (label, value, value_color) in enumerate(summary_metrics):
            x = mx + i * (mw + mgap)
            c.setFillColor(card)
            c.setStrokeColor(border)
            c.roundRect(x, my, mw, 43, 5, fill=1, stroke=1)
            c.setFillColor(muted)
            c.setFont("Helvetica-Bold", 5.8)
            c.drawCentredString(x + mw / 2, my + 27, label)
            c.setFillColor(value_color)
            c.setFont("Helvetica-Bold", 6.8 if label == "POSITIVE MONTHS" else 8.7)
            c.drawCentredString(x + mw / 2, my + 10, str(value)[:28])

        # v5.9.59: Year-level cash-flow reconciliation. The old page displayed
        # December's monthly return next to a full year-end balance, which could
        # be mistaken for the annual return. Aggregate the actual Jan-Dec monthly
        # returns and cash withdrawals instead.
        def _year_summary(schedule):
            grouped = {}
            for row in schedule:
                year = str(row.get("year") or "").strip()
                if not year:
                    continue
                grouped.setdefault(year, []).append(row)
            out = {}
            for year, rows in grouped.items():
                rows = sorted(rows, key=lambda item: int(item.get("month") or 0))
                factor = 1.0
                valid_returns = 0
                for row in rows:
                    pct = _as_float_or_none(row.get("portfolio_return_pct"))
                    if pct is None:
                        continue
                    factor *= 1.0 + pct / 100.0
                    valid_returns += 1
                start_balance = _as_float_or_none(rows[0].get("starting_balance")) if rows else None
                ending_balance = _as_float_or_none(rows[-1].get("ending_balance")) if rows else None
                withdrawn = sum((_as_float_or_none(row.get("withdrawal")) or 0.0) for row in rows)
                year_return = ((factor - 1.0) * 100.0) if valid_returns else None
                out[year] = {
                    "start": start_balance,
                    "return_pct": year_return,
                    "withdrawn": withdrawn,
                    "ending": ending_balance,
                    "end_plus_withdrawn": (ending_balance + withdrawn) if ending_balance is not None else None,
                    "months": len(rows),
                }
            return out

        mrb_years = _year_summary(mrb_schedule)
        mnr_years = _year_summary(mnr_schedule)
        ordered_years = sorted(set(mrb_years) | set(mnr_years))

        # Two short notes explain why year-end balance alone cannot be read as the
        # investment return when cash is removed every month.
        c.setFillColor(muted)
        c.setFont("Helvetica", 6.15)
        note_y = my - 13
        c.drawString(
            22, note_y,
            "YEAR RETURN = compounded Jan-Dec portfolio returns before withdrawals. YEAR WITHDRAWN = actual cash paid during that calendar year."
        )
        c.drawString(
            22, note_y - 10,
            "END + WITHDRAWN = Dec. 31 remaining balance + that year's withdrawals. It reconciles cash flow; it is not the formula used for YEAR RETURN."
        )

        headers = [
            "YEAR", "START BALANCE RB / NR", "YEAR RETURN RB / NR", "YEAR WITHDRAWN RB / NR",
            "RB YEAR-END", "RB END + WITHDRAWN", "NR YEAR-END", "NR END + WITHDRAWN", "TOTAL VALUE DIFF"
        ]
        widths = [43, 104, 92, 100, 88, 94, 88, 94, 84]
        tx0 = (lwidth - sum(widths)) / 2
        y = note_y - 18
        c.setFillColor(HexColor("#0A1A20"))
        c.setStrokeColor(accent)
        c.roundRect(tx0, y - 25, sum(widths), 25, 4, fill=1, stroke=1)
        x = tx0
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 4.8)
        for label, w in zip(headers, widths):
            c.drawCentredString(x + w / 2, y - 15.5, label)
            x += w
        y -= 27
        for ridx, year in enumerate(ordered_years[:20]):
            rb = mrb_years.get(year, {})
            nr = mnr_years.get(year, {})
            rb_start = _as_float_or_none(rb.get("start"))
            nr_start = _as_float_or_none(nr.get("start"))
            rb_ret = _as_float_or_none(rb.get("return_pct"))
            nr_ret = _as_float_or_none(nr.get("return_pct"))
            rb_withdrawn = _as_float_or_none(rb.get("withdrawn")) or 0.0
            nr_withdrawn = _as_float_or_none(nr.get("withdrawn")) or 0.0
            rb_bal = _as_float_or_none(rb.get("ending"))
            nr_bal = _as_float_or_none(nr.get("ending"))
            rb_total_value = _as_float_or_none(rb.get("end_plus_withdrawn"))
            nr_total_value = _as_float_or_none(nr.get("end_plus_withdrawn"))
            total_diff = (
                rb_total_value - nr_total_value
                if rb_total_value is not None and nr_total_value is not None else None
            )

            def _pair_money(left, right):
                left_text = _money(left) if left is not None else "-"
                right_text = _money(right) if right is not None else "-"
                return f"{left_text} / {right_text}"

            def _pair_pct(left, right, left_months, right_months):
                left_text = _maybe_pct(left) if left is not None else "-"
                right_text = _maybe_pct(right) if right is not None else "-"
                if left_months and left_months != 12:
                    left_text += f" ({left_months}m)"
                if right_months and right_months != 12:
                    right_text += f" ({right_months}m)"
                return f"{left_text} / {right_text}"

            h = 20
            c.setFillColor(card if ridx % 2 == 0 else card2)
            c.setStrokeColor(line)
            c.rect(tx0, y - h, sum(widths), h, fill=1, stroke=1)
            values = [
                year,
                _pair_money(rb_start, nr_start),
                _pair_pct(rb_ret, nr_ret, int(rb.get("months") or 0), int(nr.get("months") or 0)),
                _pair_money(rb_withdrawn, nr_withdrawn),
                _money(rb_bal) if rb_bal is not None else "-",
                _money(rb_total_value) if rb_total_value is not None else "-",
                _money(nr_bal) if nr_bal is not None else "-",
                _money(nr_total_value) if nr_total_value is not None else "-",
                _money(total_diff, signed=True) if total_diff is not None else "-",
            ]
            x = tx0
            for idx, (value, w) in enumerate(zip(values, widths)):
                if idx == 2:
                    # When both returns share one cell, use neutral text rather than
                    # implying that one strategy's sign represents the other.
                    c.setFillColor(text)
                elif idx == 8:
                    c.setFillColor(color_for_number(total_diff))
                elif idx in (4, 5, 6, 7):
                    c.setFillColor(cyan)
                else:
                    c.setFillColor(text)
                c.setFont("Helvetica-Bold" if idx in (0, 4, 5, 6, 7, 8) else "Helvetica", 5.15)
                c.drawCentredString(x + w / 2, y - 13.0, str(value)[:31])
                x += w
            y -= h

        c.setFillColor(muted)
        c.setFont("Helvetica", 5.9)
        c.drawString(
            22, 34,
            f"Total withdrawn over modeled period - RB {_money(mrb_total)} | NR {_money(mnr_total)}. Remaining + cumulative withdrawals: RB {_money(mrb_end + mrb_total)} | NR {_money(mnr_end + mnr_total)}."
        )
        draw_footer(
            lwidth,
            page_no,
            (
                "Monthly returns shown here are actual adjusted month-end returns from Yahoo/yfinance daily history."
                if monthly_is_actual
                else "Legacy saved simulation: monthly returns were equivalent rates derived from annual returns."
            ),
        )
        c.showPage()
        page_no += 1

        if mrb_schedule:
            page_no = _draw_monthly_withdrawal_detail_pages(
                "MONTHLY WITHDRAWAL SCHEDULE - REBALANCED",
                "Return applied each month, then withdrawal, then target weights restored.",
                mrb_result, mrb_schedule, page_no,
            )
        if mnr_schedule:
            page_no = _draw_monthly_withdrawal_detail_pages(
                "MONTHLY WITHDRAWAL SCHEDULE - NOT REBALANCED",
                "Return applied each month, then proportional withdrawal; holdings retain drifted weights.",
                mnr_result, mnr_schedule, page_no,
            )

    # ------------------------------------------------------------------
    # Remaining pages: individual allocation/result rows, preserving the prior layout.
    # ------------------------------------------------------------------
    width, height = A4
    rows_per_page = 12

    def draw_allocation_title(page_no: int):
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 17)
        c.drawCentredString(width / 2, height - 43, "PORTFOLIO ALLOCATION RESULTS")
        c.setFillColor(muted)
        c.setFont("Helvetica", 8)
        c.drawCentredString(width / 2, height - 59, f"{record.get('name') or record.get('id')}  |  Instrument-level simulation detail")

    def table_header(y):
        tx0 = 24
        col_w = [110, 78, 84, 84, 108, 82]
        headers = ["SYMBOL / TYPE", "ALLOCATION", "START", "END", "PROFIT / LOSS", "RETURN"]
        c.setFillColor(HexColor("#0A1A20"))
        c.setStrokeColor(accent)
        c.setLineWidth(0.8)
        c.roundRect(tx0, y - 28, sum(col_w), 28, 5, fill=1, stroke=1)
        xpos = tx0
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 7.2)
        for header, cw in zip(headers, col_w):
            c.drawCentredString(xpos + cw / 2, y - 18, header)
            xpos += cw
        return tx0, col_w, y - 28

    def draw_row(y, item, row_idx):
        tx0 = 24
        col_w = [110, 78, 84, 84, 108, 82]
        h = 46
        c.setFillColor(card if row_idx % 2 == 0 else card2)
        c.setStrokeColor(line)
        c.setLineWidth(0.5)
        c.roundRect(tx0, y - h, sum(col_w), h - 2, 4, fill=1, stroke=1)

        symbol = str(item.get("symbol") or "-")
        itype = str(item.get("type") or "")
        sector = str(item.get("sector") or "")
        weight = float(item.get("weight") or 0)
        start = float(item.get("allocated") or 0)
        unavailable = bool(item.get("unavailable"))
        end = float(item.get("ending_value") or 0) if not unavailable else 0
        profit = float(item.get("profit") or 0) if not unavailable else 0
        ret = float(item.get("return_pct") or 0) if not unavailable else 0

        xpos = tx0
        c.setFillColor(text)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(xpos + 8, y - 17, symbol[:15])
        c.setFillColor(cyan)
        c.setFont("Helvetica", 6.7)
        c.drawString(xpos + 8, y - 30, itype[:10])
        if sector:
            c.setFillColor(muted)
            c.setFont("Helvetica", 5.9)
            c.drawRightString(xpos + col_w[0] - 7, y - 30, sector[:22])
        xpos += col_w[0]

        c.setFillColor(text)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(xpos + col_w[1] / 2, y - 22, f"{weight:.1f}%")
        xpos += col_w[1]
        c.setFont("Helvetica-Bold", 8.3)
        c.drawCentredString(xpos + col_w[2] / 2, y - 22, _money(start))
        xpos += col_w[2]
        c.drawCentredString(xpos + col_w[3] / 2, y - 22, "N/A" if unavailable else _money(end))
        xpos += col_w[3]
        if unavailable:
            c.setFillColor(muted)
            c.drawCentredString(xpos + col_w[4] / 2, y - 22, "Unavailable")
        else:
            c.setFillColor(positive if profit >= 0 else negative)
            c.setFont("Helvetica-Bold", 8.7)
            c.drawCentredString(xpos + col_w[4] / 2, y - 22, _money(profit, signed=True))
        xpos += col_w[4]
        if unavailable:
            c.setFillColor(muted)
            c.drawCentredString(xpos + col_w[5] / 2, y - 22, "N/A")
        else:
            c.setFillColor(positive if ret >= 0 else negative)
            c.drawCentredString(xpos + col_w[5] / 2, y - 22, _pct(ret))
        return y - h

    idx = 0
    while idx < max(1, len(instruments)):
        c.setPageSize(A4)
        draw_page_background(width, height, wash_height=82)
        draw_allocation_title(page_no)
        _, _, row_y = table_header(height - 88)
        if not instruments:
            c.setFillColor(muted)
            c.setFont("Helvetica", 10)
            c.drawCentredString(width / 2, row_y - 35, "No instrument rows were saved.")
            idx = 1
        else:
            for local_i, item in enumerate(instruments[idx:idx + rows_per_page]):
                row_y = draw_row(row_y, item, idx + local_i)
            idx += rows_per_page
        draw_footer(width, page_no)
        c.showPage()
        page_no += 1

    # Supplemental individual-instrument analytics tables.
    if instruments:
        lwidth, lheight = landscape(A4)

        def supplemental_background(title: str, subtitle: str = ""):
            c.setPageSize(landscape(A4))
            c.setFillColor(bg)
            c.rect(0, 0, lwidth, lheight, fill=1, stroke=0)
            c.setFillColor(HexColor("#081E25"))
            c.rect(0, lheight - 78, lwidth, 78, fill=1, stroke=0)
            c.setFillColor(accent)
            c.setFont("Helvetica-Bold", 16)
            c.drawString(24, lheight - 35, title)
            c.setFillColor(muted)
            c.setFont("Helvetica", 7.5)
            if subtitle:
                c.drawString(24, lheight - 53, subtitle[:155])

        def draw_analytics_table(items: list[dict], page_number: int):
            supplemental_background(
                "PORTFOLIO INFORMATION TABLE",
                "Saved instrument analytics. Positive months use actual adjusted month-end returns; 10Y CAGR uses completed calendar-year returns.",
            )
            headers = [
                "INDUSTRY", "STOCK", "ALLOCATION", "10Y CAGR", "POS YEARS", "POS MONTHS",
                "HISTORY CHECK", "WORST YEAR", "BEST YEAR", "REG. YIELD", "EST. ANNUAL DIV."
            ]
            widths = [118, 48, 70, 58, 58, 68, 72, 82, 82, 62, 78]
            tx0, y = 22, lheight - 92
            total_w = sum(widths)
            c.setFillColor(HexColor("#0A1A20"))
            c.setStrokeColor(accent)
            c.roundRect(tx0, y - 24, total_w, 24, 4, fill=1, stroke=1)
            x = tx0
            c.setFillColor(accent)
            c.setFont("Helvetica-Bold", 6.2)
            for label, w in zip(headers, widths):
                c.drawCentredString(x + w / 2, y - 15.5, label)
                x += w
            y -= 26
            for ridx, item in enumerate(items):
                h = 40
                c.setFillColor(card if ridx % 2 == 0 else card2)
                c.setStrokeColor(line)
                c.roundRect(tx0, y - h, total_w, h - 2, 3, fill=1, stroke=1)
                industry = str(item.get("industry") or item.get("sector") or "-")[:30]
                stock = str(item.get("symbol") or "-")[:10]
                allocation = f"{float(item.get('weight') or 0):.1f}% / {_money(item.get('allocated') or 0)}"
                cagr = _maybe_pct(item.get("cagr_10y_pct"))
                pos = f"{int(item.get('positive_years') or 0)}/{int(item.get('available_years') or 0)}"
                pos_months = (
                    f"{int(item.get('positive_months'))}/{int(item.get('available_months'))}"
                    if item.get("positive_months") is not None and item.get("available_months") is not None
                    else "-"
                )
                verification = str(item.get("history_verification") or "Pending")
                verification_coverage = str(item.get("verification_coverage") or "").strip()
                verification_text = verification + (f" {verification_coverage}" if verification_coverage else "")
                max_diff = item.get("max_verification_diff_pp")
                try:
                    if max_diff is not None:
                        verification_text += f" Δ{float(max_diff):.2f}"
                except Exception:
                    pass
                worst = _best_worst(item.get("worst_year"), item.get("worst_year_pct"))
                best = _best_worst(item.get("best_year"), item.get("best_year_pct"))
                regular_yield = _yield_pct(item.get("regular_yield_pct"))
                est_div = _money(item.get("est_annual_dividend") or 0) if item.get("est_annual_dividend") is not None else "-"
                values = [industry, stock, allocation, cagr, pos, pos_months, verification_text, worst, best, regular_yield, est_div]
                x = tx0
                for col_idx, (value, w) in enumerate(zip(values, widths)):
                    c.setFillColor(text if col_idx not in (3, 7, 8) else cyan)
                    c.setFont("Helvetica-Bold" if col_idx in (1, 2, 3, 8) else "Helvetica", 6.4)
                    if col_idx == 0:
                        c.drawString(x + 5, y - 23, str(value)[:31])
                    else:
                        c.drawCentredString(x + w / 2, y - 23, str(value)[:24])
                    x += w
                y -= h
            c.setFillColor(muted)
            c.setFont("Helvetica", 6.5)
            c.drawString(24, 18, "History Check = Yahoo annual-return calculation cross-checked against independent Stooq bulk historical Close; Review means a difference above 0.25pp.")
            c.drawRightString(lwidth - 24, 18, f"Page {page_number}")
            c.showPage()

        rows_per_analytics_page = 10
        for start in range(0, len(instruments), rows_per_analytics_page):
            draw_analytics_table(instruments[start:start + rows_per_analytics_page], page_no)
            page_no += 1

        # One wide individual performance matrix containing every card timeframe saved with the simulation.
        period_order = []
        for item in instruments:
            for key in (item.get("performance") or {}).keys():
                if key not in period_order:
                    period_order.append(key)
        preferred = ["1D", "1M", "3M", "6M", "YTD"]
        years = sorted([k for k in period_order if str(k).isdigit() and len(str(k)) == 4], reverse=True)
        perf_column_groups = []
        recent = [k for k in preferred if k in period_order] + years[:10]
        if recent:
            perf_column_groups.append(recent)
        if years[10:20]:
            perf_column_groups.append(years[10:20])
        if years[20:]:
            for i in range(20, len(years), 12):
                perf_column_groups.append(years[i:i + 12])

        rows_per_perf_page = 10
        for group_no, perf_columns in enumerate(perf_column_groups, start=1):
            for start in range(0, len(instruments), rows_per_perf_page):
                items = instruments[start:start + rows_per_perf_page]
                supplemental_background(
                    f"TIMEFRAME PERFORMANCE TABLE {group_no}/{len(perf_column_groups)}",
                    "Saved return percentages for each simulation instrument. Calendar-year columns are actual completed-year returns, not CAGR.",
                )
                tx0, y = 22, lheight - 92
                stock_w = 58
                available_w = lwidth - 44 - stock_w
                perf_w = available_w / max(1, len(perf_columns))
                widths = [stock_w] + [perf_w] * len(perf_columns)
                headers = ["STOCK"] + perf_columns
                total_w = sum(widths)
                c.setFillColor(HexColor("#0A1A20"))
                c.setStrokeColor(accent)
                c.roundRect(tx0, y - 24, total_w, 24, 4, fill=1, stroke=1)
                x = tx0
                c.setFillColor(accent)
                c.setFont("Helvetica-Bold", 6.0)
                for label, w in zip(headers, widths):
                    c.drawCentredString(x + w / 2, y - 15.5, str(label))
                    x += w
                y -= 26
                for ridx, item in enumerate(items):
                    h = 38
                    c.setFillColor(card if ridx % 2 == 0 else card2)
                    c.setStrokeColor(line)
                    c.roundRect(tx0, y - h, total_w, h - 2, 3, fill=1, stroke=1)
                    x = tx0
                    c.setFillColor(text)
                    c.setFont("Helvetica-Bold", 7.2)
                    c.drawCentredString(x + stock_w / 2, y - 22, str(item.get("symbol") or "-")[:10])
                    x += stock_w
                    performance = item.get("performance") or {}
                    for metric, w in zip(perf_columns, widths[1:]):
                        value = _as_float_or_none(performance.get(metric))
                        c.setFillColor(color_for_number(value))
                        c.setFont("Helvetica-Bold", 5.9)
                        c.drawCentredString(x + w / 2, y - 22, _maybe_pct(value))
                        x += w
                    y -= h
                c.setFillColor(muted)
                c.setFont("Helvetica", 6.5)
                c.drawString(24, 18, "Timeframe values are the exact MarketScope return fields saved when this portfolio simulation was created.")
                c.drawRightString(lwidth - 24, 18, f"Page {page_no}")
                c.showPage()
                page_no += 1

    c.save()
    return buf.getvalue()

def add_simulation(records: Iterable[dict], record: dict) -> list[dict]:
    out = [dict(x) for x in records if isinstance(x, dict) and x.get("id") != record.get("id")]
    out.append(dict(record))
    return _normalize_records(out)


def delete_simulation(records: Iterable[dict], simulation_id_value: str) -> list[dict]:
    return _normalize_records([x for x in records if isinstance(x, dict) and x.get("id") != simulation_id_value])
