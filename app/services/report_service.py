"""
PDF Report Generator using ReportLab
Generates customer and monthly summary reports.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os
from datetime import date

# ── Tamil font registration ────────────────────────────────────────────────────
_TAMIL_FONT = "Helvetica"  # fallback
_TAMIL_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/lohit-tamil/Lohit-Tamil.ttf",
    "/usr/share/fonts/truetype/lohit-taml/Lohit-Tamil.ttf",
    "/usr/share/fonts/lohit-tamil/Lohit-Tamil.ttf",
]
for _path in _TAMIL_FONT_CANDIDATES:
    if os.path.exists(_path):
        try:
            pdfmetrics.registerFont(TTFont("LohitTamil", _path))
            _TAMIL_FONT = "LohitTamil"
        except Exception:
            pass
        break

# Flower code → Tamil + English mapping (must match ocr_service.FLOWER_CODE_MAP)
FLOWER_CODE_LEGEND = [
    ("1",  "மல்லிகை",     "Jasmine"),
    ("2",  "ரோஜா",        "Rose"),
    ("3",  "சேவந்தி",     "Chrysanthemum"),
    ("4",  "கனகாம்பரம்", "Crossandra"),
    ("5",  "அரளி",        "Oleander"),
    ("6",  "முல்லை",      "Mullai"),
    ("7",  "தாமரை",       "Lotus"),
    ("8",  "மரிகோல்டு",  "Marigold"),
    ("9",  "சாமந்தி",     "Sevanthi"),
    ("10", "நிலாம்பரி",  "Tuberose"),
]


# ── Colour palette ─────────────────────────────────────────────────────────────
PRIMARY   = colors.HexColor("#1B4332")
ACCENT    = colors.HexColor("#40916C")
LIGHT     = colors.HexColor("#D8F3DC")
WHITE     = colors.white
GREY      = colors.HexColor("#6B7280")
DARK      = colors.HexColor("#111827")


def _styles():
    base = getSampleStyleSheet()
    title = ParagraphStyle(
        "ReportTitle",
        parent=base["Title"],
        fontSize=20,
        textColor=PRIMARY,
        spaceAfter=4,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )
    subtitle = ParagraphStyle(
        "ReportSubtitle",
        parent=base["Normal"],
        fontSize=11,
        textColor=GREY,
        alignment=TA_CENTER,
        spaceAfter=20,
    )
    section = ParagraphStyle(
        "Section",
        parent=base["Heading2"],
        fontSize=13,
        textColor=PRIMARY,
        spaceBefore=16,
        spaceAfter=6,
        fontName="Helvetica-Bold",
    )
    body = ParagraphStyle(
        "Body",
        parent=base["Normal"],
        fontSize=10,
        textColor=DARK,
    )
    return title, subtitle, section, body


def generate_customer_report_pdf(report_data: dict) -> bytes:
    """
    Generate a PDF for a single customer's transaction history.
    report_data: output of transaction_service.get_customer_report()
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    title_style, subtitle_style, section_style, body_style = _styles()
    story = []

    # Header
    story.append(Paragraph("🌸 Flower Transaction Report", title_style))
    story.append(Paragraph("Tamil Handwritten OCR System", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT))
    story.append(Spacer(1, 12))

    # Customer summary box
    story.append(Paragraph("Customer Summary", section_style))
    summary_data = [
        ["Customer Name", report_data.get("customer_name", "-")],
        ["Total Transactions", str(report_data.get("transaction_count", 0))],
        ["Total Weight (kg)", f"{report_data.get('total_weight_kg', 0):.2f} kg"],
        ["Total Amount (₹)", f"₹ {report_data.get('total_amount', 0):,.2f}"],
        ["Report Generated", str(date.today())],
    ]
    summary_table = Table(summary_data, colWidths=[5 * cm, 10 * cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), DARK),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [WHITE, colors.HexColor("#F9FAFB")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 16))

    # Transaction detail table
    story.append(Paragraph("Transaction History", section_style))
    headers = ["Date", "Flower Type", "Weight (kg)", "Rate (₹/kg)", "Amount (₹)", "Confidence"]
    rows = [headers]
    for tx in report_data.get("transactions", []):
        rows.append([
            str(tx.get("transaction_date", "")),
            tx.get("flower_type", "-"),
            f"{tx.get('weight_kg', 0):.2f}",
            f"₹ {tx.get('price_per_kg', 0):.2f}",
            f"₹ {tx.get('total_amount', 0):,.2f}",
            f"{(tx.get('ocr_confidence') or 0) * 100:.0f}%",
        ])

    col_widths = [2.8*cm, 3.5*cm, 2.5*cm, 2.8*cm, 2.8*cm, 2.6*cm]
    detail_table = Table(rows, colWidths=col_widths, repeatRows=1)
    detail_table.setStyle(TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#F0FDF4")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(detail_table)

    # Footer
    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", thickness=1, color=LIGHT))
    story.append(Paragraph(
        "Generated by Tamil OCR Flower Transaction System | Confidential",
        ParagraphStyle("footer", parent=body_style, fontSize=8, textColor=GREY, alignment=TA_CENTER),
    ))

    doc.build(story)
    return buffer.getvalue()


def generate_transaction_template_pdf(customers: list = None) -> bytes:
    """
    Generate a printable transaction template.
    If customers list is provided, their Tamil names are pre-printed in the
    Customer Name column — users only need to fill in flower code, weight & grade.
    Flower types are replaced by numbered codes (see reference box on template).
    """
    customers = customers or []
    has_customers = bool(customers)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )

    base = getSampleStyleSheet()
    ta_font = _TAMIL_FONT  # LohitTamil if installed, else Helvetica

    style_shop = ParagraphStyle(
        "ShopName", parent=base["Normal"],
        fontSize=16, fontName="Helvetica-Bold",
        textColor=PRIMARY, alignment=TA_LEFT,
    )
    style_date = ParagraphStyle(
        "DateLabel", parent=base["Normal"],
        fontSize=11, textColor=GREY, alignment=TA_RIGHT,
    )
    style_section = ParagraphStyle(
        "Sec", parent=base["Normal"],
        fontSize=8.5, textColor=GREY, alignment=TA_CENTER,
    )
    style_legend_head = ParagraphStyle(
        "LegHead", parent=base["Normal"],
        fontSize=9, fontName="Helvetica-Bold",
        textColor=PRIMARY, spaceBefore=2,
    )
    style_legend = ParagraphStyle(
        "Leg", parent=base["Normal"],
        fontSize=8.5, textColor=DARK, leading=13,
    )
    style_footer = ParagraphStyle(
        "Foot", parent=base["Normal"],
        fontSize=7, textColor=GREY, alignment=TA_CENTER,
    )
    style_tamil_cell = ParagraphStyle(
        "TamilCell", parent=base["Normal"],
        fontSize=10, fontName=ta_font,
        textColor=DARK, leading=13,
    )
    style_code_cell = ParagraphStyle(
        "CodeCell", parent=base["Normal"],
        fontSize=9, fontName="Helvetica",  # base is Helvetica; Tamil spans use inline font tag
        textColor=colors.HexColor("#374151"), leading=12,
    )

    story = []

    # ── Header ──────────────────────────────────────────────────────────────
    header_data = [[
        Paragraph("🌸 &nbsp; Flower Shop &nbsp;&nbsp; Date: ____________", style_shop),
        Paragraph("Date: __ __ / __ __ / __ __ __ __", style_date),
    ]]
    header_table = Table(header_data, colWidths=[12 * cm, 5.3 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=6))

    # ── Flower code reference box ────────────────────────────────────────────
    # Split into two columns of 5
    left_codes  = FLOWER_CODE_LEGEND[:5]
    right_codes = FLOWER_CODE_LEGEND[5:]

    def _code_line(code, ta, en):
        # Code number and English text use Helvetica; Tamil name uses Tamil font inline.
        # We split into two paragraphs stacked, or use a hybrid approach:
        # Wrap Tamil portion in its own font tag if Tamil font is registered.
        if ta_font != "Helvetica":
            tamil_span = f'<font name="{ta_font}">{ta}</font>'
        else:
            tamil_span = ta
        return Paragraph(
            f'<font name="Helvetica-Bold">{code}</font>'
            f'<font name="Helvetica"> = </font>'
            f'{tamil_span}'
            f'<font name="Helvetica" color="#9CA3AF"> ({en})</font>',
            style_code_cell,
        )

    code_rows = [[_code_line(*l), _code_line(*r)] for l, r in zip(left_codes, right_codes)]
    code_table = Table(code_rows, colWidths=[8.6 * cm, 8.6 * cm])
    code_table.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
    ]))

    ref_outer = Table(
        [[Paragraph("🌸 Flower Code Reference — write the number in the Flower Code column", style_legend_head)],
         [code_table]],
        colWidths=[17.7 * cm],
    )
    ref_outer.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
        ("BOX",           (0, 0), (-1, -1), 0.8, ACCENT),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    story.append(ref_outer)
    story.append(Spacer(1, 6))

    # ── Instructions ────────────────────────────────────────────────────────
    instr = (
        "Customer names are pre-filled · Write Flower Code (number) · Weight in GRAMS · Grade A / B / C"
        if has_customers else
        "Fill clearly · Flower Code = number from reference above · Weight in GRAMS · Grade A / B / C"
    )
    story.append(Paragraph(instr, style_section))
    story.append(Spacer(1, 5))

    # ── Transaction table ────────────────────────────────────────────────────
    col_headers = ["S.No", "Customer Name", "Flower\nCode", "Weight\n(g)", "Grade"]
    col_widths  = [1.0*cm, 7.0*cm, 2.8*cm, 2.8*cm, 2.0*cm]  # narrower flower col

    NUM_ROWS = max(len(customers), 20)
    rows = [col_headers]
    for i, c in enumerate(customers):
        name_tamil = (c.get("name_tamil") or "").strip()
        name_en    = (c.get("name") or "").strip()
        # Use Tamil font only when the name actually contains Tamil characters.
        # Fall back to Helvetica for English/transliterated names so Latin glyphs render correctly.
        is_tamil = bool(name_tamil)
        display  = name_tamil if is_tamil else name_en
        cell_style = style_tamil_cell if is_tamil else ParagraphStyle(
            f"NameEn{i}", parent=style_tamil_cell, fontName="Helvetica",
        )
        rows.append([
            str(i + 1),
            Paragraph(display, cell_style),
            "",
            "",
            "",
        ])
    # Pad with blank rows if fewer than 20 customers
    for i in range(len(customers) + 1, NUM_ROWS + 1):
        rows.append([str(i), "", "", "", ""])

    table = Table(rows, colWidths=col_widths, repeatRows=1)
    ts = [
        # Header
        ("BACKGROUND",    (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 9),
        ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
        ("VALIGN",        (0, 0), (-1, 0), "MIDDLE"),
        # Data rows
        ("FONTSIZE",      (0, 1), (-1, -1), 9),
        ("FONTNAME",      (0, 1), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR",     (0, 1), (0, -1), GREY),
        ("ALIGN",         (0, 0), (0, -1), "CENTER"),
        ("ALIGN",         (2, 0), (4, -1), "CENTER"),
        ("VALIGN",        (0, 1), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, colors.HexColor("#F0FDF4")]),
        ("GRID",          (0, 0), (-1, -1), 0.6, colors.HexColor("#D1D5DB")),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
    ]
    # Highlight pre-filled name cells lightly
    if has_customers:
        ts.append(("BACKGROUND", (1, 1), (1, len(customers)), colors.HexColor("#ECFDF5")))
        ts.append(("FONTNAME",   (1, 1), (1, len(customers)), ta_font))

    table.setStyle(TableStyle(ts))
    story.append(table)
    story.append(Spacer(1, 8))

    # ── Grade legend ─────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=LIGHT, spaceAfter=4))
    legend_table = Table(
        [[
            Paragraph("Grade:", style_legend_head),
            Paragraph(
                "<b>A</b> = 1st Category — Premium (fresh, full bloom)&nbsp;&nbsp;&nbsp;"
                "<b>B</b> = 2nd Category — Good (slight imperfections)&nbsp;&nbsp;&nbsp;"
                "<b>C</b> = 3rd Category — Standard (older / minor damage)",
                style_legend,
            ),
        ]],
        colWidths=[1.8 * cm, 15.9 * cm],
    )
    legend_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
        ("BOX",           (0, 0), (-1, -1), 0.6, LIGHT),
    ]))
    story.append(legend_table)
    story.append(Spacer(1, 6))

    # ── Footer ──────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT))
    story.append(Paragraph(
        "Tamil OCR Flower Transaction System · Scan completed form to digitise records automatically",
        style_footer,
    ))

    doc.build(story)
    return buffer.getvalue()


