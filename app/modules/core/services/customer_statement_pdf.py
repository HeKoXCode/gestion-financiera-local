from __future__ import annotations

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from django.utils.text import slugify
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from modules.core.models import BusinessSettings, Customer, Payment
from modules.core.services.money import format_ars

PRIMARY = colors.HexColor("#126C5D")
PRIMARY_DARK = colors.HexColor("#173A32")
ACCENT = colors.HexColor("#E4AC50")
INK = colors.HexColor("#172520")
MUTED = colors.HexColor("#66756F")
LINE = colors.HexColor("#D6DFDB")
SOFT = colors.HexColor("#F2F6F4")
PAID = colors.HexColor("#E8F4EF")
WARNING = colors.HexColor("#FBF0E7")


def customer_statement_filename(customer: Customer, as_of) -> str:
    safe_name = slugify(customer.full_name) or f"cliente-{customer.pk}"
    return f"resumen-{safe_name}-{as_of:%Y-%m-%d}.pdf"


def _text(value) -> str:
    return escape(str(value or ""))


def _paragraph(value, style):
    return Paragraph(_text(value), style)


def _table(data, widths, *, header_rows=1, font_size=7.4):
    table_class = LongTable if len(data) > 8 else Table
    table = table_class(
        data,
        colWidths=widths,
        repeatRows=header_rows,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, header_rows - 1), SOFT),
                ("TEXTCOLOR", (0, 0), (-1, header_rows - 1), MUTED),
                ("FONTNAME", (0, 0), (-1, header_rows - 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), font_size),
                ("LEADING", (0, 0), (-1, -1), font_size + 2),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _section_title(title, count, styles):
    return Table(
        [[Paragraph(_text(title), styles["SectionTitle"]), str(count)]],
        colWidths=[157 * mm, 20 * mm],
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (1, 0), (1, 0), 8),
                ("TEXTCOLOR", (1, 0), (1, 0), MUTED),
                ("LINEBELOW", (0, 0), (-1, -1), 1.2, PRIMARY_DARK),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        ),
    )


