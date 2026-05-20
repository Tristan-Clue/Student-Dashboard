# ============================================================
# test_ai_engine.py
# Tests ai_engine.py logic WITHOUT making real OpenAI API calls.
#
# Uses Python's unittest.mock to replace call_openai() with a
# fake that returns predictable responses — so this test runs
# instantly with no API key and costs nothing.
#
# Run with:  python test_ai_engine.py
# ============================================================

import os
import sys
import json
from unittest.mock import patch

print("=" * 50)
print("Testing ai_engine.py (mocked API calls)")
print("=" * 50)

# ── Imports ──────────────────────────────────────────────────
try:
    from database import init_db, get_db, DATABASE_PATH
    from models import User, Summary, Flashcard
    from auth import hash_password
    from pdf_parser import record_upload
    import ai_engine
    print("\n[OK] Imports successful")
except ImportError as e:
    print(f"\n[FAIL] Import error: {e}")
    print("Make sure all project files are in the same folder.")
    sys.exit(1)

# ── Pre-test cleanup & setup ─────────────────────────────────
if os.path.exists(DATABASE_PATH):
    os.remove(DATABASE_PATH)
init_db()

# Create a test user and upload to work with.
db = get_db()
try:
    user = User(
        username="ai_tester",
        email="ai@example.com",
        password_hash=hash_password("pass123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
finally:
    db.close()

_, _, upload = record_upload(
    user_id        = user_id,
    filename       = "biology_notes.pdf",
    file_path      = "/fake/path/biology_notes.pdf",
    file_type      = "pdf",
    file_size      = 5000,
    extracted_text = (
        "Photosynthesis is the process by which plants use sunlight, "
        "water and carbon dioxide to produce oxygen and energy in the "
        "form of glucose. This occurs in the chloroplasts of plant cells. "
        "The process has two main stages: the light-dependent reactions "
        "and the Calvin cycle. Chlorophyll is the key pigment that "
        "absorbs light energy. ATP and NADPH are produced in the first "
        "stage and used in the second stage to fix carbon dioxide. "
        "The overall equation is: 6CO2 + 6H2O + light → C6H12O6 + 6O2. "
        * 10  # Repeat to make it long enough to chunk
    ),
)
upload_id = upload.id
print(f"[OK] Test user (id={user_id}) and upload (id={upload_id}) created")


# ── Helper: fake API response ────────────────────────────────
FAKE_SUMMARY    = "Photosynthesis converts sunlight into glucose using chlorophyll in two stages."
FAKE_CONCEPTS   = json.dumps(["Photosynthesis", "Chlorophyll", "ATP", "Calvin cycle", "Glucose"])
FAKE_FLASHCARDS = json.dumps([
    {
        "question":   "What is photosynthesis?",
        "answer":     "The process plants use to convert sunlight into glucose.",
        "topic":      "Biology",
        "difficulty": "easy",
    },
    {
        "question":   "What are the two stages of photosynthesis?",
        "answer":     "Light-dependent reactions and the Calvin cycle.",
        "topic":      "Biology",
        "difficulty": "medium",
    },
    {
        "question":   "What pigment absorbs light in photosynthesis?",
        "answer":     "Chlorophyll.",
        "topic":      "Biology",
        "difficulty": "easy",
    },
])


# ── 1. Test call_openai error handling (no real API key) ─────
print("\n-- call_openai error handling --")

# Temporarily set a fake key so the client initialises.
with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-fake-key-for-testing"}):
    # We expect this to fail since the key is fake — check it
    # returns (False, message, 0) gracefully instead of crashing.
    success, msg, tokens = ai_engine.call_openai(
        system_prompt = "You are a tutor.",
        user_prompt   = "Summarise: the sky is blue.",
    )
    assert success is False,  "Fake key should cause failure"
    assert tokens == 0,       "Tokens should be 0 on failure"
    assert isinstance(msg, str) and len(msg) > 0, "Error message should be a string"
    print(f"[OK] Graceful failure with fake key: '{msg[:60]}...'")


# ── 2. Test generate_summary (mocked) ───────────────────────
print("\n-- generate_summary (mocked) --")

# patch call_openai so it returns our fake summary instantly.
with patch("ai_engine.call_openai", return_value=(True, FAKE_SUMMARY, 150)):
    success, msg, summary = ai_engine.generate_summary(
        text      = upload.extracted_text,
        upload_id = upload_id,
        user_id   = user_id,
    )

assert success is True,           f"generate_summary failed: {msg}"
assert summary is not None,       "Summary object should not be None"
assert len(summary.summary_text) > 0, "Summary text should not be empty"
assert summary.upload_id == upload_id
assert summary.user_id   == user_id
print(f"[OK] Summary saved: '{summary.summary_text[:60]}...'")
print(f"     Tokens recorded: {summary.tokens_used}")


# ── 3. Test extract_key_concepts (mocked) ───────────────────
print("\n-- extract_key_concepts (mocked) --")

with patch("ai_engine.call_openai", return_value=(True, FAKE_CONCEPTS, 80)):
    success, concepts, tokens = ai_engine.extract_key_concepts(
        upload.extracted_text
    )

assert success is True,            f"extract_key_concepts failed"
assert isinstance(concepts, list), "Concepts should be a list"
assert len(concepts) >= 1,         "Should have at least 1 concept"
assert tokens == 80
print(f"[OK] Extracted {len(concepts)} concepts: {concepts}")


# ── 4. Test generate_flashcards (mocked) ────────────────────
print("\n-- generate_flashcards (mocked) --")

with patch("ai_engine.call_openai", return_value=(True, FAKE_FLASHCARDS, 200)):
    success, msg, cards = ai_engine.generate_flashcards(
        text      = upload.extracted_text,
        upload_id = upload_id,
        user_id   = user_id,
    )

assert success is True,        f"generate_flashcards failed: {msg}"
assert len(cards) >= 1,        "Should have generated at least 1 card"
assert cards[0].question,      "Card should have a question"
assert cards[0].answer,        "Card should have an answer"
assert cards[0].topic,         "Card should have a topic"
assert cards[0].difficulty in ("easy", "medium", "hard")
print(f"[OK] {len(cards)} flashcards saved to DB")
for card in cards:
    print(f"     [{card.difficulty}] Q: {card.question[:50]}")


# ── 5. Test process_document end-to-end (mocked) ────────────
print("\n-- process_document end-to-end (mocked) --")

# Return summary on first two calls, flashcards on subsequent calls.
call_responses = (
    [(True, FAKE_SUMMARY, 100)] * 12   # summary calls (chunks + combine)
    + [(True, FAKE_CONCEPTS, 80)]      # concepts call
    + [(True, FAKE_FLASHCARDS, 200)]   # flashcard calls
)

with patch("ai_engine.call_openai", side_effect=call_responses):
    success, results = ai_engine.process_document(
        upload_id = upload_id,
        user_id   = user_id,
    )

assert success is True, f"process_document failed: {results.get('error')}"
assert "summary"    in results
assert "flashcards" in results
assert "concepts"   in results
print(f"[OK] process_document completed")
print(f"     Summary:    {str(results['summary'].summary_text)[:50]}...")
print(f"     Concepts:   {results['concepts']}")
print(f"     Flashcards: {len(results['flashcards'])} cards")
print(f"     Tokens:     {results['tokens_used']}")

# Check upload is now marked as processed.
db = get_db()
try:
    refreshed = db.query(ai_engine.Upload).filter_by(id=upload_id).first()
    assert refreshed.is_processed is True, "Upload should be marked processed"
    print(f"[OK] Upload marked as is_processed=True")
finally:
    db.close()


# ── 6. Test get_summaries_for_user ──────────────────────────
print("\n-- query helpers --")
summaries = ai_engine.get_summaries_for_user(user_id)
assert len(summaries) >= 1, "Should have at least 1 summary"
print(f"[OK] get_summaries_for_user → {len(summaries)} summary/summaries")

flashcards = ai_engine.get_flashcards_for_user(user_id)
assert len(flashcards) >= 1, "Should have at least 1 flashcard"
print(f"[OK] get_flashcards_for_user → {len(flashcards)} flashcard(s)")

due = ai_engine.get_due_flashcards(user_id)
assert len(due) >= 1, "New cards with no next_review_at should be due"
print(f"[OK] get_due_flashcards → {len(due)} due card(s)")


# ── Cleanup ──────────────────────────────────────────────────
try:
    os.remove(DATABASE_PATH)
    db_dir = os.path.dirname(DATABASE_PATH)
    if os.path.isdir(db_dir) and not os.listdir(db_dir):
        os.rmdir(db_dir)
    print("\n[OK] Test database cleaned up")
except Exception as e:
    print(f"\n[WARN] Cleanup incomplete: {e}")

print("\n" + "=" * 50)
print("All ai_engine tests passed!")
print("=" * 50)
