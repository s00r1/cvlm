import os
import tempfile
import pytest

# Skip tests if optional OCR dependencies are missing
pytest.importorskip("pytesseract")
pytest.importorskip("pdf2image")

from utils_extract import extract_text_from_pdf, extract_text_from_docx
from reportlab.pdfgen import canvas
from docx import Document


def create_pdf(path, text):
    c = canvas.Canvas(path)
    c.drawString(100, 750, text)
    c.save()


def create_docx(path, text):
    doc = Document()
    doc.add_paragraph(text)
    doc.save(path)


def test_extract_functions():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "sample.pdf")
        docx_path = os.path.join(tmpdir, "sample.docx")

        create_pdf(pdf_path, "Sample PDF text")
        create_docx(docx_path, "Sample DOCX text")

        pdf_text = extract_text_from_pdf(pdf_path)
        docx_text = extract_text_from_docx(docx_path)

        assert "Sample PDF text" in pdf_text
        assert "Sample DOCX text" in docx_text
