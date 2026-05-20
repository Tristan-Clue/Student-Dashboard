# ============================================================
# ai_engine.py
# OpenAI API integration for the Student Productivity App.
#
# Responsibilities:
#   1. Load the OpenAI API key from environment / st.secrets
#   2. Generate a summary for an uploaded document
#   3. Extract key concepts from document text
#   4. Generate flashcard question-answer pairs
#   5. Save all AI results to the database
#   6. Provide a single end-to-end "process document" function
#
# All functions return (bool, result_or_error) tuples so the
# UI can always display a clear success or failure message.
#
# Token cost awareness:
#   - Text is chunked before sending (see pdf_parser.chunk_text)
#   - For summaries: all chunks are summarised then condensed
#   - For flashcards: only the first N chunks are used to keep
#     costs reasonable for a student project
# ============================================================

import os
import json
import time

import streamlit as st
from openai import OpenAI

from database import get_db
from models import Upload, Summary, Flashcard
from pdf_parser import chunk_text


# ============================================================
# SECTION 1 — CLIENT SETUP
# ============================================================

def get_openai_client() -> OpenAI:
    """
    Returns an authenticated OpenAI client.

    Looks for the API key in this order:
      1. st.secrets["OPENAI_API_KEY"]  — Streamlit Cloud deployment
      2. os.environ["OPENAI_API_KEY"]  — local .env loaded by dotenv
      3. Raises a clear error if neither is found

    Call this inside every function that needs the API so the
    client is always fresh and the key is always validated.
    """
    api_key = None

    # ── Try Streamlit secrets first (works on Streamlit Cloud) ─
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass

    # ── Fall back to environment variable ──────────────────
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        raise ValueError(
            "OpenAI API key not found. "
            "Set OPENAI_API_KEY in your .env file or Streamlit secrets."
        )

    return OpenAI(api_key=api_key)


# Model to use for all completions.
# gpt-4o is fast, cheap, and handles long documents well.
DEFAULT_MODEL    = "gpt-4o"
MAX_RETRIES      = 3       # Retry on transient API errors
RETRY_DELAY      = 2       # Seconds between retries
MAX_SUMMARY_CHUNKS   = 10  # Cap chunks sent for summarisation
MAX_FLASHCARD_CHUNKS = 5   # Cap chunks sent for flashcard generation


# ============================================================
# SECTION 2 — CORE API CALL HELPER
# ============================================================

def call_openai(
    system_prompt: str,
    user_prompt:   str,
    model:         str = DEFAULT_MODEL,
    max_tokens:    int = 1500,
    temperature:   float = 0.4,
) -> tuple[bool, str, int]:
    """
    Makes a single ChatCompletion API call with retry logic.

    Args:
        system_prompt: Instructions telling the AI what role to play.
        user_prompt:   The actual content / question to process.
        model:         OpenAI model name.
        max_tokens:    Maximum tokens in the response.
        temperature:   0 = deterministic, 1 = creative. 0.4 is a
                       good balance for factual study content.

    Returns:
        (True,  response_text, tokens_used)  on success
        (False, error_message, 0)            on failure
    """
    client = get_openai_client()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model    = model,
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                max_tokens  = max_tokens,
                temperature = temperature,
            )

            text         = response.choices[0].message.content.strip()
            tokens_used  = response.usage.total_tokens
            return True, text, tokens_used

        except Exception as e:
            error_str = str(e)

            # Don't retry on authentication errors — they won't resolve.
            if "401" in error_str or "invalid_api_key" in error_str:
                return False, "Invalid OpenAI API key. Check your .env file.", 0

            # Don't retry on quota/billing errors.
            if "429" in error_str and "quota" in error_str.lower():
                return False, "OpenAI quota exceeded. Check your billing.", 0

            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY * attempt)  # Exponential back-off
            else:
                return False, f"API call failed after {MAX_RETRIES} attempts: {error_str}", 0

    return False, "Unexpected error in call_openai.", 0


