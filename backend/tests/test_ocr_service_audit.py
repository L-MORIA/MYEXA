"""Tests for backend.services.ocr_service.OCRService.

Focus: PDF page limit (DoS guard) and None-safe text extraction.
No Tesseract/Poppler binaries are required — rendering paths are mocked.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import PyPDF2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from services.ocr_service import OCRService


def _make_blank_pdf(path, pages: int):
    writer = PyPDF2.PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    with open(path, "wb") as f:
        writer.write(f)


@pytest.fixture()
def svc():
    return OCRService()


class TestPageLimit:
    def test_pdf_over_limit_is_rejected(self, svc, tmp_path, monkeypatch):
        monkeypatch.setattr(Config, "MAX_PDF_PAGES", 2)
        pdf = tmp_path / "big.pdf"
        _make_blank_pdf(pdf, pages=3)

        result = svc.extract_from_pdf(str(pdf))
        assert result["success"] is False
        assert "too many pages" in result["error"]
        assert "3" in result["error"]

    def test_pdf_within_limit_is_processed(self, svc, tmp_path, monkeypatch):
        monkeypatch.setattr(Config, "MAX_PDF_PAGES", 5)
        pdf = tmp_path / "small.pdf"
        _make_blank_pdf(pdf, pages=2)

        # Blank pages have no text, so the service falls back to the OCR
        # branch; patch it so no Poppler/Tesseract is needed.
        with patch.object(svc, "_extract_pdf_ocr", return_value="rendered text"):
            result = svc.extract_from_pdf(str(pdf))
        assert result["success"] is True
        assert result["text"] == "rendered text"

    def test_page_count(self, svc, tmp_path):
        pdf = tmp_path / "p.pdf"
        _make_blank_pdf(pdf, pages=4)
        assert svc._page_count(str(pdf)) == 4


class TestTextExtraction:
    def test_extract_pdf_text_tolerates_none_pages(self, svc, tmp_path):
        """PyPDF2's extract_text() can return None — must not crash on +=."""
        pdf = tmp_path / "blank.pdf"
        _make_blank_pdf(pdf, pages=1)

        with patch("services.ocr_service.PyPDF2.PdfReader") as mock_reader:
            page = MagicMock()
            page.extract_text.return_value = None
            mock_reader.return_value.pages = [page, page]
            text = svc._extract_pdf_text(str(pdf))

        assert text == ""

    def test_process_file_missing_file(self, svc):
        result = svc.process_file("Z:/definitely/missing/file.pdf")
        assert result["success"] is False
        assert result["error"] == "File not found"

    def test_process_file_unsupported_extension(self, svc, tmp_path):
        f = tmp_path / "file.docx"
        f.write_text("x")
        result = svc.process_file(str(f))
        assert result["success"] is False
        assert "Unsupported format" in result["error"]
