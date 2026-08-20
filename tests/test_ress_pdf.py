from __future__ import annotations

import json
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from smartvalve.experiments.ress_pdf import (
    _story,
    _styles,
    render_ress_pdf,
    sha256_file,
)


def _fixture(root: Path, *, final: bool = False) -> tuple[Path, Path]:
    manuscript = root / "manuscript.md"
    marker = "" if final else "> Working manuscript - raw sensitivity in progress.\n\n"
    manuscript.write_text(
        "# Physical Access Changes Estimated Reliability\n\n"
        + marker
        + "## Abstract\n\n"
        + " ".join("evidence" for _ in range(150))
        + "\n\n## 1. Introduction\n\n"
        + "Bearing access changes the deployment estimate [@First; @Second]. " * 260
        + "\n\n### 1.1 Physical units\n\n"
        + "1. Hold out each physical bearing\n"
        + "   across all operating settings.\n"
        + "2. Quarantine both partial-access arms.\n\n"
        + "| Protocol | Identity | Setting |\n"
        + "|---|---|---|\n"
        + "| Random | shared | shared |\n"
        + "| Crossed | unseen | unseen |\n\n"
        + "## 2. Results\n\n"
        + "The paired interval remains positive [@First]. " * 260
        + "\n\n## 3. Discussion\n\n"
        + "The estimand is deployment-specific. " * 260
        + "\n\n## 4. Conclusion\n\nThe protocol changes the reported reliability.\n",
        encoding="utf-8",
    )
    bibliography = root / "references.bib"
    bibliography.write_text(
        "@article{First, author={A. Author and B. Author}, title={First evidence}, "
        "journal={Reliability Journal}, year={2025}, doi={10.1000/first}}\n"
        "@article{Second, author={C. Author}, title={Second evidence}, "
        "journal={Signal Journal}, year={2026}, doi={10.1000/second}}\n",
        encoding="utf-8",
    )
    return manuscript, bibliography


def test_working_pdf_is_deterministic_and_machine_checked(tmp_path: Path) -> None:
    manuscript, bibliography = _fixture(tmp_path)
    reports = []
    for index in (1, 2):
        output = tmp_path / f"working-{index}.pdf"
        report_path = tmp_path / f"working-{index}.json"
        reports.append(
            render_ress_pdf(
                manuscript_path=manuscript,
                bibliography_path=bibliography,
                output_path=output,
                report_path=report_path,
                working_preflight=True,
            )
        )
        assert json.loads(report_path.read_text(encoding="utf-8")) == reports[-1]
    assert reports[0]["output_sha256"] == reports[1]["output_sha256"]
    assert sha256_file(tmp_path / "working-1.pdf") == sha256_file(
        tmp_path / "working-2.pdf"
    )
    assert reports[0]["page_count"] >= 5
    assert reports[0]["blank_page_count"] == 0
    assert reports[0]["cited_reference_count"] == 2
    assert reports[0]["working_preflight_watermark"] is True
    assert reports[0]["submission_ready"] is False


def test_multiline_list_continuation_remains_in_the_list_item() -> None:
    styles, _ = _styles()
    story, _ = _story(
        "# Title\n\n1. First line\n   continued phrase\n2. Second item\n",
        {},
        styles=styles,
        available_width=160,
    )
    list_items = [
        item
        for item in story
        if getattr(getattr(item, "style", None), "name", "") == "SmartValveList"
    ]
    assert len(list_items) == 2
    assert "First line continued phrase" in list_items[0].getPlainText()


def test_final_pdf_rejects_working_markers(tmp_path: Path) -> None:
    manuscript, bibliography = _fixture(tmp_path)
    with pytest.raises(ValueError, match="forbidden markers"):
        render_ress_pdf(
            manuscript_path=manuscript,
            bibliography_path=bibliography,
            output_path=tmp_path / "final.pdf",
            report_path=tmp_path / "final.json",
        )


def test_final_pdf_requires_all_five_figure_pdfs(tmp_path: Path) -> None:
    manuscript, bibliography = _fixture(tmp_path, final=True)
    with pytest.raises(ValueError, match="requires 5 one-page main figures"):
        render_ress_pdf(
            manuscript_path=manuscript,
            bibliography_path=bibliography,
            output_path=tmp_path / "final.pdf",
            report_path=tmp_path / "final.json",
        )


def test_final_pdf_with_five_figures_is_deterministic_and_machine_complete(
    tmp_path: Path,
) -> None:
    manuscript, bibliography = _fixture(tmp_path, final=True)
    figures = []
    for index in range(1, 6):
        figure = tmp_path / f"figure-{index}.pdf"
        figure_canvas = canvas.Canvas(str(figure), pagesize=A4, invariant=1)
        figure_canvas.drawString(72, 760, f"Deterministic test figure {index}")
        figure_canvas.showPage()
        figure_canvas.save()
        figures.append(figure)

    reports = []
    for index in (1, 2):
        output = tmp_path / f"final-{index}.pdf"
        report_path = tmp_path / f"final-{index}.json"
        reports.append(
            render_ress_pdf(
                manuscript_path=manuscript,
                bibliography_path=bibliography,
                output_path=output,
                report_path=report_path,
                figure_pdfs=figures,
            )
        )
    assert reports[0]["output_sha256"] == reports[1]["output_sha256"]
    assert reports[0]["main_figure_pdf_count"] == 5
    assert reports[0]["main_figure_pdfs"] == [
        {
            "order": index,
            "path": figure.resolve().as_posix(),
            "sha256": sha256_file(figure),
            "bytes": figure.stat().st_size,
        }
        for index, figure in enumerate(figures, start=1)
    ]
    assert reports[0]["page_count"] >= 10
    assert reports[0]["machine_render_complete"] is True
    assert reports[0]["working_preflight_watermark"] is False
    assert reports[0]["human_visual_review_complete"] is False
    assert reports[0]["submission_ready"] is False


def test_final_pdf_rejects_duplicate_figure_path(tmp_path: Path) -> None:
    manuscript, bibliography = _fixture(tmp_path, final=True)
    figure = tmp_path / "figure.pdf"
    figure_canvas = canvas.Canvas(str(figure), pagesize=A4, invariant=1)
    figure_canvas.drawString(72, 760, "Repeated figure")
    figure_canvas.showPage()
    figure_canvas.save()

    with pytest.raises(ValueError, match="figure paths must be unique"):
        render_ress_pdf(
            manuscript_path=manuscript,
            bibliography_path=bibliography,
            output_path=tmp_path / "final.pdf",
            report_path=tmp_path / "final.json",
            figure_pdfs=[figure] * 5,
        )


def test_final_pdf_rejects_duplicate_figure_content(tmp_path: Path) -> None:
    manuscript, bibliography = _fixture(tmp_path, final=True)
    first = tmp_path / "figure-1.pdf"
    figure_canvas = canvas.Canvas(str(first), pagesize=A4, invariant=1)
    figure_canvas.drawString(72, 760, "Repeated figure bytes")
    figure_canvas.showPage()
    figure_canvas.save()
    figures = [first]
    for index in range(2, 6):
        figure = tmp_path / f"figure-{index}.pdf"
        figure.write_bytes(first.read_bytes())
        figures.append(figure)

    with pytest.raises(ValueError, match="figure contents must be unique"):
        render_ress_pdf(
            manuscript_path=manuscript,
            bibliography_path=bibliography,
            output_path=tmp_path / "final.pdf",
            report_path=tmp_path / "final.json",
            figure_pdfs=figures,
        )
