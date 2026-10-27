import io
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.graphics.shapes import (
    Drawing,
    Rect,
    String,
    Line,
    Circle,
    PolyLine,
    Group,
)
from sqlalchemy.orm import Session

from app.models import Employee, RiskRecord, AlertCase, CaseNote, AnalystFeedback

RULE_FLAG_DESCRIPTIONS = {
    "off_hours_upload": "Data transfer initiated outside standard working hours (8 PM - 6 AM)",
    "risky_destination": "Upload directed to an unapproved, personal, or external cloud destination",
    "unusual_geo": "Authentication from an atypical geographic location or unrecognised IP subnet",
    "split_transfer": "Multiple consecutive upload chunks on the same day (potential threshold avoidance)",
    "usb_spike": "Elevated volume of USB or removable storage device write events",
    "privilege_escalation": "Elevated system privileges used immediately preceding data transfer",
}

TIER_COLORS = {
    "Critical": colors.HexColor("#ef4444"),
    "High": colors.HexColor("#f97316"),
    "Medium": colors.HexColor("#eab308"),
    "Low": colors.HexColor("#22c55e"),
}


class NumberedCanvas:
    """Canvas wrapper to add running headers and footers with page numbers."""

    def __init__(self, *args, **kwargs):
        pass


def make_trend_chart(trend_data: list[tuple[str, float]], target_date_str: str) -> Drawing:
    """
    Renders a crisp vector 14-day risk-score trend line chart using pure ReportLab Drawing.
    trend_data: list of (date_str, risk_score)
    """
    d = Drawing(520, 110)

    # Background canvas
    d.add(Rect(0, 0, 520, 110, fillColor=colors.HexColor("#0f172a"), strokeColor=colors.HexColor("#1e293b"), strokeWidth=1, rx=4, ry=4))

    # Grid parameters
    x_offset = 40
    y_offset = 22
    plot_width = 450
    plot_height = 70

    # Draw horizontal grid lines (0, 35, 60, 85, 100)
    grid_levels = [(0, "0"), (35, "35"), (60, "60"), (85, "85"), (100, "100")]
    for val, label in grid_levels:
        y_pos = y_offset + (val / 100.0) * plot_height
        d.add(Line(x_offset, y_pos, x_offset + plot_width, y_pos, strokeColor=colors.HexColor("#334155"), strokeWidth=0.5, strokeDashArray=[2, 2]))
        d.add(String(x_offset - 25, y_pos - 3, label, fontName="Helvetica", fontSize=7, fillColor=colors.HexColor("#64748b")))

    if not trend_data:
        d.add(String(200, 50, "Insufficient trend history available", fontName="Helvetica", fontSize=9, fillColor=colors.HexColor("#94a3b8")))
        return d

    n_points = len(trend_data)
    step = plot_width / max(1, n_points - 1) if n_points > 1 else plot_width / 2

    points = []
    circles = []

    for idx, (dt_str, score) in enumerate(trend_data):
        cx = x_offset + (idx * step if n_points > 1 else plot_width / 2)
        cy = y_offset + (min(100.0, max(0.0, score)) / 100.0) * plot_height
        points.append((cx, cy))

        is_target = dt_str == target_date_str
        dot_color = colors.HexColor("#ef4444") if is_target else (colors.HexColor("#38bdf8") if score >= 60 else colors.HexColor("#64748b"))
        dot_radius = 4 if is_target else 2.5

        circles.append(Circle(cx, cy, dot_radius, fillColor=dot_color, strokeColor=colors.HexColor("#0f172a"), strokeWidth=1))

        # Show x-axis date labels for first, mid, and last points
        if idx == 0 or idx == n_points - 1 or idx == n_points // 2 or is_target:
            short_dt = dt_str[5:]  # MM-DD
            d.add(String(cx - 10, y_offset - 14, short_dt, fontName="Helvetica", fontSize=7, fillColor=colors.HexColor("#94a3b8")))

    # Draw line connecting points
    if len(points) > 1:
        flat_points = [coord for pt in points for coord in pt]
        d.add(PolyLine(flat_points, strokeColor=colors.HexColor("#38bdf8"), strokeWidth=2))

    for c in circles:
        d.add(c)

    return d


