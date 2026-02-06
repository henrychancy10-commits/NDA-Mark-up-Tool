"""
Parse markup guidelines from various file formats.
Supports: .pdf, .docx, .doc, .txt
"""

import os

from docx import Document
from PyPDF2 import PdfReader


def parse_guidelines(file_path: str) -> str:
    """
    Extract text from a guidelines file.

    Args:
        file_path: path to the uploaded guidelines file

    Returns:
        extracted text content
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return _parse_pdf(file_path)
    elif ext in (".docx", ".doc"):
        return _parse_docx(file_path)
    elif ext == ".txt":
        return _parse_text(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def _parse_pdf(file_path: str) -> str:
    """Extract text from a PDF file."""
    reader = PdfReader(file_path)
    text_parts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            text_parts.append(text)
    return "\n\n".join(text_parts)


def _parse_docx(file_path: str) -> str:
    """Extract text from a Word document."""
    doc = Document(file_path)
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)

    # Also get text from tables
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    text = para.text.strip()
                    if text:
                        paragraphs.append(text)

    return "\n\n".join(paragraphs)


def _parse_text(file_path: str) -> str:
    """Read a plain text file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
