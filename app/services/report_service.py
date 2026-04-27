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
from datetime import date


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


def generate_transaction_template_pdf() -> bytes:
    """
    Generate a blank printable transaction template that flower shops fill in
    by hand. Designed so the OCR pipeline can parse it easily.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    base = getSampleStyleSheet()

    style_shop = ParagraphStyle(
        "ShopName", parent=base["Normal"],
        fontSize=18, fontName="Helvetica-Bold",
        textColor=PRIMARY, alignment=TA_LEFT,
    )
    style_date = ParagraphStyle(
        "DateLabel", parent=base["Normal"],
        fontSize=11, textColor=GREY, alignment=TA_RIGHT,
    )
    style_section = ParagraphStyle(
        "Sec", parent=base["Normal"],
        fontSize=9, textColor=GREY, alignment=TA_CENTER,
    )
    style_legend_head = ParagraphStyle(
        "LegHead", parent=base["Normal"],
        fontSize=10, fontName="Helvetica-Bold",
        textColor=PRIMARY, spaceBefore=4,
    )
    style_legend = ParagraphStyle(
        "Leg", parent=base["Normal"],
        fontSize=9, textColor=DARK, leading=14,
    )
    style_footer = ParagraphStyle(
        "Foot", parent=base["Normal"],
        fontSize=7.5, textColor=GREY, alignment=TA_CENTER,
    )

    story = []

    # ── Header row: shop name left, date right ──────────────────────────────
    header_data = [[
        Paragraph("🌸 &nbsp; Flower Shop Name: ___________________________", style_shop),
        Paragraph("Date: __ __ / __ __ / __ __ __ __", style_date),
    ]]
    header_table = Table(header_data, colWidths=[12 * cm, 5.5 * cm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=10))

    # ── Instructions line ───────────────────────────────────────────────────
    story.append(Paragraph(
        "Fill clearly in block letters · Weight in GRAMS · Grade: A / B / C",
        style_section,
    ))
    story.append(Spacer(1, 8))

    # ── Transaction table ───────────────────────────────────────────────────
    NUM_ROWS = 20
    col_headers = ["S.No", "Customer Name", "Flower Type", "Weight (g)", "Grade"]
    col_widths  = [1.2*cm, 5.5*cm, 5.0*cm, 3.0*cm, 2.3*cm]

    rows = [col_headers]
    for i in range(1, NUM_ROWS + 1):
        rows.append([str(i), "", "", "", ""])

    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        # Header
        ("BACKGROUND",    (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 10),
        ("ALIGN",         (0, 0), (-1, 0), "CENTER"),
        # Data rows
        ("FONTSIZE",      (0, 1), (-1, -1), 9),
        ("FONTNAME",      (0, 1), (0, -1), "Helvetica-Bold"),   # S.No bold
        ("TEXTCOLOR",     (0, 1), (0, -1), GREY),
        ("ALIGN",         (0, 0), (0, -1), "CENTER"),           # S.No centered
        ("ALIGN",         (4, 0), (4, -1), "CENTER"),           # Grade centered
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, colors.HexColor("#F0FDF4")]),
        ("GRID",          (0, 0), (-1, -1), 0.6, colors.HexColor("#D1D5DB")),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    story.append(Spacer(1, 14))

    # ── Grade legend ────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=LIGHT, spaceAfter=6))

    legend_data = [[
        Paragraph("Grade Reference:", style_legend_head),
        Paragraph("<b>A</b> = 1st Category &nbsp;&nbsp; (Premium — fresh, full bloom, no damage)", style_legend),
        Paragraph("<b>B</b> = 2nd Category &nbsp; (Good — slight imperfections, day-old)", style_legend),
        Paragraph("<b>C</b> = 3rd Category &nbsp; (Standard — minor damage, older stock)", style_legend),
    ]]
    legend_table = Table(
        [[
            Paragraph("Grade Reference:", style_legend_head),
            Paragraph(
                "<b>A</b> = 1st Category &nbsp;&nbsp; Premium — fresh, full bloom, no damage<br/>"
                "<b>B</b> = 2nd Category &nbsp; Good — slight imperfections, day-old stock<br/>"
                "<b>C</b> = 3rd Category &nbsp; Standard — minor damage or older stock",
                style_legend,
            ),
        ]],
        colWidths=[3.5 * cm, 14 * cm],
    )
    legend_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F0FDF4")),
        ("BOX",           (0, 0), (-1, -1), 0.6, LIGHT),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(legend_table)
    story.append(Spacer(1, 10))

    # ── Footer ───────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=LIGHT))
    story.append(Paragraph(
        "Tamil OCR Flower Transaction System · Scan this completed form to digitise records automatically",
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
