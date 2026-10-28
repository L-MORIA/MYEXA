"""Tests for backend.services.ocr_service.OCRService.

All external dependencies (PyPDF2, PIL, pytesseract, pdf2image) are mocked so
the tests never touch the filesystem or spawn Tesseract.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.ocr_service import OCRService  # noqa: E402


@pytest.fixture()
def svc():
    return OCRService()


class TestProcessFile:
    def test_missing_file(self, svc):
        result = svc.process_file("/definitely/not/here.pdf", "eng")
        assert result["success"] is False
        assert result["text"] == ""
        assert result["error"] == "File not found"

    def test_unsupported_format(self, svc, tmp_path):
        f = tmp_path / "doc.docx"
        f.write_bytes(b"x")
        result = svc.process_file(str(f), "eng")
        assert result["success"] is False
        assert "Unsupported format" in result["error"]

    def test_pdf_dispatched_to_pdf_extraction(self, svc, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4")
        with patch.object(svc, "extract_from_pdf", return_value={"text": "x", "success": True}) as m:
            svc.process_file(str(f), "eng")
        m.assert_called_once()

    def test_image_dispatched_to_image_extraction(self, svc, tmp_path):
        f = tmp_path / "img.png"
        f.write_bytes(b"\x89PNG")
        with patch.object(svc, "extract_from_image", return_value={"text": "x", "success": True}) as m:
            svc.process_file(str(f), "rus")
        m.assert_called_once_with(str(f), "rus")


class TestExtractFromPdf:
    def test_uses_pyPDF2_when_text_present(self, svc, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF")
        with patch.object(svc, "_extract_pdf_text", return_value="Extracted text"):
            result = svc.extract_from_pdf(str(f))
        assert result["success"] is True
        assert result["method"] == "PyPDF2"
        assert result["text"] == "Extracted text"

    def test_falls_back_to_ocr_when_text_empty(self, svc, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF")
        with patch.object(svc, "_extract_pdf_text", return_value="   "):
            with patch.object(svc, "_extract_pdf_ocr", return_value="OCR text"):
                result = svc.extract_from_pdf(str(f))
        assert result["method"] == "Tesseract"
        assert result["text"] == "OCR text"

    def test_falls_back_to_ocr_when_pypdf2_raises(self, svc, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF")
        with patch.object(svc, "_extract_pdf_text", side_effect=RuntimeError("corrupt")):
            with patch.object(svc, "_extract_pdf_ocr", return_value="OCR text"):
                result = svc.extract_from_pdf(str(f))
        assert result["success"] is True
        assert result["method"] == "Tesseract"

    def test_returns_failure_when_both_fail(self, svc, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF")
        with patch.object(svc, "_extract_pdf_text", side_effect=RuntimeError("corrupt")):
            with patch.object(svc, "_extract_pdf_ocr", side_effect=RuntimeError("no poppler")):
                result = svc.extract_from_pdf(str(f))
        assert result["success"] is False
        assert result["method"] == "Failed"
        assert result["error"]


class TestExtractFromImage:
    def test_returns_ocr_text(self, svc, tmp_path):
        f = tmp_path / "img.png"
        f.write_bytes(b"\x89PNG")
        with patch("services.ocr_service.Image.open", return_value=MagicMock()):
            with patch("services.ocr_service.pytesseract.image_to_string", return_value="IMG TEXT"):
                result = svc.extract_from_image(str(f), "eng")
        assert result["success"] is True
        assert result["text"] == "IMG TEXT"
        assert result["method"] == "Tesseract"

    def test_passes_language_through(self, svc, tmp_path):
        f = tmp_path / "img.png"
        f.write_bytes(b"\x89PNG")
        with patch("services.ocr_service.Image.open", return_value=MagicMock()):
            with patch("services.ocr_service.pytesseract.image_to_string", return_value="T") as m:
                svc.extract_from_image(str(f), "rus")
        assert m.call_args.kwargs.get("lang") == "rus"

    def test_returns_failure_on_error(self, svc, tmp_path):
        f = tmp_path / "img.png"
        f.write_bytes(b"\x89PNG")
        with patch("services.ocr_service.Image.open", return_value=MagicMock()):
            with patch("services.ocr_service.pytesseract.image_to_string", side_effect=RuntimeError("no tesseract")):
                result = svc.extract_from_image(str(f), "eng")
        assert result["success"] is False
        assert result["error"]

    def test_returns_failure_on_unreadable_image(self, svc, tmp_path):
        f = tmp_path / "img.png"
        f.write_bytes(b"not-an-image")
        with patch("services.ocr_service.Image.open", side_effect=RuntimeError("cannot identify")):
            result = svc.extract_from_image(str(f), "eng")
        assert result["success"] is False


class TestInit:
    def test_custom_tesseract_path_is_applied(self):
        with patch("services.ocr_service.Config.TESSERACT_PATH", "C:/tesseract/tesseract.exe"):
            with patch("services.ocr_service.pytesseract") as mock_pt:
                OCRService()
                assert mock_pt.pytesseract.tesseract_cmd == "C:/tesseract/tesseract.exe"

    def test_default_path_leaves_cmd_untouched(self):
        with patch("services.ocr_service.Config.TESSERACT_PATH", "tesseract"):
            with patch("services.ocr_service.pytesseract") as mock_pt:
                OCRService()
                assert mock_pt.pytesseract.tesseract_cmd.__class__ is not str


class TestOcrLanguage:
    """The requested language has to reach Tesseract.

    The PDF branch used to call image_to_string() without the language, so a
    Russian scan was read with the default English model and came out as
    garbage.
    """

    def test_pdf_path_forwards_the_language(self, svc):
        with patch.object(svc, "_page_count", return_value=1):
            with patch.object(svc, "_extract_pdf_text", return_value=""):
                with patch.object(svc, "_extract_pdf_ocr", return_value="Привет") as mock_ocr:
                    result = svc.extract_from_pdf("scan.pdf", "rus")

        assert result["success"] is True
        assert mock_ocr.call_args.args[1] == "rus"

    def test_process_file_forwards_the_language_to_the_pdf_branch(self, svc, tmp_path):
        pdf = tmp_path / "scan.pdf"
        pdf.write_bytes(b"%PDF")

        with patch.object(svc, "extract_from_pdf", return_value={"text": "", "success": True}) as mock_pdf:
            svc.process_file(str(pdf), "rus")

        assert mock_pdf.call_args.args[1] == "rus"

    def test_image_to_string_is_called_with_the_language(self, svc, tmp_path):
        image = tmp_path / "scan.png"
        image.write_bytes(b"PNG")

        with patch("services.ocr_service.Image.open", return_value=MagicMock()):
            with patch("services.ocr_service.pytesseract.image_to_string",
                       return_value="Привет") as mock_ocr:
                svc.extract_from_image(str(image), "rus")

        assert mock_ocr.call_args.kwargs["lang"] == "rus"
