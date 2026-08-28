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
        body = {
            "message": message,
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
    # Landscape is intentional; 20 annual returns are split into two legible timeframe bands.
    # ------------------------------------------------------------------
    lwidth, lheight = landscape(A4)
    c.setPageSize((lwidth, lheight))
    draw_page_background(lwidth, lheight, wash_height=112)

    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(lwidth / 2, lheight - 36, "PORTFOLIO SPLIT SIMULATOR")
    c.setFillColor(muted)
    c.setFont("Helvetica", 8.5)
    meta = (
        f"{record.get('name') or record.get('id')}  |  Period {record.get('period', 'YTD')}  |  "
        f"{record.get('allocation_mode', 'Equal split')}  |  {record.get('created_at_display_et', '')}"
    )
    c.drawCentredString(lwidth / 2, lheight - 55, meta[:165])

    # Four main portfolio result cards.
    labels = [
        ("TOTAL INVESTED", _money(record.get("total_invested", 0)), text),
        ("EST. ENDING VALUE", _money(record.get("ending_value", 0)), text),
        ("PROFIT / LOSS", _money(record.get("profit_loss", 0), signed=True), color_for_number(record.get("profit_loss"))),
        ("TOTAL RETURN", _pct(record.get("total_return", 0)), color_for_number(record.get("total_return"))),
    ]
    x0 = 24
    gap = 10
    box_w = (lwidth - 2 * x0 - 3 * gap) / 4
    box_y = lheight - 128
    box_h = 54
    for i, (label, value, value_color) in enumerate(labels):
        x = x0 + i * (box_w + gap)
        c.setFillColor(card)
        c.setStrokeColor(border)
        c.setLineWidth(0.8)
        c.roundRect(x, box_y, box_w, box_h, 7, fill=1, stroke=1)
        c.setFillColor(muted)
        c.setFont("Helvetica-Bold", 7.6)
        c.drawCentredString(x + box_w / 2, box_y + 36, label)
        c.setFillColor(value_color)
        c.setFont("Helvetica-Bold", 13.5)
        c.drawCentredString(x + box_w / 2, box_y + 15, value)

    # Combined portfolio performance statistics.
    section_y = box_y - 28
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(24, section_y, "COMBINED PORTFOLIO PERFORMANCE")
    c.setFillColor(muted)
    c.setFont("Helvetica", 7.0)
    c.drawRightString(lwidth - 24, section_y, "Allocation-weighted combination of all instruments")

    pos_years = f"{int(combined.get('positive_years') or 0)}/{int(combined.get('available_years') or 0)}"
    stat_cells = [
        ("10Y CAGR", _maybe_pct(combined.get("cagr_10y_pct")), color_for_number(combined.get("cagr_10y_pct"))),
        ("POS YEARS", pos_years, text),
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
        value_font = 9.2 if label in {"WORST YEAR", "BEST YEAR"} else 11.2
        c.setFont("Helvetica-Bold", value_font)
        c.drawCentredString(x + stat_w / 2, stat_y + 13, str(value)[:22])

    # Combined timeframe table with the exact requested fields.
    timeframe_title_y = stat_y - 28
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(24, timeframe_title_y, "COMBINED TIMEFRAME PERFORMANCE")
    c.setFillColor(muted)
    c.setFont("Helvetica", 7.0)
    c.drawRightString(lwidth - 24, timeframe_title_y, "Static allocation-weighted return for each saved timeframe")

    combined_perf = combined.get("performance") or {}
    preferred_timeframes = ["1D", "1M", "3M", "6M", "YTD"]
    saved_years = sorted(
        [str(key) for key in combined_perf if str(key).isdigit() and len(str(key)) == 4],
        reverse=True,
    )
    timeframe_groups = [preferred_timeframes + saved_years[:10]]
    if saved_years[10:20]:
        timeframe_groups.append(saved_years[10:20])

    table_x = 24
    table_w = lwidth - 48
    header_h = 24
    value_h = 34

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
            c.setFont("Helvetica-Bold", 7.2)
            c.drawCentredString(x + cell_w / 2, header_y + 8.5, label)

        values_y = header_y - value_h - 2
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
            c.setFont("Helvetica-Bold", 7.8)
            c.drawCentredString(x + cell_w / 2, values_y + 12.5, _maybe_pct(value))
        return values_y

    first_values_y = draw_timeframe_band(timeframe_groups[0], timeframe_title_y - 28)
    values_y = first_values_y
    if len(timeframe_groups) > 1:
        c.setFillColor(muted)
        c.setFont("Helvetica-Bold", 6.7)
        c.drawString(24, first_values_y - 15, "OLDER COMPLETED CALENDAR YEARS")
        values_y = draw_timeframe_band(timeframe_groups[1], first_values_y - 46)

    # First-page instrument identity + analyst/price-target snapshot.
    # This is intentionally compact so the combined portfolio analytics/timeframes stay on page 1.
    instrument_title_y = values_y - 18
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 8.7)
    c.drawString(24, instrument_title_y, "PORTFOLIO INSTRUMENT / ANALYST SNAPSHOT")
    c.setFillColor(muted)
    c.setFont("Helvetica", 6.1)
    c.drawRightString(lwidth - 24, instrument_title_y, "Saved analyst rating and Low / Average / High price targets")

    first_page_max_rows = 8
    first_page_items = instruments[:first_page_max_rows]
    info_headers = ["SYMBOL", "NAME", "TYPE", "SECTOR", "ANALYST RATING", "TARGET LOW", "TARGET AVG", "TARGET HIGH"]
    info_widths = [49, 158, 42, 118, 82, 72, 72, 72]
    info_x = 24
    info_y = instrument_title_y - 18
    info_total_w = sum(info_widths)
    header_row_h = 15
    row_h = 14
    c.setFillColor(HexColor("#0A1A20"))
    c.setStrokeColor(accent)
    c.setLineWidth(0.65)
    c.roundRect(info_x, info_y - header_row_h, info_total_w, header_row_h, 3, fill=1, stroke=1)
    xpos = info_x
    c.setFillColor(accent)
    c.setFont("Helvetica-Bold", 5.7)
    for label, cw in zip(info_headers, info_widths):
        c.drawCentredString(xpos + cw / 2, info_y - 10.1, label)
        xpos += cw
    info_y -= header_row_h + 1

    def _target_text(value):
        numeric = _as_float_or_none(value)
        return _money(numeric) if numeric is not None and numeric > 0 else "-"

    for ridx, item in enumerate(first_page_items):
        c.setFillColor(card if ridx % 2 == 0 else card2)
        c.setStrokeColor(line)
        c.setLineWidth(0.35)
        c.rect(info_x, info_y - row_h, info_total_w, row_h, fill=1, stroke=1)
        values = [
            str(item.get("symbol") or "-")[:10],
            str(item.get("name") or item.get("symbol") or "-")[:31],
            str(item.get("type") or "-")[:8],
            str(item.get("sector") or "-")[:23],
            str(item.get("analyst_rating") or "Not Rated")[:16],
            _target_text(item.get("price_target_low")),
            _target_text(item.get("price_target_average")),
            _target_text(item.get("price_target_high")),
        ]
        xpos = info_x
        for col_idx, (value, cw) in enumerate(zip(values, info_widths)):
            c.setFillColor(text if col_idx not in (4, 5, 6, 7) else (cyan if col_idx in (5, 6, 7) else muted))
            c.setFont("Helvetica-Bold" if col_idx in (0, 4, 6) else "Helvetica", 5.6)
            if col_idx in (1, 3):
                c.drawString(xpos + 3, info_y - 9.4, str(value))
            else:
                c.drawCentredString(xpos + cw / 2, info_y - 9.4, str(value))
            xpos += cw
        info_y -= row_h

    if len(instruments) > first_page_max_rows:
        c.setFillColor(muted)
        c.setFont("Helvetica", 5.8)
        c.drawRightString(
            info_x + info_total_w,
            max(28, info_y - 7),
            f"Showing {first_page_max_rows} of {len(instruments)} instruments on page 1; complete instrument detail follows.",
        )

    draw_footer(
        lwidth,
        1,
        "Combined returns are allocation-weighted historical simulations. Analyst ratings/targets are saved snapshot values; not investment advice.",
    )
    c.showPage()

    # ------------------------------------------------------------------
    # Pages 2+: individual allocation/result rows, preserving the prior layout.
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

    page_no = 2
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
                "Saved instrument analytics. 10Y CAGR uses 10 completed calendar-year returns when available; dividend estimate uses saved trailing yield.",
            )
            headers = [
                "INDUSTRY", "STOCK", "ALLOCATION", "10Y CAGR", "POS YEARS",
                "WORST YEAR", "BEST YEAR", "REG. YIELD", "EST. ANNUAL DIV."
            ]
            widths = [135, 54, 78, 66, 67, 93, 93, 70, 92]
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
                worst = _best_worst(item.get("worst_year"), item.get("worst_year_pct"))
                best = _best_worst(item.get("best_year"), item.get("best_year_pct"))
                regular_yield = _yield_pct(item.get("regular_yield_pct"))
                est_div = _money(item.get("est_annual_dividend") or 0) if item.get("est_annual_dividend") is not None else "-"
                values = [industry, stock, allocation, cagr, pos, worst, best, regular_yield, est_div]
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
            c.drawString(24, 18, "Regular yield is trailing/indicative and may change. Est. annual dividend = saved allocation x saved regular yield; no reinvestment/tax assumption.")
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
