"""Render an auditable, dependency-light diagnostic PDF."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _text(value: object) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _hash_text(value: object) -> str:
    digest = _text(value)
    return "<br/>".join(digest[index : index + 32] for index in range(0, len(digest), 32))


def build_diagnostic_pdf(payload: dict[str, Any]) -> bytes:
    """Build a formal English PDF from an immutable repository payload."""

    diagnosis = payload["diagnosis"]
    network = payload["network"]
    quality = payload["quality"]["current"]
    audit = payload.get("audit", {})
    identity = payload.get("identity", {})
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="SmartValve Condition Diagnostic Report",
        author="SmartValve AI Twin",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "SmartValveTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#102238"),
        alignment=TA_LEFT,
        spaceAfter=4 * mm,
    )
    heading = ParagraphStyle(
        "SmartValveHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#147987"),
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )
    body = ParagraphStyle(
        "SmartValveBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#24364A"),
    )
    story: list[object] = [
        Paragraph("SmartValve Condition Diagnostic Report", title),
        Paragraph(
            f"Run ID: {_text(payload['run_id'])}<br/>"
            f"Correlation ID: {_text(payload.get('correlation_id', 'not recorded'))}<br/>"
            f"Created at: {_text(payload.get('created_at', 'not recorded'))}<br/>"
            f"Operator: {_text(payload.get('operator_id', 'not recorded'))}<br/>"
            f"Authenticated subject: {_text(identity.get('subject', 'not recorded'))}<br/>"
            f"Identity issuer: {_text(identity.get('issuer', 'not recorded'))}<br/>"
            f"Authentication mode: {_text(identity.get('auth_mode', 'legacy'))}",
            body,
        ),
        Spacer(1, 3 * mm),
    ]
    summary_rows = [
        ["Asset", _text(payload["asset_id"]), "Source", _text(payload["source"])],
        [
            "Evidence grade",
            _text(payload.get("evidence_grade", "not recorded")),
            "Audit seal",
            "SHA-256 chained",
        ],
        [
            "Model",
            _text(payload["model_version"]),
            "Decision",
            _text(diagnosis.get("decision_state", "legacy")),
        ],
        [
            "NE 107 style state",
            _text(diagnosis["ne107_status"]),
            "Health score",
            f"{float(diagnosis['health_score']):.1f} / 100",
        ],
        [
            "Data quality",
            f"{float(quality['score']):.1f} / 100 ({_text(quality['status'])})",
            "Network impact",
            f"{float(network['impact_score']):.1f} / 100",
        ],
    ]
    summary = Table(summary_rows, colWidths=[35 * mm, 56 * mm, 35 * mm, 52 * mm])
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2F7FA")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#24364A")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C7D7E3")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend(
        [
            summary,
            Paragraph("Primary finding", heading),
            Paragraph(_text(diagnosis["primary_finding"]), body),
            Paragraph("Recommended action", heading),
            Paragraph(_text(diagnosis["recommendation"]), body),
            Paragraph("Evidence", heading),
        ]
    )
    evidence_rows = [["Variable", "Value"]] + [
        [_text(name), _text(value)] for name, value in diagnosis["evidence"].items()
    ]
    evidence = Table(evidence_rows, colWidths=[100 * mm, 78 * mm], repeatRows=1)
    evidence.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#102238")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F7FA")]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C7D7E3")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    affected = ", ".join(network["affected_nodes"]) or "None"
    story.extend(
        [
            evidence,
            Paragraph("Hydraulic consequence", heading),
            Paragraph(
                f"Available travel: {float(network['available_travel_pct']):.1f}%<br/>"
                f"Affected nodes: {_text(affected)}<br/>"
                f"Engine: {_text(network['engine'])}",
                body,
            ),
            Paragraph("Claim boundary", heading),
            Paragraph(
                "This report is generated by an industrial engineering PoC. Hydraulic loss "
                "mapping remains illustrative until calibrated with a product-specific Kv/Cv "
                "curve. Public rig evidence is not manufacturer product validation.",
                body,
            ),
            Paragraph("Data integrity", heading),
            Paragraph(
                "Baseline data SHA-256:<br/>"
                f"{_hash_text(audit.get('baseline_sha256', 'not recorded'))}<br/>"
                f"Current data SHA-256:<br/>{_hash_text(quality['data_sha256'])}<br/>"
                f"Result SHA-256:<br/>{_hash_text(audit.get('result_sha256', 'not recorded'))}<br/>"
                "Audit record SHA-256:<br/>"
                f"{_hash_text(audit.get('record_sha256', 'not recorded'))}",
                body,
            ),
            Paragraph("Limitations", heading),
            Paragraph(
                "<br/>".join(
                    f"- {_text(item)}" for item in payload.get("limitations", ["Not recorded"])
                ),
                body,
            ),
        ]
    )
    document.build(story)
    return buffer.getvalue()