def generate_monthly_report_pdf(report_data: dict) -> bytes:
    """Generate a PDF monthly summary report."""
    import calendar
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    title_style, subtitle_style, section_style, body_style = _styles()
    story = []

    month_name = calendar.month_name[report_data.get("month", 1)]
    year = report_data.get("year", date.today().year)

    story.append(Paragraph("🌸 Monthly Summary Report", title_style))
    story.append(Paragraph(f"{month_name} {year} | Tamil Handwritten OCR System", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT))
    story.append(Spacer(1, 12))

    # Grand total
    story.append(Paragraph("Monthly Overview", section_style))
    overview = [
        ["Period", f"{month_name} {year}"],
        ["Grand Total Revenue", f"₹ {report_data.get('grand_total', 0):,.2f}"],
    ]
    ov_table = Table(overview, colWidths=[5*cm, 10*cm])
    ov_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(ov_table)
    story.append(Spacer(1, 16))

    # Per-flower breakdown
    story.append(Paragraph("Flower-wise Breakdown", section_style))
    headers = ["Flower Type", "Total Weight (kg)", "Total Amount (₹)", "Transactions"]
    rows = [headers]
    for f in report_data.get("flowers", []):
        rows.append([
            f.get("flower_type", "-"),
            f"{f.get('total_weight_kg', 0):.2f} kg",
            f"₹ {f.get('total_amount', 0):,.2f}",
            str(f.get("transaction_count", 0)),
        ])

    ft = Table(rows, colWidths=[5*cm, 4*cm, 4.5*cm, 3.5*cm], repeatRows=1)
    ft.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#F0FDF4")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(ft)

    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", thickness=1, color=LIGHT))
    story.append(Paragraph(
        "Generated by Tamil OCR Flower Transaction System | Confidential",
        ParagraphStyle("footer", parent=body_style, fontSize=8, textColor=GREY, alignment=TA_CENTER),
    ))

    doc.build(story)
    return buffer.getvalue()
