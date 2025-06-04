import pytesseract
from pdf2image import convert_from_path
from PyPDF2 import PdfReader
from docx import Document


def extract_text_from_pdf(file_path):
    try:
        reader = PdfReader(file_path)
        fulltext = "\n".join([page.extract_text() or "" for page in reader.pages])
        if fulltext.strip():
            return fulltext
    except Exception:
        pass
    try:
        images = convert_from_path(file_path)
        text = "\n".join(
            [pytesseract.image_to_string(img, lang="fra+eng") for img in images]
        )
        return text
    except Exception:
        return ""


def extract_text_from_docx(file_path):
    try:
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs])
    except Exception:
        return ""
