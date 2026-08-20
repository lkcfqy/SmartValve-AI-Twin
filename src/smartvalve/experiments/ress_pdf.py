"""Render a deterministic RESS manuscript PDF and machine-check its page topology."""

from __future__ import annotations

import hashlib
import html
import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    LongTable,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    TableStyle,
)

RENDERER_VERSION = "smartvalve-ress-pdf-renderer-0.1.2"
EXPECTED_MAIN_FIGURE_COUNT = 5
FORBIDDEN_FINAL_MARKERS = (
    "SMARTVALVE_EMPIRICAL_FINAL",
    "working manuscript",
    "raw sensitivity in progress",
    "author action required",
    "submission hold",
    "TODO",
    "TBD",
    "{{",
    "}}",
)
DEJAVU_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
DEJAVU_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
DEJAVU_MONO = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")


def sha256_file(path: Path) -> str:
    """Hash a file in bounded chunks."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _register_fonts() -> tuple[str, str, str]:
    if all(path.is_file() for path in (DEJAVU_REGULAR, DEJAVU_BOLD, DEJAVU_MONO)):
        names = ("SmartValveSans", "SmartValveSans-Bold", "SmartValveMono")
        if names[0] not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(names[0], str(DEJAVU_REGULAR)))
            pdfmetrics.registerFont(TTFont(names[1], str(DEJAVU_BOLD)))
            pdfmetrics.registerFont(TTFont(names[2], str(DEJAVU_MONO)))
        return names
    return "Helvetica", "Helvetica-Bold", "Courier"


def _ascii_dashes(text: str) -> str:
    replacements = {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "--",
        "\u2212": "-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:[’'-][A-Za-z0-9]+)*", text))


def _parse_bibtex(text: str) -> dict[str, dict[str, str]]:
    """Parse the flat fields used by the checked-in bibliography."""

    entries: dict[str, dict[str, str]] = {}
    cursor = 0
    while True:
        match = re.search(r"@[A-Za-z]+\s*\{", text[cursor:])
        if match is None:
            break
        opening = cursor + match.end() - 1
        depth = 0
        closing = None
        for index in range(opening, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    closing = index
                    break
        if closing is None:
            raise ValueError("bibliography contains an unterminated entry")
        body = text[opening + 1 : closing]
        key, separator, fields_text = body.partition(",")
        key = key.strip()
        if not separator or not key or key in entries:
            raise ValueError("bibliography contains an empty or duplicate entry key")
        entries[key] = _parse_bibtex_fields(fields_text)
        cursor = closing + 1
    if not entries:
        raise ValueError("bibliography contains no entries")
    return entries


def _parse_bibtex_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    cursor = 0
    while cursor < len(text):
        match = re.search(r"([A-Za-z][A-Za-z0-9_-]*)\s*=\s*", text[cursor:])
        if match is None:
            break
        name = match.group(1).casefold()
        value_start = cursor + match.end()
        if value_start >= len(text):
            raise ValueError(f"bibliography field has no value: {name}")
        delimiter = text[value_start]
        if delimiter == "{":
            depth = 0
            value_end = None
            for index in range(value_start, len(text)):
                if text[index] == "{":
                    depth += 1
                elif text[index] == "}":
                    depth -= 1
                    if depth == 0:
                        value_end = index
                        break
            if value_end is None:
                raise ValueError(f"unterminated bibliography field: {name}")
            value = text[value_start + 1 : value_end]
            cursor = value_end + 1
        elif delimiter == '"':
            value_end = text.find('"', value_start + 1)
            if value_end < 0:
                raise ValueError(f"unterminated bibliography field: {name}")
            value = text[value_start + 1 : value_end]
            cursor = value_end + 1
        else:
            value_end = text.find(",", value_start)
            if value_end < 0:
                value_end = len(text)
            value = text[value_start:value_end]
            cursor = value_end + 1
        normalized = re.sub(r"[{}]", "", " ".join(value.split()))
        normalized = re.sub(r"\\(?:[\"'`^~=.Hckruv])\s*([A-Za-z])", r"\1", normalized)
        normalized = re.sub(r"\\[A-Za-z]+\s*", "", normalized)
        fields[name] = normalized.replace("\\", "")
    return fields


def _citation_order(markdown: str) -> tuple[list[str], dict[str, int]]:
    ordered: list[str] = []
    for group in re.findall(r"\[([^\]]*@[A-Za-z][^\]]*)\]", markdown):
        for key in re.findall(r"@([A-Za-z][A-Za-z0-9_:-]+)", group):
            if key not in ordered:
                ordered.append(key)
    return ordered, {key: index for index, key in enumerate(ordered, start=1)}


def _inline(text: str, citation_numbers: Mapping[str, int]) -> str:
    text = _ascii_dashes(text)
    text = text.replace(r"\tau", "tau").replace(r"\Delta", "Delta")
    text = re.sub(r"\\text\{([^{}]+)\}", r"\1", text)
    text = text.replace(r"\(", "").replace(r"\)", "")

    def citation(match: re.Match[str]) -> str:
        keys = re.findall(r"@([A-Za-z][A-Za-z0-9_:-]+)", match.group(1))
        numbers = [citation_numbers[key] for key in keys if key in citation_numbers]
        return "[" + ", ".join(str(item) for item in numbers) + "]"

    text = re.sub(r"\[([^\]]*@[A-Za-z][^\]]*)\]", citation, text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"[Figure: \1]", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1 (\2)", text)
    text = text.replace("`", "").replace("**", "").replace("__", "")
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)
    return html.escape(" ".join(text.split()), quote=False)


def _styles() -> tuple[dict[str, ParagraphStyle], tuple[str, str, str]]:
    regular, bold, mono = _register_fonts()
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "SmartValveTitle",
            parent=base["Title"],
            fontName=bold,
            fontSize=17,
            leading=21,
            alignment=TA_CENTER,
            spaceAfter=12,
            textColor=colors.HexColor("#123047"),
        ),
        "h2": ParagraphStyle(
            "SmartValveH2",
            parent=base["Heading1"],
            fontName=bold,
            fontSize=13,
            leading=16,
            spaceBefore=10,
            spaceAfter=6,
            textColor=colors.HexColor("#123047"),
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "SmartValveH3",
            parent=base["Heading2"],
            fontName=bold,
            fontSize=10.5,
            leading=13,
            spaceBefore=8,
            spaceAfter=4,
            textColor=colors.HexColor("#24556F"),
            keepWithNext=True,
        ),
        "h4": ParagraphStyle(
            "SmartValveH4",
            parent=base["Heading3"],
            fontName=bold,
            fontSize=9.4,
            leading=11.8,
            spaceBefore=7,
            spaceAfter=3,
            textColor=colors.HexColor("#263943"),
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "SmartValveBody",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=9.2,
            leading=12.3,
            alignment=TA_LEFT,
            spaceAfter=5,
            splitLongWords=True,
        ),
        "list": ParagraphStyle(
            "SmartValveList",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=9.1,
            leading=12,
            leftIndent=14,
            firstLineIndent=-10,
            alignment=TA_LEFT,
            spaceAfter=3,
        ),
        "quote": ParagraphStyle(
            "SmartValveQuote",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=8.8,
            leading=11.5,
            leftIndent=14,
            rightIndent=14,
            borderColor=colors.HexColor("#9DB3C1"),
            borderWidth=0.8,
            borderPadding=6,
            backColor=colors.HexColor("#F4F7F9"),
            textColor=colors.HexColor("#3B4A54"),
            spaceAfter=6,
        ),
        "code": ParagraphStyle(
            "SmartValveCode",
            parent=base["Code"],
            fontName=mono,
            fontSize=7.2,
            leading=9.2,
            leftIndent=8,
            rightIndent=8,
            borderColor=colors.HexColor("#D5DCE0"),
            borderWidth=0.5,
            borderPadding=5,
            backColor=colors.HexColor("#F7F8F9"),
            spaceAfter=6,
        ),
        "reference": ParagraphStyle(
            "SmartValveReference",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=7.7,
            leading=10.2,
            leftIndent=15,
            firstLineIndent=-15,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "table": ParagraphStyle(
            "SmartValveTable",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=6.2,
            leading=7.8,
            alignment=TA_LEFT,
        ),
        "table_header": ParagraphStyle(
            "SmartValveTableHeader",
            parent=base["BodyText"],
            fontName=bold,
            fontSize=6.2,
            leading=7.8,
            alignment=TA_LEFT,
            textColor=colors.white,
        ),
    }
    return styles, (regular, bold, mono)


def _markdown_table(
    lines: list[str],
    *,
    styles: Mapping[str, ParagraphStyle],
    citation_numbers: Mapping[str, int],
    available_width: float,
) -> LongTable:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    if len(rows) > 1 and all(re.fullmatch(r":?-{3,}:?", item) for item in rows[1]):
        rows.pop(1)
    column_count = max(len(row) for row in rows)
    for row in rows:
        row.extend([""] * (column_count - len(row)))
    rendered = []
    for row_index, row in enumerate(rows):
        style = styles["table_header"] if row_index == 0 else styles["table"]
        rendered.append([Paragraph(_inline(cell, citation_numbers), style) for cell in row])
    table = LongTable(
        rendered,
        colWidths=[available_width / column_count] * column_count,
        repeatRows=1,
        hAlign="LEFT",
    )
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#24556F")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#8EA5B2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for row_index in range(1, len(rendered)):
        if row_index % 2 == 0:
            commands.append(
                ("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#F3F6F8"))
            )
    table.setStyle(TableStyle(commands))
    return table


def _reference_text(number: int, key: str, fields: Mapping[str, str]) -> str:
    authors = fields.get("author", "Unknown author").replace(" and ", "; ")
    title = fields.get("title", "Untitled")
    venue = fields.get("journal") or fields.get("booktitle") or fields.get("publisher", "")
    year = fields.get("year", "n.d.")
    volume = fields.get("volume", "")
    pages = fields.get("pages", "")
    doi = fields.get("doi", "")
    parts = [f"[{number}] {authors}. {title}."]
    if venue:
        parts.append(
            venue
            + (f" {volume}" if volume else "")
            + (f":{pages}" if pages else "")
            + "."
        )
    parts.append(f"{year}.")
    if doi:
        parts.append(f"https://doi.org/{doi.removeprefix('https://doi.org/')}")
    return " ".join(parts)


def _story(
    markdown: str,
    bibliography: Mapping[str, Mapping[str, str]],
    *,
    styles: Mapping[str, ParagraphStyle],
    available_width: float,
) -> tuple[list[Any], list[str]]:
    citation_order, citation_numbers = _citation_order(markdown)
    missing = [key for key in citation_order if key not in bibliography]
    if missing:
        raise ValueError(f"manuscript citations lack bibliography entries: {missing}")
    cleaned = _strip_comments(markdown)
    lines = cleaned.splitlines()
    flowables: list[Any] = []
    paragraph_lines: list[str] = []
    code_lines: list[str] = []
    in_code = False

    def flush_paragraph() -> None:
        if paragraph_lines:
            value = _inline(" ".join(paragraph_lines), citation_numbers)
            if value:
                flowables.append(Paragraph(value, styles["body"]))
            paragraph_lines.clear()

    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if line.strip().startswith("```"):
            flush_paragraph()
            if in_code:
                flowables.append(Preformatted(_ascii_dashes("\n".join(code_lines)), styles["code"]))
                code_lines.clear()
            in_code = not in_code
            index += 1
            continue
        if in_code:
            code_lines.append(line)
            index += 1
            continue
        if not line.strip():
            flush_paragraph()
            index += 1
            continue
        if line.startswith("# "):
            flush_paragraph()
            flowables.append(Paragraph(_inline(line[2:], citation_numbers), styles["title"]))
            index += 1
            continue
        if line.startswith("#### "):
            flush_paragraph()
            flowables.append(Spacer(1, 5))
            flowables.append(Paragraph(_inline(line[5:], citation_numbers), styles["h4"]))
            index += 1
            continue
        if line.startswith("### "):
            flush_paragraph()
            flowables.append(Spacer(1, 5))
            flowables.append(Paragraph(_inline(line[4:], citation_numbers), styles["h3"]))
            index += 1
            continue
        if line.startswith("## "):
            flush_paragraph()
            flowables.append(Spacer(1, 6))
            flowables.append(Paragraph(_inline(line[3:], citation_numbers), styles["h2"]))
            index += 1
            continue
        if line.strip().startswith("|"):
            flush_paragraph()
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index])
                index += 1
            flowables.append(
                KeepTogether(
                    [
                        _markdown_table(
                            table_lines,
                            styles=styles,
                            citation_numbers=citation_numbers,
                            available_width=available_width,
                        ),
                        Spacer(1, 6),
                    ]
                )
            )
            continue
        if line.startswith("> "):
            flush_paragraph()
            quote_lines = []
            while index < len(lines) and lines[index].startswith("> "):
                quote_lines.append(lines[index][2:])
                index += 1
            flowables.append(
                Paragraph(_inline(" ".join(quote_lines), citation_numbers), styles["quote"])
            )
            continue
        list_match = re.match(r"^\s*(?:([-*])|(\d+)\.)\s+(.+)$", line)
        if list_match:
            flush_paragraph()
            bullet = "•" if list_match.group(1) else f"{list_match.group(2)}."
            item_lines = [list_match.group(3)]
            index += 1
            while index < len(lines):
                continuation = lines[index].rstrip()
                if not re.match(r"^\s{2,}\S", continuation):
                    break
                item_lines.append(continuation.strip())
                index += 1
            flowables.append(
                Paragraph(
                    f"{html.escape(bullet)} &nbsp;"
                    f"{_inline(' '.join(item_lines), citation_numbers)}",
                    styles["list"],
                )
            )
            continue
        if re.fullmatch(r"\s*[-*_]{3,}\s*", line):
            flush_paragraph()
            flowables.append(Spacer(1, 5))
            index += 1
            continue
        paragraph_lines.append(line.strip())
        index += 1
    flush_paragraph()
    if in_code:
        raise ValueError("manuscript contains an unterminated code fence")
    flowables.append(PageBreak())
    flowables.append(Paragraph("References", styles["h2"]))
    for key in citation_order:
        number = citation_numbers[key]
        flowables.append(
            KeepTogether(
                [
                    Paragraph(
                        _inline(_reference_text(number, key, bibliography[key]), {}),
                        styles["reference"],
                    )
                ]
            )
        )
        flowables.append(Spacer(1, 3))
    return flowables, citation_order


class _InvariantCanvas(canvas.Canvas):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["invariant"] = 1
        super().__init__(*args, **kwargs)


def _page_decorator(*, working_preflight: bool, short_title: str, regular_font: str):
    def draw_page(page_canvas: canvas.Canvas, document: BaseDocTemplate) -> None:
        width, height = A4
        page_canvas.saveState()
        page_canvas.setFont(regular_font, 7.2)
        page_canvas.setFillColor(colors.HexColor("#5A6870"))
        page_canvas.drawString(18 * mm, height - 12 * mm, _ascii_dashes(short_title))
        page_canvas.drawRightString(width - 18 * mm, 10 * mm, f"Page {document.page}")
        page_canvas.setStrokeColor(colors.HexColor("#D2DADF"))
        page_canvas.setLineWidth(0.35)
        page_canvas.line(18 * mm, height - 14 * mm, width - 18 * mm, height - 14 * mm)
        if working_preflight:
            page_canvas.setFillColor(colors.Color(0.75, 0.12, 0.12, alpha=0.10))
            page_canvas.setFont(regular_font, 34)
            page_canvas.translate(width / 2, height / 2)
            page_canvas.rotate(36)
            page_canvas.drawCentredString(0, 0, "WORKING PREFLIGHT - NOT FOR SUBMISSION")
        page_canvas.restoreState()

    return draw_page


def _append_figure_pdfs(base_pdf: Path, figure_pdfs: Iterable[Path], output_pdf: Path) -> None:
    writer = PdfWriter()
    writer.append(str(base_pdf))
    for figure_path in figure_pdfs:
        reader = PdfReader(figure_path.resolve(strict=True))
        if len(reader.pages) != 1:
            raise ValueError(f"main figure PDF must contain exactly one page: {figure_path}")
        writer.add_page(reader.pages[0])
    writer.add_metadata(
        {
            "/Title": "Physical Access Changes Estimated Bearing-Diagnosis Reliability",
            "/Producer": RENDERER_VERSION,
            "/CreationDate": "D:20000101000000Z",
            "/ModDate": "D:20000101000000Z",
        }
    )
    with output_pdf.open("wb") as handle:
        writer.write(handle)


def render_ress_pdf(
    *,
    manuscript_path: Path,
    bibliography_path: Path,
    output_path: Path,
    report_path: Path,
    figure_pdfs: Iterable[Path] = (),
    working_preflight: bool = False,
) -> dict[str, Any]:
    """Render Markdown and BibTeX to a deterministic PDF with strict final-mode holds."""

    manuscript_path = manuscript_path.resolve(strict=True)
    bibliography_path = bibliography_path.resolve(strict=True)
    output_path = output_path.resolve()
    report_path = report_path.resolve()
    figures = [path.resolve(strict=True) for path in figure_pdfs]
    figure_hashes = [sha256_file(path) for path in figures]
    if len(set(figures)) != len(figures):
        raise ValueError("RESS PDF figure paths must be unique")
    if len(set(figure_hashes)) != len(figure_hashes):
        raise ValueError("RESS PDF figure contents must be unique")
    if output_path.exists() or report_path.exists():
        raise ValueError("RESS PDF output or report already exists")
    if output_path.suffix.casefold() != ".pdf":
        raise ValueError("RESS PDF output must use the .pdf extension")
    manuscript = manuscript_path.read_text(encoding="utf-8")
    bibliography_text = bibliography_path.read_text(encoding="utf-8")
    final_markers = [
        marker
        for marker in FORBIDDEN_FINAL_MARKERS
        if marker.casefold() in manuscript.casefold()
    ]
    if not working_preflight and final_markers:
        raise ValueError(f"final RESS PDF manuscript contains forbidden markers: {final_markers}")
    if not working_preflight and len(figures) != EXPECTED_MAIN_FIGURE_COUNT:
        raise ValueError(
            f"final RESS PDF requires {EXPECTED_MAIN_FIGURE_COUNT} one-page main figures"
        )
    title_match = re.search(r"(?m)^# (?!#)([^\n]+)$", manuscript)
    if title_match is None:
        raise ValueError("RESS PDF manuscript has no H1 title")
    bibliography = _parse_bibtex(bibliography_text)
    styles, fonts = _styles()
    left = right = 18 * mm
    top = 20 * mm
    bottom = 22 * mm
    width, height = A4
    available_width = width - left - right
    story, cited_keys = _story(
        manuscript,
        bibliography,
        styles=styles,
        available_width=available_width,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    base_pdf = output_path.with_suffix(".base.pdf") if figures else output_path
    document = BaseDocTemplate(
        str(base_pdf),
        pagesize=A4,
        leftMargin=left,
        rightMargin=right,
        topMargin=top,
        bottomMargin=bottom,
        title=_ascii_dashes(title_match.group(1)),
        author="SmartValve-AI-Twin authors",
        subject="RESS manuscript visual preflight",
    )
    frame = Frame(left, bottom, available_width, height - top - bottom, id="body")
    document.addPageTemplates(
        [
            PageTemplate(
                id="main",
                frames=[frame],
                onPage=_page_decorator(
                    working_preflight=working_preflight,
                    short_title="SmartValve bearing access audit - manuscript preflight",
                    regular_font=fonts[0],
                ),
            )
        ]
    )
    document.build(story, canvasmaker=_InvariantCanvas)
    if figures:
        _append_figure_pdfs(base_pdf, figures, output_path)
        base_pdf.unlink()

    reader = PdfReader(output_path)
    page_text = [(page.extract_text() or "").strip() for page in reader.pages]
    blank_pages = [index + 1 for index, value in enumerate(page_text) if not value]
    if blank_pages:
        raise ValueError(f"RESS PDF contains pages without extractable text: {blank_pages}")
    expected_pages = len(reader.pages)
    if expected_pages < 5:
        raise ValueError("RESS PDF unexpectedly contains fewer than five pages")
    page_sizes = {
        (
            round(float(page.mediabox.width), 3),
            round(float(page.mediabox.height), 3),
        )
        for page in reader.pages[: expected_pages - len(figures)]
    }
    if page_sizes != {(round(A4[0], 3), round(A4[1], 3))}:
        raise ValueError("RESS manuscript PDF pages do not share the A4 page size")
    report = {
        "status": (
            "rendered_working_visual_preflight"
            if working_preflight
            else "rendered_final_machine_pdf"
        ),
        "renderer_version": RENDERER_VERSION,
        "manuscript_path": manuscript_path.as_posix(),
        "manuscript_sha256": sha256_file(manuscript_path),
        "bibliography_path": bibliography_path.as_posix(),
        "bibliography_sha256": sha256_file(bibliography_path),
        "output_path": output_path.as_posix(),
        "output_sha256": sha256_file(output_path),
        "output_bytes": output_path.stat().st_size,
        "page_count": expected_pages,
        "blank_page_count": 0,
        "manuscript_word_count": _word_count(manuscript),
        "cited_reference_count": len(cited_keys),
        "bibliography_entry_count": len(bibliography),
        "main_figure_pdf_count": len(figures),
        "main_figure_pdfs": [
            {
                "order": index,
                "path": path.as_posix(),
                "sha256": digest,
                "bytes": path.stat().st_size,
            }
            for index, (path, digest) in enumerate(
                zip(figures, figure_hashes, strict=True),
                start=1,
            )
        ],
        "working_preflight_watermark": working_preflight,
        "forbidden_final_marker_count": len(final_markers),
        "machine_render_complete": (
            not working_preflight and len(figures) == EXPECTED_MAIN_FIGURE_COUNT
        ),
        "human_visual_review_complete": False,
        "submission_ready": False,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