# ============================================================
# SECTION 3 — SUMMARY GENERATION
# ============================================================

SUMMARY_SYSTEM_PROMPT = """You are an expert academic tutor helping students understand
complex material. Your job is to create clear, well-structured summaries that
capture the most important ideas, arguments, and facts from study material.

Write in plain English. Use short paragraphs. Avoid bullet points unless the
content is genuinely list-like. Aim for the kind of summary a student could
read the night before an exam to recall the key ideas."""


def summarise_chunk(chunk: str, chunk_index: int, total_chunks: int) -> tuple[bool, str, int]:
    """
    Summarises a single text chunk.

    Used internally by generate_summary() to process large
    documents chunk by chunk before combining them.
    """
    user_prompt = (
        f"Please summarise the following text "
        f"(part {chunk_index + 1} of {total_chunks}):\n\n{chunk}"
    )
    return call_openai(
        system_prompt = SUMMARY_SYSTEM_PROMPT,
        user_prompt   = user_prompt,
        max_tokens    = 600,
        temperature   = 0.3,
    )


def combine_summaries(chunk_summaries: list[str]) -> tuple[bool, str, int]:
    """
    Takes individual chunk summaries and produces one final summary.

    This two-pass approach (summarise chunks → combine) avoids
    sending the entire document in a single API call while still
    producing a coherent overall summary.
    """
    combined_input = "\n\n---\n\n".join(
        f"Part {i + 1}:\n{s}" for i, s in enumerate(chunk_summaries)
    )

    user_prompt = (
        "Below are summaries of different parts of the same document. "
        "Please combine them into a single, coherent summary that flows "
        "naturally and removes any repetition:\n\n"
        f"{combined_input}"
    )

    return call_openai(
        system_prompt = SUMMARY_SYSTEM_PROMPT,
        user_prompt   = user_prompt,
        max_tokens    = 1000,
        temperature   = 0.3,
    )


def generate_summary(
    text:      str,
    upload_id: int,
    user_id:   int,
) -> tuple[bool, str, Summary | None]:
    """
    Generates a full document summary and saves it to the database.

    Pipeline:
      1. Split text into chunks
      2. Summarise each chunk individually
      3. Combine chunk summaries into one final summary
      4. Save to the summaries table

    Returns:
        (True,  "success", Summary object)
        (False, "error",   None)
    """
    if not text or not text.strip():
        return False, "No text to summarise.", None

    chunks      = chunk_text(text)
    total_tokens = 0

    # ── Cap chunks to control API cost ─────────────────────
    if len(chunks) > MAX_SUMMARY_CHUNKS:
        chunks = chunks[:MAX_SUMMARY_CHUNKS]

    # ── Step 1: Summarise each chunk ────────────────────────
    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        success, result, tokens = summarise_chunk(chunk, i, len(chunks))
        if not success:
            return False, f"Summary failed on chunk {i + 1}: {result}", None
        chunk_summaries.append(result)
        total_tokens += tokens

    # ── Step 2: Combine into one summary ────────────────────
    if len(chunk_summaries) == 1:
        # Only one chunk — no need to combine.
        final_summary = chunk_summaries[0]
    else:
        success, final_summary, tokens = combine_summaries(chunk_summaries)
        if not success:
            return False, f"Failed to combine summaries: {final_summary}", None
        total_tokens += tokens

    # ── Step 3: Save to database ────────────────────────────
    db = get_db()
    try:
        summary_record = Summary(
            user_id      = user_id,
            upload_id    = upload_id,
            summary_text = final_summary,
            model_used   = DEFAULT_MODEL,
            tokens_used  = total_tokens,
        )
        db.add(summary_record)
        db.commit()
        db.refresh(summary_record)
        # expunge() detaches the object from the session while keeping
        # all its loaded data accessible after db.close().
        db.expunge(summary_record)
        return True, "Summary generated successfully.", summary_record

    except Exception as e:
        db.rollback()
        return False, f"Failed to save summary: {str(e)}", None
    finally:
        db.close()


