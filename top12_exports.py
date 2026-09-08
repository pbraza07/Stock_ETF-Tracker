"""Readable ranking reports with complete evidence workbook."""

from io import BytesIO
from xml.sax.saxutils import escape
import json
import math
import pandas as pd
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
)
from marketscope_pdf_theme import (
    ACCENT,
    CARD,
    CARD_ALT,
    LINE,
    TEXT,
    build_styles,
    document_kwargs,
    page_decorator,
    paragraph,
    table_style,
)

DISCLOSURES = {
    "Recession": "Recession resilience is based on historical stress performance and probabilistic modeling. No stock is guaranteed to preserve value during a recession.",
    "Max Profit": "High historical performance and projected return do not guarantee future results.",
}
LIMITATION = "Historical studies using current universe membership or current sectors are exploratory and subject to survivorship/classification bias. They are not certified leakage-free predictive validation. Missing point-in-time inputs are never represented as observed."


def build_top12_excel(kind, table, result, portfolio=None, history=None, backtest=None):
    out = BytesIO()
    from top12_rankings import WEIGHTS

    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        table.to_excel(writer, sheet_name="Top 12", index=False)
        result["all_scores"].to_excel(
            writer, sheet_name="All Candidate Scores", index=False
        )
        table.groupby("Sector").size().rename("Stocks").to_excel(
            writer, sheet_name="Sector Distribution"
        )
        pd.DataFrame(
            [{"Field": k, "Value": str(v)} for k, v in result["metadata"].items()]
        ).to_excel(writer, sheet_name="Timestamps and Model", index=False)
        pd.DataFrame(
            [{"Component": k, "Weight": v} for k, v in WEIGHTS[kind].items()]
        ).to_excel(writer, sheet_name="Methodology", index=False)
        pd.DataFrame((history or {}).get("events", [])).to_excel(
            writer, sheet_name="Ranking Changes", index=False
        )
        (
            backtest
            if isinstance(backtest, pd.DataFrame)
            else pd.DataFrame({"Status": ["Not run"]})
        ).to_excel(writer, sheet_name="Backtest", index=False)
        pd.DataFrame(
            {
                "Limitations": [
                    DISCLOSURES[kind],
                    LIMITATION,
                    *result.get("warnings", []),
                ]
            }
        ).to_excel(writer, sheet_name="Sources and Limitations", index=False)
        for strategy, payload in (portfolio or {}).get("strategies", {}).items():
            payload["table"].to_excel(writer, sheet_name=strategy[:31], index=False)
            pd.DataFrame(
                [{"Metric": k, "Value": str(v)} for k, v in payload["summary"].items()]
            ).to_excel(writer, sheet_name=(strategy + " Summary")[:31], index=False)
        for sheet in writer.book:
            sheet.freeze_panes = "C2"
            sheet.auto_filter.ref = sheet.dimensions
            for column in sheet.columns:
                sheet.column_dimensions[column[0].column_letter].width = min(
                    60, max(15, max(len(str(c.value or "")) for c in column) + 2)
                )
    return out.getvalue()


def build_top12_pdf(kind, table, result, portfolio=None, history=None, backtest=None):
    out = BytesIO()
    styles = build_styles()
    story = []

    def p(text, style="BodyText"):
        mapped = "MSBody" if style == "BodyText" else style
        return paragraph(text, styles, mapped)

    title = (
        "Top 12 Recession-Resilient Stocks"
        if kind == "Recession"
        else "Top 12 Max-Profit High-Performance Stocks"
    )
    story += [p(DISCLOSURES[kind], "MSWarning"), Spacer(1, 12)]
    for k, v in result["metadata"].items():
        story.append(p(f"{k}: {v}"))
    story += [Spacer(1, 12), p("Sector allocation", "Heading2")]
    for sector, count in table.groupby("Sector").size().items():
        story.append(
            p(f"{sector}: {count}" + (" — SECTOR CAP REACHED" if count == 4 else ""))
        )
    story.append(PageBreak())
    for i, row in enumerate(table.to_dict("records")):
        story.append(
            p(f"#{row['Rank']} {row['Symbol']} — {row.get('Name','')}", "Heading2")
        )
        story.append(p(row.get("Why Selected", "")))
        cols = [
            "Sector",
            kind + " Score",
            "Data Confidence",
            "Maximum Drawdown %",
            "Recovery Periods",
            "Recovery Basis",
        ] + [
            ("Bear " if kind == "Recession" else "") + f"P{q} Future Return %"
            for q in (10, 25, 50, 75, 90)
        ]
        rows = []
        for c in cols:
            value = row.get(c)
            if value is None or (isinstance(value, float) and not math.isfinite(value)):
                value = "Unavailable"
            elif isinstance(value, (float, int)):
                value = f"{value:,.2f}"
            rows.append([p(c), p(value)])
        t = Table(rows, colWidths=[360, 365])
        t.setStyle(table_style(font_size=7.4, header=False))
        t.setStyle(TableStyle([
            ("TEXTCOLOR", (0, 0), (0, -1), ACCENT),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ]))
        story.extend([t, Spacer(1, 12)])
        if i < 11:
            story.append(PageBreak())
    story += [PageBreak(), p("Methodology and validation", "Heading1"), p(LIMITATION)]
    from top12_rankings import WEIGHTS

    for component, weight in WEIGHTS[kind].items():
        story.append(p(f"{component}: {weight:.0%}"))
    if isinstance(backtest, pd.DataFrame) and not backtest.empty:
        story.append(
            p(
                f"{len(backtest)} exploratory walk-forward observations; full evidence is in Excel."
            )
        )
    else:
        story.append(p("Walk-forward study has not been run for this report."))
    for strategy, payload in (portfolio or {}).get("strategies", {}).items():
        story.extend([PageBreak(), p(strategy + " portfolio", "Heading1")])
        for k, v in payload["summary"].items():
            story.append(p(f"{k}: {v}"))
    story += [PageBreak(), p("Ranking changes", "Heading1")]
    for event in (history or {}).get("events", []):
        story.append(
            p(
                f"{event['Timestamp']}: added {event.get('Ticker Added') or '—'}; removed {event.get('Ticker Removed') or '—'}; rank {event.get('Previous Rank')} → {event.get('New Rank')}; {event['Reason for Change']}"
            )
        )
    if not (history or {}).get("events"):
        story.append(p("No changes recorded."))

    decorator = page_decorator(title, "Dynamic Top 12 ranking and portfolio evidence")
    SimpleDocTemplate(out, **document_kwargs("MarketScope " + title)).build(
        story, onFirstPage=decorator, onLaterPages=decorator
    )
    return out.getvalue()
