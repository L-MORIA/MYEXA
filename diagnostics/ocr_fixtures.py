"""Generate OCR test files: a text-layer PDF, an image and an image-only PDF.

Run: python diagnostics/ocr_fixtures.py
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.environ.get("TEMP", "."), "myexa_ocr_fixtures")

TEXT = "MYEXA OCR check: artificial intelligence in medicine 2026"


def _font(size: int):
    for name in ("arial.ttf", "segoeui.ttf", "calibri.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_image(path: str) -> None:
    image = Image.new("RGB", (1200, 300), "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 60), TEXT, fill="black", font=_font(36))
    draw.text((40, 150), "second line: search quality", fill="black", font=_font(36))
    image.save(path)


def make_image_only_pdf(path: str) -> None:
    """A PDF without a text layer — the case that needs poppler + OCR.

    The resolution must match what PIL writes into the PDF (72 dpi), otherwise
    the image is drawn larger than the page and the lower part is cut off.
    """
    image = Image.new("RGB", (1200, 300), "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 60), TEXT, fill="black", font=_font(36))
    draw.text((40, 150), "second line: search quality", fill="black", font=_font(36))
    image.save(path, "PDF", resolution=72.0)


def make_text_pdf(path: str) -> None:
    """A PDF with a real text layer — the case PyPDF2 handles."""
    content = b"BT /F1 24 Tf 72 700 Td (MYEXA OCR check: text layer PDF) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(index).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (b"trailer\n<< /Size " + str(len(objects) + 1).encode()
            + b" /Root 1 0 R >>\nstartxref\n" + str(xref_at).encode() + b"\n%%EOF\n")
    with open(path, "wb") as f:
        f.write(bytes(out))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    files = {
        "text_layer.pdf": make_text_pdf,
        "scan.png": make_image,
        "scan.pdf": make_image_only_pdf,
    }
    for name, builder in files.items():
        path = os.path.join(OUT_DIR, name)
        builder(path)
        print(f"  {path}  ({os.path.getsize(path)} bytes)")


if __name__ == "__main__":
    sys.exit(main())
