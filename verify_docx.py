from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from job_app_helper.utils.docx_utils import markdown_to_docx

WORKDIR = Path(__file__).resolve().parent
SAMPLE_RESUME = WORKDIR / "resumes" / "default_resume.md"
TMP_DIR = WORKDIR / "tmp" / "docs"


def _read_docx_xml(docx_path: Path) -> tuple[bytes, bytes]:
    with zipfile.ZipFile(docx_path) as archive:
        document_xml = archive.read("word/document.xml")
        rels_xml = archive.read("word/_rels/document.xml.rels")
    return document_xml, rels_xml


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_conversion() -> None:
    markdown = SAMPLE_RESUME.read_text(encoding="utf-8")
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    output_path = TMP_DIR / "resume.docx"
    markdown_to_docx(markdown, str(output_path))

    _assert(output_path.exists(), "DOCX file was not created.")

    document_xml, rels_xml = _read_docx_xml(output_path)
    document_root = ET.fromstring(document_xml)
    rels_root = ET.fromstring(rels_xml)

    text_content = "".join(
        node.text or ""
        for node in document_root.iter()
        if node.tag.endswith("}t")
    )
    hyperlink_targets = [
        node.attrib.get("Target", "")
        for node in rels_root.iter()
        if node.tag.endswith("}Relationship")
    ]

    _assert("Ari Wahyudi" in text_content, "Header name was not rendered.")
    _assert("Senior Data Analyst" in text_content, "Header title was not rendered.")
    _assert(
        "PROFESSIONAL EXPERIENCE" in text_content,
        "Expected section heading missing from DOCX.",
    )
    _assert(
        any("linkedin.com" in target for target in hyperlink_targets),
        "LinkedIn hyperlink was not embedded in the DOCX.",
    )

    print("DOCX verification passed.")


if __name__ == "__main__":
    test_conversion()
