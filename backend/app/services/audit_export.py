import csv
import io
import json
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from app.models.audit import AuditLog


def audit_logs_to_csv(logs: list[AuditLog]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["date", "action", "entity_type", "entity_id", "user_id", "institution_id", "ip_address", "metadata"])
    for log in logs:
        writer.writerow(
            [
                _csv_safe(log.created_at.isoformat()),
                _csv_safe(log.action),
                _csv_safe(log.entity_type),
                _csv_safe(log.entity_id),
                _csv_safe(log.user_id),
                _csv_safe(log.institution_id),
                _csv_safe(log.ip_address),
                _csv_safe(json.dumps(log.extra, ensure_ascii=False, default=str, sort_keys=True)),
            ]
        )
    return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")


def audit_logs_to_pdf(logs: list[AuditLog]) -> bytes:
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title="Journal d'audit InfoBridge",
        author="InfoBridge",
    )
    styles = getSampleStyleSheet()
    small = styles["BodyText"]
    small.fontSize = 6
    small.leading = 8
    rows = [[
        Paragraph("<b>Date</b>", small),
        Paragraph("<b>Action</b>", small),
        Paragraph("<b>Entité</b>", small),
        Paragraph("<b>Utilisateur</b>", small),
        Paragraph("<b>IP</b>", small),
        Paragraph("<b>Métadonnées</b>", small),
    ]]
    for log in logs:
        metadata = json.dumps(log.extra, ensure_ascii=False, default=str, sort_keys=True)
        rows.append(
            [
                Paragraph(escape(log.created_at.isoformat()), small),
                Paragraph(escape(log.action), small),
                Paragraph(escape(f"{log.entity_type} · {log.entity_id or '-'}"), small),
                Paragraph(escape(str(log.user_id or "-")), small),
                Paragraph(escape(str(log.ip_address or "-")), small),
                Paragraph(escape(metadata[:1000]), small),
            ]
        )
    table = LongTable(rows, repeatRows=1, colWidths=[35 * mm, 38 * mm, 50 * mm, 40 * mm, 28 * mm, 76 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#202c3a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5df")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fa")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story = [Paragraph("Journal d'audit InfoBridge", styles["Title"]), Spacer(1, 4 * mm), table]
    document.build(story)
    return output.getvalue()


def _csv_safe(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text