# ============================================================
# SECTION 4 — KEY CONCEPTS EXTRACTION
# ============================================================

KEY_CONCEPTS_SYSTEM_PROMPT = """You are an expert academic tutor.
Extract the most important key concepts, terms, and ideas from the provided text.

Return ONLY a JSON array of strings. Each string is one key concept.
Example output:
["Photosynthesis", "Chlorophyll", "ATP synthesis", "Light reactions", "Calvin cycle"]

Rules:
- Return 5 to 15 concepts depending on how rich the material is.
- Each concept should be a short noun phrase (1–5 words).
- Order from most important to least important.
- Return ONLY the JSON array. No explanation, no preamble."""


def extract_key_concepts(text: str) -> tuple[bool, list[str], int]:
    """
    Extracts key concepts from document text as a Python list.

    Uses only the first chunk to keep this call fast and cheap —
    the most important concepts are usually near the beginning.

    Returns:
        (True,  ["concept1", "concept2", ...], tokens_used)
        (False, [],                            0)
    """
    # Use the first chunk only for key concept extraction.
    chunks = chunk_text(text)
    if not chunks:
        return False, [], 0

    first_chunk = chunks[0]

    success, result, tokens = call_openai(
        system_prompt = KEY_CONCEPTS_SYSTEM_PROMPT,
        user_prompt   = f"Extract key concepts from:\n\n{first_chunk}",
        max_tokens    = 300,
        temperature   = 0.2,  # Low temperature for consistent, factual output
    )

    if not success:
        return False, [], 0

    # ── Parse the JSON array safely ─────────────────────────
    try:
        # Strip markdown code fences if the model added them.
        clean = result.strip().strip("```json").strip("```").strip()
        concepts = json.loads(clean)

        if isinstance(concepts, list):
            # Filter out any non-string items just in case.
            concepts = [str(c).strip() for c in concepts if c]
            return True, concepts, tokens

    except json.JSONDecodeError:
        # If JSON parsing fails, try to extract items manually.
        # This handles cases where the model returns a plain list.
        lines    = [l.strip().strip('"-,') for l in result.split("\n")]
        concepts = [l for l in lines if l and len(l) < 80]
        if concepts:
            return True, concepts[:15], tokens

    return False, [], 0


# ============================================================
# SECTION 5 — FLASHCARD GENERATION
# ============================================================

FLASHCARD_SYSTEM_PROMPT = """You are an expert academic tutor creating flashcards
to help students study effectively.

Generate question-answer flashcard pairs from the provided text.

Return ONLY a JSON array of objects. Each object must have exactly these keys:
  "question" - a clear, specific question
  "answer"   - a concise but complete answer (1–3 sentences)
  "topic"    - a short topic label (1–4 words)
  "difficulty" - one of: "easy", "medium", "hard"

Example output:
[
  {
    "question": "What is the powerhouse of the cell?",
    "answer": "The mitochondria. It produces ATP through cellular respiration.",
    "topic": "Cell biology",
    "difficulty": "easy"
  }
]

Rules:
- Generate 5 to 10 flashcards per chunk of text.
- Questions should test understanding, not just memorisation.
- Vary the difficulty — include a mix of easy, medium, and hard.
- Return ONLY the JSON array. No explanation, no preamble."""


