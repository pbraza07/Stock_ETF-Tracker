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


def build_portfolio_simulation_pdf(record: dict) -> bytes:
    """Build a polished PDF modeled on the MarketScope portfolio simulator reference layout."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

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
    rows_per_first = 9
    rows_per_next = 12

    def draw_background():
        c.setFillColor(bg)
        c.rect(0, 0, width, height, fill=1, stroke=0)
        # subtle top accent wash
        c.setFillColor(HexColor("#081E25"))
        c.rect(0, height - 155, width, 155, fill=1, stroke=0)

    def draw_title(continued: bool = False):
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 19 if not continued else 16)
        title = "PORTFOLIO SPLIT SIMULATOR" + (" - CONTINUED" if continued else "")
        c.drawCentredString(width / 2, height - 48, title)
        c.setFillColor(muted)
        c.setFont("Helvetica", 8.5)
        meta = (
            f"{record.get('name') or record.get('id')}  |  Period {record.get('period', 'YTD')}  |  "
            f"{record.get('allocation_mode', 'Equal split')}  |  {record.get('created_at_display_et', '')}"
        )
        c.drawCentredString(width / 2, height - 66, meta[:135])

    def draw_summary():
        labels = [
            ("TOTAL INVESTED", _money(record.get("total_invested", 0)), text),
            ("EST. ENDING VALUE", _money(record.get("ending_value", 0)), text),
            ("PROFIT / LOSS", _money(record.get("profit_loss", 0), signed=True), positive if float(record.get("profit_loss", 0) or 0) >= 0 else negative),
            ("TOTAL RETURN", _pct(record.get("total_return", 0)), positive if float(record.get("total_return", 0) or 0) >= 0 else negative),
        ]
        x0 = 25
        gap = 8
        box_w = (width - 2 * x0 - 3 * gap) / 4
        y = height - 142
        h = 58
        for i, (label, value, value_color) in enumerate(labels):
            x = x0 + i * (box_w + gap)
            c.setFillColor(card)
            c.setStrokeColor(border)
            c.setLineWidth(0.8)
            c.roundRect(x, y, box_w, h, 7, fill=1, stroke=1)
            c.setFillColor(muted)
            c.setFont("Helvetica-Bold", 7.2)
            c.drawCentredString(x + box_w / 2, y + 38, label)
            c.setFillColor(value_color)
            c.setFont("Helvetica-Bold", 13.5)
            c.drawCentredString(x + box_w / 2, y + 17, value)

    def table_header(y):
        x0 = 24
        col_w = [110, 78, 84, 84, 108, 82]
        headers = ["SYMBOL / TYPE", "ALLOCATION", "START", "END", "PROFIT / LOSS", "RETURN"]
        c.setFillColor(HexColor("#0A1A20"))
        c.setStrokeColor(accent)
        c.setLineWidth(0.8)
        c.roundRect(x0, y - 28, sum(col_w), 28, 5, fill=1, stroke=1)
        xpos = x0
        c.setFillColor(accent)
        c.setFont("Helvetica-Bold", 7.2)
        for header, cw in zip(headers, col_w):
            c.drawCentredString(xpos + cw / 2, y - 18, header)
            xpos += cw
        return x0, col_w, y - 28

    def draw_row(y, item, row_idx):
        x0 = 24
        col_w = [110, 78, 84, 84, 108, 82]
        h = 46
        c.setFillColor(card if row_idx % 2 == 0 else card2)
        c.setStrokeColor(line)
        c.setLineWidth(0.5)
        c.roundRect(x0, y - h, sum(col_w), h - 2, 4, fill=1, stroke=1)

        symbol = str(item.get("symbol") or "-")
        itype = str(item.get("type") or "")
        sector = str(item.get("sector") or "")
        weight = float(item.get("weight") or 0)
        start = float(item.get("allocated") or 0)
        unavailable = bool(item.get("unavailable"))
        end = float(item.get("ending_value") or 0) if not unavailable else 0
        profit = float(item.get("profit") or 0) if not unavailable else 0
        ret = float(item.get("return_pct") or 0) if not unavailable else 0

        xpos = x0
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

    def draw_footer(page_no: int):
        c.setFillColor(muted)
        c.setFont("Helvetica", 6.8)
        note = "Historical simulation based on MarketScope saved adjusted-return data. Not a forecast or investment recommendation."
        c.drawString(26, 22, note)
        c.drawRightString(width - 26, 22, f"Page {page_no}")

    page_no = 1
    idx = 0
    while idx < max(1, len(instruments)):
        draw_background()
        draw_title(continued=page_no > 1)
        if page_no == 1:
            draw_summary()
            header_y = height - 182
            capacity = rows_per_first
        else:
            header_y = height - 96
            capacity = rows_per_next
        _, _, row_y = table_header(header_y)
        if not instruments:
            c.setFillColor(muted)
            c.setFont("Helvetica", 10)
            c.drawCentredString(width / 2, row_y - 35, "No instrument rows were saved.")
            idx = 1
        else:
            for local_i, item in enumerate(instruments[idx:idx + capacity]):
                row_y = draw_row(row_y, item, idx + local_i)
            idx += capacity
        draw_footer(page_no)
        c.showPage()
        page_no += 1


    # v5.9.6 supplemental saved information tables.
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

        def draw_analytics_table(items: list[dict], start_index: int, page_number: int):
            supplemental_background(
                "PORTFOLIO INFORMATION TABLE",
                "Saved instrument analytics. 10Y CAGR uses 10 completed calendar-year returns when available; dividend estimate uses saved trailing yield.",
            )
            headers = [
                "INDUSTRY", "STOCK", "ALLOCATION", "10Y CAGR", "POS YEARS",
                "WORST YEAR", "BEST YEAR", "REG. YIELD", "EST. ANNUAL DIV."
            ]
            widths = [135, 54, 78, 66, 67, 93, 93, 70, 92]
            x0, y = 22, lheight - 92
            total_w = sum(widths)
            c.setFillColor(HexColor("#0A1A20"))
            c.setStrokeColor(accent)
            c.roundRect(x0, y - 24, total_w, 24, 4, fill=1, stroke=1)
            x = x0
            c.setFillColor(accent)
            c.setFont("Helvetica-Bold", 6.2)
            for label, w in zip(headers, widths):
                c.drawCentredString(x + w / 2, y - 15.5, label)
                x += w
            y -= 26
            for idx, item in enumerate(items):
                h = 40
                c.setFillColor(card if idx % 2 == 0 else card2)
                c.setStrokeColor(line)
                c.roundRect(x0, y - h, total_w, h - 2, 3, fill=1, stroke=1)
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
                x = x0
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
            draw_analytics_table(instruments[start:start + rows_per_analytics_page], start, page_no)
            page_no += 1

        # One wide performance matrix containing every card timeframe saved with the simulation.
        period_order = []
        for item in instruments:
            for key in (item.get("performance") or {}).keys():
                if key not in period_order:
                    period_order.append(key)
        preferred = ["1D", "1M", "3M", "6M", "YTD"]
        years = sorted([k for k in period_order if str(k).isdigit() and len(str(k)) == 4], reverse=True)
        perf_columns = [k for k in preferred if k in period_order] + years
        if perf_columns:
            rows_per_perf_page = 10
            for start in range(0, len(instruments), rows_per_perf_page):
                items = instruments[start:start + rows_per_perf_page]
                supplemental_background(
                    "TIMEFRAME PERFORMANCE TABLE",
                    "Saved return percentages for the same simulation instruments. Calendar-year columns are actual completed-year returns, not CAGR.",
                )
                x0, y = 22, lheight - 92
                stock_w = 58
                available_w = lwidth - 44 - stock_w
                perf_w = available_w / max(1, len(perf_columns))
                widths = [stock_w] + [perf_w] * len(perf_columns)
                headers = ["STOCK"] + perf_columns
                total_w = sum(widths)
                c.setFillColor(HexColor("#0A1A20"))
                c.setStrokeColor(accent)
                c.roundRect(x0, y - 24, total_w, 24, 4, fill=1, stroke=1)
                x = x0
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
                    c.roundRect(x0, y - h, total_w, h - 2, 3, fill=1, stroke=1)
                    x = x0
                    c.setFillColor(text)
                    c.setFont("Helvetica-Bold", 7.2)
                    c.drawCentredString(x + stock_w / 2, y - 22, str(item.get("symbol") or "-")[:10])
                    x += stock_w
                    performance = item.get("performance") or {}
                    for metric, w in zip(perf_columns, widths[1:]):
                        value = performance.get(metric)
                        try:
                            numeric = float(value) if value is not None else None
                        except (TypeError, ValueError):
                            numeric = None
                        c.setFillColor(positive if numeric is not None and numeric > 0 else (negative if numeric is not None and numeric < 0 else muted))
                        c.setFont("Helvetica-Bold", 5.9)
                        c.drawCentredString(x + w / 2, y - 22, _maybe_pct(numeric))
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