def _page_footer(canvas, document, *, business_name, as_of):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(16 * mm, 11 * mm, 194 * mm, 11 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(16 * mm, 7 * mm, business_name)
    canvas.drawRightString(
        194 * mm,
        7 * mm,
        f"Actualizado al {as_of:%d/%m/%Y} · Página {document.page}",
    )
    canvas.restoreState()


def build_customer_statement_pdf(
    *,
    customer: Customer,
    as_of,
    history: dict,
    settings: BusinessSettings,
) -> bytes:
    """Create the privacy-reduced customer-facing account statement."""
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=f"Resumen de cuenta de {customer.full_name}",
        author=settings.business_name,
        pageCompression=0,
    )

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Business",
            parent=styles["Normal"],
            textColor=INK,
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=15,
        )
    )
    styles.add(
        ParagraphStyle(
            name="DocumentTitle",
            parent=styles["Normal"],
            textColor=PRIMARY,
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=20,
            alignment=TA_RIGHT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CustomerName",
            parent=styles["Normal"],
            textColor=INK,
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=18,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Normal"],
            textColor=INK,
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Cell",
            parent=styles["Normal"],
            textColor=INK,
            fontSize=7.4,
            leading=9.3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CellRight",
            parent=styles["Cell"],
            alignment=TA_RIGHT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Disclaimer",
            parent=styles["Normal"],
            textColor=MUTED,
            fontSize=7.2,
            leading=9.2,
            alignment=TA_CENTER,
        )
    )

    story = []
    logo = None
    try:
        logo_path = Path(settings.logo.path) if settings.logo else None
        if logo_path and logo_path.is_file():
            logo = Image(str(logo_path), width=18 * mm, height=18 * mm, kind="proportional")
    except (NotImplementedError, OSError, ValueError):
        logo = None

    brand_mark = logo or Table(
        [["GF"]],
        colWidths=[18 * mm],
        rowHeights=[18 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.5, PRIMARY),
            ]
        ),
    )
    header = Table(
        [
            [
                brand_mark,
                Paragraph(
                    f"{_text(settings.business_name)}<br/>"
                    '<font name="Helvetica" size="7" color="#66756F">'
                    "Ventas, préstamos y cobranza</font>",
                    styles["Business"],
                ),
                Paragraph(
                    "Resumen de cuenta<br/>"
                    f'<font name="Helvetica" size="8" color="#66756F">'
                    f"Al {as_of:%d/%m/%Y}</font>",
                    styles["DocumentTitle"],
                ),
            ]
        ],
        colWidths=[21 * mm, 89 * mm, 67 * mm],
        style=TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LINEBELOW", (0, 0), (-1, -1), 1.5, PRIMARY_DARK),
            ]
        ),
    )
    story.extend([header, Spacer(1, 6 * mm)])

    customer_box = Table(
        [
            [
                Paragraph(
                    '<font size="7" color="#66756F">CLIENTE</font><br/>'
                    f"<b>{_text(customer.full_name)}</b>",
                    styles["CustomerName"],
                ),
                Paragraph(
                    '<font size="7" color="#66756F">RESUMEN ACTUALIZADO</font><br/>'
                    f"<b>{as_of:%d/%m/%Y}</b>",
                    styles["CellRight"],
                ),
            ]
        ],
        colWidths=[125 * mm, 52 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        ),
    )
    story.extend([customer_box, Spacer(1, 3 * mm)])

    kpi_data = [
        (
            "TOTAL EN CUOTAS",
            format_ars(history["total_installments"]),
            SOFT,
        ),
        ("TOTAL ABONADO", format_ars(history["total_paid"]), PAID),
        ("SALDO TOTAL PENDIENTE", format_ars(history["total_balance"]), WARNING),
        ("CUOTAS VENCIDAS", str(history["overdue_installments"]), WARNING),
    ]
    kpis = Table(
        [
            [
                Paragraph(
                    f'<font size="6.5" color="#66756F">{label}</font><br/>'
                    f'<font size="11"><b>{_text(value)}</b></font>',
                    styles["Cell"],
                )
                for label, value, _ in kpi_data
            ]
        ],
        colWidths=[44.25 * mm] * 4,
        style=TableStyle(
            [
                *(
                    ("BACKGROUND", (index, 0), (index, 0), background)
                    for index, (_, _, background) in enumerate(kpi_data)
                ),
                ("BOX", (0, 0), (-1, -1), 0.5, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        ),
    )
    story.extend([kpis, Spacer(1, 5 * mm)])

    sale_rows = history["sale_rows"]
    story.extend(
        [
            _section_title("Ventas, préstamos y planes de cuotas", len(sale_rows), styles),
            Spacer(1, 2 * mm),
        ]
    )
    if sale_rows:
        data = [["Fecha", "Operación", "Plan", "Situación", "Total acordado", "Saldo pendiente"]]
        for row in sale_rows:
            sale = row["sale"]
            data.append(
                [
                    f"{sale.delivery_date:%d/%m/%Y}",
                    _paragraph(sale.product_description, styles["Cell"]),
                    _paragraph(
                        f"{sale.installment_count} cuotas · {sale.get_frequency_display()}",
                        styles["Cell"],
                    ),
                    sale.get_status_display(),
                    _paragraph(format_ars(sale.financed_amount), styles["CellRight"]),
                    _paragraph(format_ars(row["exigible_total"]), styles["CellRight"]),
                ]
            )
        story.append(_table(data, [20 * mm, 43 * mm, 34 * mm, 22 * mm, 29 * mm, 29 * mm]))
    else:
        story.append(Paragraph("No hay ventas ni préstamos registrados.", styles["Disclaimer"]))

    installment_rows = history["installment_rows"]
    story.extend(
        [
            Spacer(1, 5 * mm),
            _section_title("Detalle de todas las cuotas", len(installment_rows), styles),
            Spacer(1, 2 * mm),
        ]
    )
    if installment_rows:
        data = [["Operación", "Cuota", "Vencimiento", "Situación", "Importe", "Recargos", "Saldo"]]
        for row in installment_rows:
            data.append(
                [
                    _paragraph(row["sale"].product_description, styles["Cell"]),
                    f'{row["installment"].number}/{row["sale"].installment_count}',
                    f'{row["installment"].due_date:%d/%m/%Y}',
                    _paragraph(row["status_label"], styles["Cell"]),
                    _paragraph(
                        format_ars(row["installment"].original_amount),
                        styles["CellRight"],
                    ),
                    _paragraph(
                        format_ars(row["balance"].late_fees_generated),
                        styles["CellRight"],
                    ),
                    _paragraph(
                        format_ars(row["balance"].total_due),
                        styles["CellRight"],
                    ),
                ]
            )
        story.append(
            _table(
                data,
                [38 * mm, 15 * mm, 23 * mm, 30 * mm, 24 * mm, 23 * mm, 24 * mm],
                font_size=7,
            )
        )
    else:
        story.append(Paragraph("No hay cuotas registradas.", styles["Disclaimer"]))

    payments = history["payments"]
    story.extend(
        [
            Spacer(1, 5 * mm),
            _section_title("Pagos registrados", len(payments), styles),
            Spacer(1, 2 * mm),
        ]
    )
    if payments:
        data = [["Fecha", "Concepto", "Operación", "Situación", "Importe"]]
        for payment in payments:
            payment_status = (
                "Registrado" if payment.status == Payment.Status.REGISTERED else "Anulado"
            )
            data.append(
                [
                    f"{payment.payment_date:%d/%m/%Y}",
                    payment.get_kind_display(),
                    _paragraph(payment.sale.product_description, styles["Cell"]),
                    payment_status,
                    _paragraph(format_ars(payment.amount), styles["CellRight"]),
                ]
            )
        story.append(_table(data, [24 * mm, 31 * mm, 62 * mm, 28 * mm, 32 * mm]))
    else:
        story.append(Paragraph("Todavía no hay pagos registrados.", styles["Disclaimer"]))

    story.extend(
        [
            Spacer(1, 5 * mm),
            Paragraph(
                "Este resumen refleja los movimientos registrados en el sistema hasta la fecha "
                "indicada. Ante cualquier diferencia, consultá con el negocio.",
                styles["Disclaimer"],
            ),
        ]
    )

    def footer(canvas, doc):
        _page_footer(
            canvas,
            doc,
            business_name=settings.business_name,
            as_of=as_of,
        )

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
