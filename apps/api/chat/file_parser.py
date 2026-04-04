"""File parsing utilities for extracting text content from uploaded documents.

Supports PDF, DOCX, Excel (xlsx/xls), and image files.
Images are described using Gemini vision.
"""

import base64
import io

from fastapi import UploadFile

from apps.api.config import settings
from apps.api.logging_config import get_logger

logger = get_logger(__name__)

ALLOWED_EXTENSIONS = {
    "pdf",
    "docx",
    "xlsx",
    "xls",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
}

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

MIME_MAP = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def _get_extension(filename: str) -> str:
    """Extract lowercase file extension from a filename."""
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


async def validate_upload(file: UploadFile) -> tuple[bool, str]:
    """Validate the uploaded file's type and size.

    Returns:
        A tuple of (is_valid, error_message).
    """
    ext = _get_extension(file.filename or "")
    if ext not in ALLOWED_EXTENSIONS:
        return (
            False,
            f"Unsupported file type '.{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    await file.seek(0)

    if len(content) > MAX_FILE_SIZE_BYTES:
        return False, f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB."

    return True, ""


async def parse_file(file: UploadFile) -> dict:
    """Parse an uploaded file and extract its text content.

    Args:
        file: The uploaded file from FastAPI.

    Returns:
        A dict with keys: filename, file_type, extracted_text, is_image, image_base64.
    """
    filename = file.filename or "unknown"
    ext = _get_extension(filename)
    content = await file.read()

    logger.info("parsing_file", filename=filename, extension=ext, size_bytes=len(content))

    is_image = ext in IMAGE_EXTENSIONS

    if is_image:
        image_b64 = base64.b64encode(content).decode("utf-8")
        extracted_text = await _describe_image(image_b64, ext)
        return {
            "filename": filename,
            "file_type": ext,
            "extracted_text": extracted_text,
            "is_image": True,
            "image_base64": image_b64,
        }

    extracted_text = ""

    if ext == "pdf":
        extracted_text = _parse_pdf(content)
    elif ext == "docx":
        extracted_text = _parse_docx(content)
    elif ext in {"xlsx", "xls"}:
        extracted_text = _parse_excel(content)

    logger.info("file_parsed", filename=filename, text_length=len(extracted_text))

    return {
        "filename": filename,
        "file_type": ext,
        "extracted_text": extracted_text,
        "is_image": False,
        "image_base64": None,
    }


async def _describe_image(image_b64: str, ext: str) -> str:
    """Use Gemini vision to describe an image and extract any visible text."""
    if settings.is_llm_mock_mode:
        return "[Mock mode] Image uploaded. Cannot describe without a valid Gemini API key."

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model)

        mime_type = MIME_MAP.get(ext, "image/png")
        image_part = {
            "inline_data": {
                "mime_type": mime_type,
                "data": image_b64,
            }
        }

        response = await model.generate_content_async(
            [
                "Describe this image in detail. If there is any text visible in the image, "
                "extract and include all of it. If the image contains charts, tables, or data, "
                "describe the data thoroughly. Provide a structured description.",
                image_part,
            ]
        )

        description = response.text.strip() if response.text else ""
        logger.info("image_described", description_length=len(description))
        return description

    except Exception:
        logger.exception("image_description_failed")
        return (
            "[Image uploaded but could not be analyzed. "
            "Please describe what you see or ask a specific question.]"
        )


def _parse_pdf(content: bytes) -> str:
    """Extract text from a PDF file using PyMuPDF."""
    import pymupdf

    text_parts = []
    with pymupdf.open(stream=content, filetype="pdf") as doc:
        for page_num, page in enumerate(doc, 1):
            page_text = page.get_text()
            if page_text.strip():
                text_parts.append(f"[Page {page_num}]\n{page_text.strip()}")

    return "\n\n".join(text_parts)


def _parse_docx(content: bytes) -> str:
    """Extract text from a DOCX file using python-docx."""
    from docx import Document

    doc = Document(io.BytesIO(content))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

    # Also extract text from tables
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                paragraphs.append(row_text)

    return "\n\n".join(paragraphs)


def _parse_excel(content: bytes) -> str:
    """Extract text from an Excel file using openpyxl."""
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    text_parts = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        sheet_rows = []
        for row in ws.iter_rows(values_only=True):
            cells = [str(cell) if cell is not None else "" for cell in row]
            if any(c.strip() for c in cells):
                sheet_rows.append(" | ".join(cells))

        if sheet_rows:
            text_parts.append(f"[Sheet: {sheet_name}]\n" + "\n".join(sheet_rows))

    wb.close()
    return "\n\n".join(text_parts)
