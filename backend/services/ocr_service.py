import PyPDF2
from PIL import Image
import pytesseract
from config import Config
from typing import Dict
import os
import logging

logger = logging.getLogger(__name__)

class OCRService:
    def __init__(self):
        self.tesseract_path = Config.TESSERACT_PATH
        if self.tesseract_path != "tesseract":
            pytesseract.pytesseract.pytesseract_cmd = self.tesseract_path
    
    def extract_from_pdf(self, file_path: str) -> Dict:
        """Extract text from PDF using PyPDF2, fallback to Tesseract"""
        try:
            # Try PyPDF2 first
            text = self._extract_pdf_text(file_path)
            if text.strip():
                return {
                    "text": text,
                    "confidence": 0.95,
                    "method": "PyPDF2",
                    "success": True
                }
        except Exception as e:
            logger.error(f"PyPDF2 error: {e}")
        
        # Fallback to Tesseract
        try:
            text = self._extract_pdf_ocr(file_path)
            return {
                "text": text,
                "confidence": 0.85,
                "method": "Tesseract",
                "success": True
            }
        except Exception as e:
            logger.error(f"Tesseract error: {e}")
            return {
                "text": "",
                "confidence": 0.0,
                "method": "Failed",
                "success": False
            }
    
    def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text from PDF using PyPDF2"""
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text()
        return text
    
    def _extract_pdf_ocr(self, file_path: str) -> str:
        """Extract text from PDF using Tesseract OCR"""
        from pdf2image import convert_from_path
        
        images = convert_from_path(file_path)
        text = ""
        for image in images:
            text += pytesseract.image_to_string(image)
        return text
    
    def extract_from_image(self, file_path: str, language: str = "eng") -> Dict:
        """Extract text from image using Tesseract"""
        try:
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image, lang=language)
            
            return {
                "text": text,
                "confidence": 0.85,
                "method": "Tesseract",
                "success": True
            }
        except Exception as e:
            logger.error(f"Image OCR error: {e}")
            return {
                "text": "",
                "confidence": 0.0,
                "method": "Failed",
                "success": False
            }
    
    def process_file(self, file_path: str, language: str = "eng") -> Dict:
        """Process file (PDF or image) and extract text"""
        if not os.path.exists(file_path):
            return {
                "text": "",
                "confidence": 0.0,
                "method": "Failed",
                "success": False,
                "error": "File not found"
            }
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == ".pdf":
            return self.extract_from_pdf(file_path)
        elif file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
            return self.extract_from_image(file_path, language)
        else:
            return {
                "text": "",
                "confidence": 0.0,
                "method": "Failed",
                "success": False,
                "error": f"Unsupported file type: {file_ext}"
            }