def generate_flashcards_from_chunk(
    chunk: str,
    chunk_index: int,
) -> tuple[bool, list[dict], int]:
    """
    Generates raw flashcard dicts from a single text chunk.

    Returns:
        (True,  [{"question":..., "answer":..., "topic":..., "difficulty":...}], tokens)
        (False, [], 0)
    """
    user_prompt = (
        f"Generate flashcards from the following study material "
        f"(section {chunk_index + 1}):\n\n{chunk}"
    )

    success, result, tokens = call_openai(
        system_prompt = FLASHCARD_SYSTEM_PROMPT,
        user_prompt   = user_prompt,
        max_tokens    = 1500,
        temperature   = 0.5,  # Slightly higher for varied question styles
    )

    if not success:
        return False, [], 0

    # ── Parse JSON response ─────────────────────────────────
    try:
        clean = result.strip().strip("```json").strip("```").strip()
        cards = json.loads(clean)

        if isinstance(cards, list):
            # Validate each card has required keys.
            valid_cards = []
            for card in cards:
                if all(k in card for k in ("question", "answer", "topic")):
                    # Ensure difficulty is a valid value.
                    card.setdefault("difficulty", "medium")
                    if card["difficulty"] not in ("easy", "medium", "hard"):
                        card["difficulty"] = "medium"
                    valid_cards.append(card)
            return True, valid_cards, tokens

    except json.JSONDecodeError:
        pass

    return False, [], 0


def generate_flashcards(
    text:      str,
    upload_id: int,
    user_id:   int,
) -> tuple[bool, str, list[Flashcard]]:
    """
    Generates flashcards for a document and saves them to the DB.

    Processes up to MAX_FLASHCARD_CHUNKS chunks to keep costs
    manageable while still covering the main content.

    Returns:
        (True,  "X flashcards created", [Flashcard, ...])
        (False, "error message",        [])
    """
    if not text or not text.strip():
        return False, "No text to generate flashcards from.", []

    chunks = chunk_text(text)
    if len(chunks) > MAX_FLASHCARD_CHUNKS:
        chunks = chunks[:MAX_FLASHCARD_CHUNKS]

    all_card_dicts = []
    total_tokens   = 0

    # ── Generate cards chunk by chunk ───────────────────────
    for i, chunk in enumerate(chunks):
        success, cards, tokens = generate_flashcards_from_chunk(chunk, i)
        if success and cards:
            all_card_dicts.extend(cards)
        total_tokens += tokens

    if not all_card_dicts:
        return False, "No flashcards could be generated from this document.", []

    # ── Save all cards to the database ──────────────────────
    db = get_db()
    saved_cards = []
    try:
        for card_dict in all_card_dicts:
            card = Flashcard(
                user_id   = user_id,
                upload_id = upload_id,
                question  = card_dict["question"],
                answer    = card_dict["answer"],
                topic     = card_dict.get("topic", "General"),
                difficulty = card_dict.get("difficulty", "medium"),
            )
            db.add(card)
            saved_cards.append(card)

        db.commit()

        # Refresh then expunge each card so attributes remain
        # accessible after the session closes.
        for card in saved_cards:
            db.refresh(card)
            db.expunge(card)

        message = f"{len(saved_cards)} flashcards generated successfully."
        return True, message, saved_cards

    except Exception as e:
        db.rollback()
        return False, f"Failed to save flashcards: {str(e)}", []
    finally:
        db.close()


# ============================================================
# SECTION 6 — END-TO-END DOCUMENT PROCESSOR
# ============================================================