def generate_incident_pdf(db: Session, employee_id: str, incident_date) -> bytes:
    """Generates a professional 1-2 page PDF Incident Report."""
    # Retrieve required data
    record = (
        db.query(RiskRecord)
        .filter(RiskRecord.employee_id == employee_id, RiskRecord.date == incident_date)
        .first()
    )
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    case = (
        db.query(AlertCase)
        .filter(AlertCase.employee_id == employee_id, AlertCase.date == incident_date)
        .first()
    )
    feedback = (
        db.query(AnalystFeedback)
        .filter(AnalystFeedback.employee_id == employee_id, AnalystFeedback.date == incident_date)
        .first()
    )
    notes = (
        db.query(CaseNote)
        .filter(CaseNote.employee_id == employee_id, CaseNote.date == incident_date)
        .order_by(CaseNote.created_at.asc())
        .all()
    )

    # 14-day trend query
    start_date = incident_date - timedelta(days=14)
    trend_records = (
        db.query(RiskRecord.date, RiskRecord.risk_score)
        .filter(
            RiskRecord.employee_id == employee_id,
            RiskRecord.date >= start_date,
            RiskRecord.date <= incident_date,
        )
        .order_by(RiskRecord.date.asc())
        .all()
    )
    trend_data = [(r.date.isoformat(), float(r.risk_score)) for r in trend_records]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    header_title_style = ParagraphStyle(
        "HeaderTitle",
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#0f172a"),
    )
    sub_title_style = ParagraphStyle(
        "SubTitle",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748b"),
    )
    section_h1 = ParagraphStyle(
        "SectionH1",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#0284c7"),
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "BodyDark",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )
    callout_style = ParagraphStyle(
        "CalloutText",
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=13,
        textColor=colors.HexColor("#1e293b"),
    )

    elements = []

    # 1. Header & Title Block
    header_data = [
        [
            Paragraph("<b>SENTINEL AI</b> &bull; INSIDER THREAT INCIDENT DOSSIER", header_title_style),
            Paragraph(
                f"<b>CONFIDENTIAL</b><br/>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                ParagraphStyle("RAlign", parent=sub_title_style, alignment=2),
            ),
        ]
    ]
    header_table = Table(header_data, colWidths=[340, 200])
    header_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    elements.append(header_table)
    elements.append(Spacer(1, 4))

    # Divider bar
    d_bar = Drawing(540, 2)
    d_bar.add(Line(0, 1, 540, 1, strokeColor=colors.HexColor("#0284c7"), strokeWidth=2))
    elements.append(d_bar)
    elements.append(Spacer(1, 8))

    # 2. Key Target Metadata & Risk Score Banner
    risk_score = record.risk_score if record else 0.0
    risk_tier = record.risk_tier if record else "Low"
    case_status = case.status if case else "New"
    assignee = case.assignee if (case and case.assignee) else "Unassigned"
    emp_name = employee.name if employee else employee_id
    department = employee.department if employee else "Unassigned"

    tier_color = TIER_COLORS.get(risk_tier, colors.HexColor("#64748b"))

    meta_cells = [
        [
            Paragraph("<b>Employee ID:</b>", body_style),
            Paragraph(f"<b>{employee_id}</b> ({emp_name})", body_style),
            Paragraph("<b>Risk Score:</b>", body_style),
            Paragraph(
                f"<font color='{tier_color.hexval()}'><b>{risk_score:.1f} / 100 ({risk_tier})</b></font>",
                body_style,
            ),
        ],
        [
            Paragraph("<b>Department:</b>", body_style),
            Paragraph(department, body_style),
            Paragraph("<b>Case Status:</b>", body_style),
            Paragraph(f"<b>{case_status}</b> (Investigator: {assignee})", body_style),
        ],
        [
            Paragraph("<b>Incident Date:</b>", body_style),
            Paragraph(incident_date.isoformat(), body_style),
            Paragraph("<b>Analyst Verdict:</b>", body_style),
            Paragraph(
                (
                    f"<b>{feedback.label.upper().replace('_', ' ')}</b>"
                    if feedback
                    else "<i>Pending Review</i>"
                ),
                body_style,
            ),
        ],
    ]
    meta_table = Table(meta_cells, colWidths=[90, 180, 90, 180])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    elements.append(meta_table)
    elements.append(Spacer(1, 10))

    # 3. AI Investigation Agent Explanation
    elements.append(Paragraph("EXECUTIVE AI INVESTIGATION SUMMARY", section_h1))
    explanation_text = (
        record.explanation
        if (record and record.explanation)
        else "No automated narrative available for this record."
    )
    expl_table = Table(
        [[Paragraph(explanation_text, callout_style)]],
        colWidths=[540],
    )
    expl_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
            ("LINEBEFORE", (0, 0), (0, -1), 3.5, colors.HexColor("#0284c7")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ])
    )
    elements.append(expl_table)
    elements.append(Spacer(1, 10))

    # 4. Ensemble Model Score Breakdown & Plain-Language Rule Flags
    col_left = []
    col_left.append(Paragraph("DETECTION ENSEMBLE BREAKDOWN", section_h1))
    if record:
        model_rows = [
            [
                Paragraph("<b>Model</b>", body_style),
                Paragraph("<b>Anomaly Score</b>", body_style),
                Paragraph("<b>Interpretation</b>", body_style),
            ],
            [
                Paragraph("Isolation Forest", body_style),
                Paragraph(f"{record.isolation_forest_score:.3f}", body_style),
                Paragraph("Unsupervised Outlier", body_style),
            ],
            [
                Paragraph("Deep Autoencoder", body_style),
                Paragraph(f"{record.autoencoder_score:.3f}", body_style),
                Paragraph("Reconstruction Anomaly", body_style),
            ],
            [
                Paragraph("LSTM Sequence Net", body_style),
                Paragraph(f"{record.lstm_score:.3f}", body_style),
                Paragraph("Multi-Day Drift Error", body_style),
            ],
            [
                Paragraph("XGBoost Supervised", body_style),
                Paragraph(f"{record.xgboost_score:.3f}", body_style),
                Paragraph("Exfiltration Probability", body_style),
            ],
        ]
    else:
        model_rows = [[Paragraph("No model record available", body_style)]]

    model_table = Table(model_rows, colWidths=[100, 75, 85])
    model_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    col_left.append(model_table)

    col_right = []
    col_right.append(Paragraph("RULE VIOLATIONS DETECTED", section_h1))
    rule_flags = record.rule_flags if (record and record.rule_flags) else []
    if rule_flags:
        flag_rows = []
        for flag in rule_flags:
            desc = RULE_FLAG_DESCRIPTIONS.get(flag, flag.replace("_", " ").capitalize())
            flag_rows.append([
                Paragraph(f"&bull; <b>{flag}</b>:", body_style),
                Paragraph(desc, body_style),
            ])
        flag_table = Table(flag_rows, colWidths=[100, 160])
        flag_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ])
        )
        col_right.append(flag_table)
    else:
        col_right.append(Paragraph("<i>No heuristic rule triggers fired. Signal purely behavioural.</i>", body_style))

    two_col_table = Table([[col_left, col_right]], colWidths=[270, 270])
    two_col_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements.append(two_col_table)
    elements.append(Spacer(1, 10))

    # 5. 14-Day Risk-Score Trend Chart
    elements.append(Paragraph("14-DAY BEHAVIOURAL RISK TRAJECTORY", section_h1))
    chart_drawing = make_trend_chart(trend_data, incident_date.isoformat())
    elements.append(chart_drawing)
    elements.append(Spacer(1, 10))

    # 6. Case Notes & Analyst Log Timeline
    elements.append(Paragraph("INVESTIGATIVE NOTES & ACTIONS TIMELINE", section_h1))
    note_rows = [
        [
            Paragraph("<b>Timestamp (UTC)</b>", body_style),
            Paragraph("<b>Author</b>", body_style),
            Paragraph("<b>Note / Observation</b>", body_style),
        ]
    ]

    if feedback:
        note_rows.append([
            Paragraph(feedback.created_at.strftime("%Y-%m-%d %H:%M"), body_style),
            Paragraph(f"Analyst: {feedback.analyst}", body_style),
            Paragraph(f"<b>VERDICT: {feedback.label.upper()}</b> &bull; {feedback.note or ''}", body_style),
        ])

    for n in notes:
        note_rows.append([
            Paragraph(n.created_at.strftime("%Y-%m-%d %H:%M"), body_style),
            Paragraph(n.author, body_style),
            Paragraph(n.text, body_style),
        ])

    if len(note_rows) == 1:
        note_rows.append([
            Paragraph("-", body_style),
            Paragraph("System", body_style),
            Paragraph("<i>No investigative case notes recorded yet.</i>", body_style),
        ])

    notes_table = Table(note_rows, colWidths=[100, 110, 330])
    notes_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    elements.append(notes_table)
    elements.append(Spacer(1, 14))

    # 7. Privacy Compliance Footer
    footer_text = (
        "<b>LEGAL &amp; COMPLIANCE NOTICE:</b> Generated from behavioural metadata only. "
        "No file contents were inspected."
    )
    footer_p = Paragraph(
        footer_text,
        ParagraphStyle(
            "Footer",
            fontName="Helvetica-Oblique",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#64748b"),
            alignment=1,
        ),
    )
    elements.append(footer_p)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
