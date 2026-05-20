# ============================================================
# pdf_parser.py
# Document upload handling and text extraction.
#
# Responsibilities:
#   1. Save uploaded files to disk (organised by user)
#   2. Extract plain text from PDF, TXT, and DOCX files
#   3. Split long text into chunks for the AI pipeline
#   4. Record uploads in the database
#   5. Provide helper functions for the upload UI page
#
# Extraction strategy:
#   PDF  → try pdfplumber first, fall back to pypdf
#   TXT  → read directly with UTF-8 / latin-1 fallback
#   DOCX → python-docx paragraph extraction
# ============================================================

import os
import uuid
from datetime import datetime, timezone

import streamlit as st

from database import get_db
from models import Upload


# ============================================================
# SECTION 1 — DIRECTORY SETUP
# ============================================================

# Base uploads folder, relative to this file.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")

# Allowed file extensions and their MIME types.
ALLOWED_EXTENSIONS = {"pdf", "txt", "docx"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Maximum file size: 20 MB (in bytes).
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024


def get_user_upload_dir(user_id: int) -> str:
    """
    Returns (and creates if needed) the upload folder for a user.

    Structure:  uploads/<user_id>/
    Each user gets their own subfolder so files never collide
    across accounts and per-user cleanup is trivial.
    """
    user_dir = os.path.join(UPLOADS_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


# ============================================================
# SECTION 2 — FILE SAVING
# ============================================================

def save_uploaded_file(uploaded_file, user_id: int) -> tuple[bool, str, str]:
    """
    Saves a Streamlit UploadedFile object to disk.

    Uses a UUID prefix on the filename to prevent collisions
    when the same user uploads the same file twice.

    Returns:
        (True,  file_path, original_filename)  on success
        (False, error_message, "")             on failure

    Args:
        uploaded_file: st.UploadedFile from st.file_uploader()
        user_id:       the logged-in user's database ID
    """
    try:
        original_name = uploaded_file.name
        file_bytes    = uploaded_file.read()
        file_size     = len(file_bytes)

        # ── Validate file size ──────────────────────────────
        if file_size > MAX_FILE_SIZE_BYTES:
            size_mb = file_size / (1024 * 1024)
            return False, f"File too large ({size_mb:.1f} MB). Maximum is 20 MB.", ""

        # ── Validate extension ──────────────────────────────
        ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"Unsupported file type '.{ext}'. Allowed: PDF, TXT, DOCX.", ""

        # ── Build a unique filename ─────────────────────────
        # e.g. "a3f2c1d4_lecture_notes.pdf"
        unique_prefix = uuid.uuid4().hex[:8]
        safe_name     = f"{unique_prefix}_{original_name}"
        user_dir      = get_user_upload_dir(user_id)
        file_path     = os.path.join(user_dir, safe_name)

        # ── Write to disk ───────────────────────────────────
        with open(file_path, "wb") as f:
            f.write(file_bytes)

        return True, file_path, original_name

    except Exception as e:
        return False, f"Failed to save file: {str(e)}", ""


# ============================================================
# SECTION 3 — TEXT EXTRACTION
# ============================================================

def extract_text_from_pdf(file_path: str) -> tuple[bool, str]:
    """
    Extracts all text from a PDF file.

    Strategy:
      1. Try pdfplumber — better for complex layouts, tables.
      2. Fall back to pypdf — better for simple/scanned PDFs.
      3. If both fail, return an empty string gracefully.

    Returns:
        (True,  extracted_text)   on success
        (False, error_message)    if both parsers fail
    """
    # ── Attempt 1: pdfplumber ───────────────────────────────
    try:
        import pdfplumber

        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    # Add a page marker so the AI knows where
                    # each page starts — useful for citations.
                    text_parts.append(f"[Page {i + 1} of {total_pages}]\n{page_text}")

        if text_parts:
            return True, "\n\n".join(text_parts)

        # pdfplumber returned no text — fall through to pypdf.

    except Exception:
        pass  # Silent fall-through to backup parser.

    # ── Attempt 2: pypdf ────────────────────────────────────
    try:
        from pypdf import PdfReader

        reader     = PdfReader(file_path)
        text_parts = []

        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"[Page {i + 1}]\n{page_text}")

        if text_parts:
            return True, "\n\n".join(text_parts)

        return False, "No text could be extracted. The PDF may be image-based or password-protected."

    except Exception as e:
        return False, f"PDF extraction failed: {str(e)}"


def extract_text_from_txt(file_path: str) -> tuple[bool, str]:
    """
    Reads a plain text file.

    Tries UTF-8 first, falls back to latin-1 which can read
    almost any single-byte encoding without crashing.

    Returns:
        (True,  file_contents)
        (False, error_message)
    """
    # ── Attempt 1: UTF-8 ────────────────────────────────────
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return True, f.read()
    except UnicodeDecodeError:
        pass

    # ── Attempt 2: latin-1 fallback ─────────────────────────
    try:
        with open(file_path, "r", encoding="latin-1") as f:
            return True, f.read()
    except Exception as e:
        return False, f"Could not read text file: {str(e)}"


def extract_text_from_docx(file_path: str) -> tuple[bool, str]:
    """
    Extracts text from a Microsoft Word (.docx) file.

    Joins all non-empty paragraphs with double newlines so the
    AI pipeline sees natural paragraph breaks.

    Returns:
        (True,  extracted_text)
        (False, error_message)
    """
    try:
        from docx import Document

        doc        = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text       = "\n\n".join(paragraphs)

        if not text:
            return False, "No text found in the Word document."

        return True, text

    except ImportError:
        return False, "python-docx is not installed. Run: pip install python-docx"
    except Exception as e:
        return False, f"DOCX extraction failed: {str(e)}"


def extract_text(file_path: str, file_type: str) -> tuple[bool, str]:
    """
    Master dispatcher — routes to the correct extractor by file type.

    Args:
        file_path: absolute path to the file on disk
        file_type: "pdf", "txt", or "docx"

    Returns:
        (True,  extracted_text)
        (False, error_message)
    """
    file_type = file_type.lower().strip(".")

    if file_type == "pdf":
        return extract_text_from_pdf(file_path)
    elif file_type == "txt":
        return extract_text_from_txt(file_path)
    elif file_type == "docx":
        return extract_text_from_docx(file_path)
    else:
        return False, f"Unsupported file type: '{file_type}'"


# ============================================================
# SECTION 4 — TEXT CHUNKING
# ============================================================

def chunk_text(text: str, chunk_size: int = 3000, overlap: int = 200) -> list[str]:
    """
    Splits a long text into overlapping chunks for the AI pipeline.

    Why chunking?
      OpenAI models have token limits. A large PDF (50+ pages)
      would exceed the context window if sent all at once.
      Chunking lets us process it in pieces.

    Why overlap?
      The overlap between chunks ensures sentences or ideas that
      fall near a chunk boundary are captured in both chunks,
      so the AI doesn't miss context at the seams.

    Args:
        text:       the full extracted text
        chunk_size: approx characters per chunk (default 3000 ≈ ~750 tokens)
        overlap:    characters of overlap between chunks (default 200)

    Returns:
        A list of text chunk strings.

    Example:
        chunks = chunk_text(long_pdf_text)
        # → ["Chapter 1 intro...", "...intro continued, Chapter 2...", ...]
    """
    text = text.strip()
    if not text:
        return []

    # If the whole text fits in one chunk, no splitting needed.
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start  = 0

    while start < len(text):
        end = start + chunk_size

        # ── Try to cut at a paragraph break ────────────────
        # Avoids cutting mid-sentence when possible.
        if end < len(text):
            # Look for a double newline within the last 300 chars of the chunk.
            paragraph_break = text.rfind("\n\n", start, end)
            if paragraph_break != -1 and paragraph_break > start + (chunk_size // 2):
                end = paragraph_break

            # Fall back to a single newline if no paragraph break.
            else:
                line_break = text.rfind("\n", start, end)
                if line_break != -1 and line_break > start + (chunk_size // 2):
                    end = line_break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start forward, stepping back by `overlap` characters
        # so the next chunk has some context from the previous one.
        start = end - overlap

    return chunks


def get_text_stats(text: str) -> dict:
    """
    Returns basic statistics about extracted text.
    Useful for displaying info to the user before AI processing.

    Returns a dict with:
        word_count:   approximate number of words
        char_count:   total characters
        chunk_count:  how many chunks chunk_text() would produce
        page_markers: how many [Page N] markers were found
    """
    if not text:
        return {"word_count": 0, "char_count": 0, "chunk_count": 0, "page_markers": 0}

    import re
    words       = len(text.split())
    chars       = len(text)
    chunks      = len(chunk_text(text))
    page_marks  = len(re.findall(r"\[Page \d+", text))

    return {
        "word_count":   words,
        "char_count":   chars,
        "chunk_count":  chunks,
        "page_markers": page_marks,
    }


# ============================================================
# SECTION 5 — DATABASE INTEGRATION
# ============================================================

def record_upload(
    user_id:        int,
    filename:       str,
    file_path:      str,
    file_type:      str,
    file_size:      int,
    extracted_text: str | None = None,
) -> tuple[bool, str, Upload | None]:
    """
    Saves an upload record to the database.

    Called after a file has been successfully saved to disk
    and its text extracted. Creates an Upload row so the
    dashboard and AI pipeline can reference it.

    Returns:
        (True,  "success", Upload object)   on success
        (False, "error message", None)      on failure
    """
    db = get_db()
    try:
        upload = Upload(
            user_id        = user_id,
            filename       = filename,
            file_path      = file_path,
            file_type      = file_type,
            file_size      = file_size,
            extracted_text = extracted_text,
            is_processed   = False,
            uploaded_at    = datetime.now(timezone.utc),
        )
        db.add(upload)
        db.commit()
        db.refresh(upload)
        return True, "Upload recorded successfully.", upload

    except Exception as e:
        db.rollback()
        return False, f"Failed to record upload: {str(e)}", None
    finally:
        db.close()


def get_user_uploads(user_id: int) -> list[Upload]:
    """
    Returns all uploads for a user, newest first.

    Used by the dashboard and summaries page to list documents.
    """
    db = get_db()
    try:
        return (
            db.query(Upload)
            .filter(Upload.user_id == user_id)
            .order_by(Upload.uploaded_at.desc())
            .all()
        )
    finally:
        db.close()


def get_upload_by_id(upload_id: int, user_id: int) -> Upload | None:
    """
    Fetches a single upload by ID, scoped to the logged-in user.

    The user_id check prevents one user from accessing
    another user's documents.
    """
    db = get_db()
    try:
        return (
            db.query(Upload)
            .filter(
                Upload.id      == upload_id,
                Upload.user_id == user_id,
            )
            .first()
        )
    finally:
        db.close()


def delete_upload(upload_id: int, user_id: int) -> tuple[bool, str]:
    """
    Deletes an upload record and its file from disk.

    Scoped to user_id so users can only delete their own files.
    Cascade rules in models.py handle deletion of related
    summaries and flashcards automatically.

    Returns:
        (True,  "Deleted.")
        (False, "error message")
    """
    db = get_db()
    try:
        upload = (
            db.query(Upload)
            .filter(
                Upload.id      == upload_id,
                Upload.user_id == user_id,
            )
            .first()
        )

        if not upload:
            return False, "Upload not found."

        # ── Delete file from disk first ─────────────────────
        if os.path.exists(upload.file_path):
            os.remove(upload.file_path)

        # ── Delete DB record (cascades to summaries/cards) ──
        db.delete(upload)
        db.commit()
        return True, f"'{upload.filename}' deleted successfully."

    except Exception as e:
        db.rollback()
        return False, f"Delete failed: {str(e)}"
    finally:
        db.close()


# ============================================================
# SECTION 6 — FULL PIPELINE HELPER
# ============================================================

def process_upload(uploaded_file, user_id: int) -> tuple[bool, str, Upload | None]:
    """
    End-to-end handler: save → extract → record in DB.

    This is the single function the upload page calls.
    It runs all three steps and returns a clear result.

    Returns:
        (True,  "success message", Upload object)
        (False, "error message",   None)

    Usage in the upload page:
        success, message, upload = process_upload(uploaded_file, user_id)
        if success:
            st.success(message)
            # trigger AI processing next
        else:
            st.error(message)
    """
    # ── Step 1: Save file to disk ───────────────────────────
    saved, result, original_name = save_uploaded_file(uploaded_file, user_id)
    if not saved:
        return False, result, None

    file_path = result
    file_size = os.path.getsize(file_path)
    ext       = original_name.rsplit(".", 1)[-1].lower()

    # ── Step 2: Extract text ────────────────────────────────
    extracted, text_or_error = extract_text(file_path, ext)

    # Extraction failure is non-fatal — we still record the
    # upload so the user can see it in their dashboard, but
    # extracted_text will be None and AI processing will be skipped.
    if not extracted:
        extracted_text = None
        warning        = f" (Warning: text extraction failed — {text_or_error})"
    else:
        extracted_text = text_or_error
        warning        = ""

    # ── Step 3: Record in database ──────────────────────────
    recorded, db_msg, upload = record_upload(
        user_id        = user_id,
        filename       = original_name,
        file_path      = file_path,
        file_type      = ext,
        file_size      = file_size,
        extracted_text = extracted_text,
    )

    if not recorded:
        return False, db_msg, None

    stats   = get_text_stats(extracted_text or "")
    summary = (
        f"'{original_name}' uploaded successfully. "
        f"{stats['word_count']:,} words extracted across "
        f"{stats['chunk_count']} chunks.{warning}"
    )
    return True, summary, upload
