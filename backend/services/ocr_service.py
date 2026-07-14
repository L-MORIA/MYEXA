import logging
import os
import PyPDF2
from PIL import Image
import pytesseract
from config import Config
from typing import Dict

logger = logging.getLogger(__name__)


class OCRService:
    def __init__(self):
        self.tesseract_path = Config.TESSERACT_PATH
        if self.tesseract_path != "tesseract":
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path

    def extract_from_pdf(self, file_path: str) -> Dict:
        try:
            text = self._extract_pdf_text(file_path)
            if text.strip():
                return {"text": text, "confidence": 0.95, "method": "PyPDF2", "success": True}
        except Exception as e:
            logger.warning("PyPDF2 extraction failed, falling back to OCR: %s", e)

        try:
            text = self._extract_pdf_ocr(file_path)
            return {"text": text, "confidence": 0.85, "method": "Tesseract", "success": True}
        except Exception as e:
            logger.error("PDF OCR failed: %s", e)
            return {"text": "", "confidence": 0.0, "method": "Failed", "success": False, "error": str(e)}

    def _extract_pdf_text(self, file_path: str) -> str:
        text = ""
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text()
        return text

    def _extract_pdf_ocr(self, file_path: str) -> str:
        from pdf2image import convert_from_path

        images = convert_from_path(file_path)
        text = ""
        for image in images:
            text += pytesseract.image_to_string(image)
        return text

    def extract_from_image(self, file_path: str, language: str = "eng") -> Dict:
        try:
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image, lang=language)
            return {"text": text, "confidence": 0.85, "method": "Tesseract", "success": True}
        except Exception as e:
            logger.error("Image OCR error: %s", e)
            return {"text": "", "confidence": 0.0, "method": "Failed", "success": False, "error": str(e)}

    def process_file(self, file_path: str, language: str = "eng") -> Dict:
        if not os.path.exists(file_path):
            return {"text": "", "confidence": 0.0, "method": "Failed", "success": False, "error": "File not found"}

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            return self.extract_from_pdf(file_path)
        if ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff"):
            return self.extract_from_image(file_path, language)
        return {"text": "", "confidence": 0.0, "method": "Failed", "success": False, "error": f"Unsupported format: {ext}"}