def process_document(
    upload_id: int,
    user_id:   int,
) -> tuple[bool, dict]:
    """
    Full AI processing pipeline for an uploaded document.

    Runs in order:
      1. Load extracted text from the database
      2. Extract key concepts  → save to summary record
      3. Generate summary      → save to summaries table
      4. Generate flashcards   → save to flashcards table
      5. Mark upload as processed

    Returns:
        (True, {
            "summary":   Summary object,
            "concepts":  ["concept1", ...],
            "flashcards": [Flashcard, ...],
            "tokens_used": int,
        })
        (False, {"error": "message"})

    Usage in the upload page:
        success, results = process_document(upload.id, user_id)
        if success:
            st.success(f"Generated {len(results['flashcards'])} flashcards!")
    """
    db = get_db()
    try:
        # ── Load the upload record ──────────────────────────
        upload = db.query(Upload).filter(
            Upload.id      == upload_id,
            Upload.user_id == user_id,
        ).first()

        if not upload:
            return False, {"error": "Upload not found."}

        if not upload.extracted_text:
            return False, {"error": "No extracted text found. Cannot process."}

        text         = upload.extracted_text
        total_tokens = 0
        results      = {}

        # ── Step 1: Key concepts ────────────────────────────
        concepts_ok, concepts, tokens = extract_key_concepts(text)
        total_tokens += tokens
        results["concepts"] = concepts if concepts_ok else []

        # ── Step 2: Summary (includes key concepts) ─────────
        sum_ok, sum_msg, summary = generate_summary(text, upload_id, user_id)
        if not sum_ok:
            return False, {"error": f"Summary generation failed: {sum_msg}"}

        total_tokens += summary.tokens_used

        # ── Attach key concepts to the summary record ───────
        # summary came from a different session (generate_summary
        # opened and closed its own session), so we use db.merge()
        # to re-attach it to this session before updating it.
        if concepts_ok and concepts:
            summary = db.merge(summary)
            summary.key_concepts = "|".join(concepts)
            db.commit()
            db.expunge(summary)

        results["summary"] = summary

        # ── Step 3: Flashcards ──────────────────────────────
        fc_ok, fc_msg, flashcards = generate_flashcards(text, upload_id, user_id)
        if not fc_ok:
            # Flashcard failure is non-fatal — summary was saved.
            results["flashcards"]  = []
            results["fc_warning"]  = fc_msg
        else:
            results["flashcards"]  = flashcards

        # ── Step 4: Mark upload as processed ────────────────
        upload.is_processed = True
        db.add(upload)
        db.commit()

        results["tokens_used"] = total_tokens
        return True, results

    except Exception as e:
        db.rollback()
        return False, {"error": f"Processing failed: {str(e)}"}
    finally:
        db.close()


# ============================================================
# SECTION 7 — DATABASE QUERY HELPERS
# ============================================================

def get_summaries_for_user(user_id: int) -> list[Summary]:
    """Returns all summaries for a user, newest first."""
    db = get_db()
    try:
        return (
            db.query(Summary)
            .filter(Summary.user_id == user_id)
            .order_by(Summary.created_at.desc())
            .all()
        )
    finally:
        db.close()


def get_summary_for_upload(upload_id: int, user_id: int) -> Summary | None:
    """Returns the most recent summary for a specific upload."""
    db = get_db()
    try:
        return (
            db.query(Summary)
            .filter(
                Summary.upload_id == upload_id,
                Summary.user_id   == user_id,
            )
            .order_by(Summary.created_at.desc())
            .first()
        )
    finally:
        db.close()


def get_flashcards_for_user(
    user_id:    int,
    topic:      str | None = None,
    difficulty: str | None = None,
) -> list[Flashcard]:
    """
    Returns flashcards for a user with optional filters.

    Args:
        user_id:    the logged-in user
        topic:      filter by topic name (optional)
        difficulty: filter by "easy"/"medium"/"hard" (optional)
    """
    db = get_db()
    try:
        query = db.query(Flashcard).filter(Flashcard.user_id == user_id)

        if topic:
            query = query.filter(Flashcard.topic == topic)
        if difficulty:
            query = query.filter(Flashcard.difficulty == difficulty)

        return query.order_by(Flashcard.created_at.desc()).all()
    finally:
        db.close()


def get_due_flashcards(user_id: int) -> list[Flashcard]:
    """
    Returns flashcards that are due for review today.

    A card is due if:
      - It has never been reviewed (next_review_at is None), OR
      - Its next_review_at date is today or in the past

    Used by the dashboard to show the "cards due today" count.
    """
    from datetime import datetime, timezone
    from sqlalchemy import or_

    db  = get_db()
    now = datetime.now(timezone.utc)

    try:
        return (
            db.query(Flashcard)
            .filter(
                Flashcard.user_id == user_id,
                or_(
                    Flashcard.next_review_at == None,   # noqa: E711
                    Flashcard.next_review_at <= now,
                ),
            )
            .all()
        )
    finally:
        db.close()
