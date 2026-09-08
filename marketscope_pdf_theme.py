"""Shared MarketScope PDF presentation system.

All vector reports use the same dark, landscape visual language as the saved
Stock/Portfolio Projection report.  Report builders remain responsible for
their own content and calculations; this module only owns presentation.
"""

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, TableStyle


PAGE_SIZE = landscape(A4)
BACKGROUND = colors.HexColor("#06101A")
HEADER_WASH = colors.HexColor("#081E25")
CARD = colors.HexColor("#0C1824")
CARD_ALT = colors.HexColor("#0B1621")
BORDER = colors.HexColor("#27465A")
LINE = colors.HexColor("#20394A")
ACCENT = colors.HexColor("#56E58B")
CYAN = colors.HexColor("#68D7FF")
TEXT = colors.HexColor("#F2F7FB")
MUTED = colors.HexColor("#A5B5C3")
WARNING_BG = colors.HexColor("#2A1B12")
WARNING_TEXT = colors.HexColor("#FED7AA")


def marketscope_version() -> str:
    try:
        return (Path(__file__).with_name("VERSION.txt").read_text(encoding="utf-8").strip() or "unknown")
    except OSError:
        return "unknown"


def build_styles():
    styles = getSampleStyleSheet()
    styles["Title"].fontName = "Helvetica-Bold"
    styles["Title"].fontSize = 18
    styles["Title"].leading = 22
    styles["Title"].textColor = ACCENT
    styles["Title"].spaceAfter = 8
    for name in ("Heading1", "Heading2", "Heading3"):
        styles[name].fontName = "Helvetica-Bold"
        styles[name].textColor = ACCENT
    styles["Heading1"].fontSize = 14
    styles["Heading1"].leading = 18
    styles["Heading2"].fontSize = 10.5
    styles["Heading2"].leading = 14
    styles["Heading3"].fontSize = 9
    styles["Heading3"].leading = 12
    styles["BodyText"].fontName = "Helvetica"
    styles["BodyText"].fontSize = 8.2
    styles["BodyText"].leading = 10.5
    styles["BodyText"].textColor = TEXT
    styles.add(ParagraphStyle(
        name="MSBody", parent=styles["BodyText"], alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="MSMuted", parent=styles["BodyText"], textColor=MUTED,
        fontSize=7.4, leading=9.2,
    ))
    styles.add(ParagraphStyle(
        name="MSWarning", parent=styles["BodyText"], fontSize=7.8, leading=10,
        textColor=WARNING_TEXT, backColor=WARNING_BG, borderColor=colors.HexColor("#9A5A23"),
        borderWidth=0.6, borderPadding=6,
    ))
    styles.add(ParagraphStyle(
        name="MSCell", parent=styles["BodyText"], fontSize=6.5, leading=8,
    ))
    styles.add(ParagraphStyle(
        name="MSCellMuted", parent=styles["MSCell"], textColor=MUTED,
    ))
    return styles


def paragraph(value, styles, style="MSBody"):
    cleaned = str(value if value is not None else "").replace("—", "-").replace("→", "to")
    return Paragraph(escape(cleaned), styles[style])


def table_style(*, font_size=7.2, header=True, grid=True, align=None):
    commands = [
        ("TEXTCOLOR", (0, 0), (-1, -1), TEXT),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 1.7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [CARD, CARD_ALT]),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B40")),
            ("TEXTCOLOR", (0, 0), (-1, 0), ACCENT),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])
    if grid:
        commands.append(("GRID", (0, 0), (-1, -1), 0.35, LINE))
    if align:
        commands.append(("ALIGN", (0, 0), (-1, -1), align))
    return TableStyle(commands)


def page_decorator(report_title: str, subtitle: str = ""):
    """Return a Platypus page callback matching the Stock Projection PDF."""

    def draw(canvas, doc):
        width, height = doc.pagesize
        canvas.saveState()
        canvas.setFillColor(BACKGROUND)
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
        canvas.setFillColor(HEADER_WASH)
        canvas.rect(0, height - 66, width, 66, fill=1, stroke=0)
        canvas.setFillColor(ACCENT)
        canvas.setFont("Helvetica-Bold", 14)
        canvas.drawString(30, height - 31, report_title[:78])
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7.2)
        if subtitle:
            canvas.drawString(30, height - 47, subtitle[:120])
        canvas.setFont("Helvetica-Bold", 7.2)
        canvas.drawRightString(width - 30, height - 31, f"MarketScope v{marketscope_version()}")
        canvas.setStrokeColor(LINE)
        canvas.line(30, 30, width - 30, 30)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 6.8)
        canvas.drawString(30, 18, "MarketScope research report - historical results and projections do not guarantee future performance.")
        canvas.drawRightString(width - 30, 18, f"Page {doc.page}")
        canvas.restoreState()

    return draw


def document_kwargs(title: str):
    return dict(
        pagesize=PAGE_SIZE,
        rightMargin=0.42 * inch,
        leftMargin=0.42 * inch,
        topMargin=0.95 * inch,
        bottomMargin=0.48 * inch,
        title=title,
    )
