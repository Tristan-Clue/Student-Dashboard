# ============================================================
# test_db.py
# Quick verification script for database.py and models.py.
#
# Run with:  python test_db.py
# Expected:  All checks print OK, no errors.
# Safe to delete after testing.
# ============================================================

import os
import sys
from datetime import datetime

print("=" * 50)
print("Testing database.py + models.py")
print("=" * 50)

# ── 1. Imports ──────────────────────────────────────────────
try:
    from database import init_db, get_db, DATABASE_PATH
    from models import User, Upload, Summary, Flashcard, StudyStat
    print("\n[OK] Imports successful")
except ImportError as e:
    print(f"\n[FAIL] Import error: {e}")
    print("Make sure you ran:  pip install sqlalchemy")
    sys.exit(1)

# ── 2. Create tables ────────────────────────────────────────
try:
    init_db()
    print(f"[OK] Tables created at: {DATABASE_PATH}")
except Exception as e:
    print(f"[FAIL] init_db() failed: {e}")
    sys.exit(1)

# ── 3. Open a session ───────────────────────────────────────
db = get_db()
try:
    # ── 4. Create a test user ───────────────────────────────
    user = User(
        username="test_student",
        email="test@example.com",
        password_hash="hashed_password_placeholder",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print(f"[OK] Created user: {user}")

    # ── 5. Create a test upload ─────────────────────────────
    upload = Upload(
        user_id=user.id,
        filename="lecture_notes.pdf",
        file_path="/uploads/1/lecture_notes.pdf",
        file_type="pdf",
        file_size=204800,
        extracted_text="This is sample extracted text from the PDF.",
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    print(f"[OK] Created upload: {upload}")

    # ── 6. Create a test summary ────────────────────────────
    summary = Summary(
        user_id=user.id,
        upload_id=upload.id,
        summary_text="This document covers key concepts in biology.",
        key_concepts="photosynthesis|chlorophyll|ATP|mitochondria",
        model_used="gpt-4o",
        tokens_used=512,
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    print(f"[OK] Created summary: {summary}")
    print(f"     Key concepts list: {summary.get_key_concepts_list()}")

    # ── 7. Create a test flashcard ──────────────────────────
    card = Flashcard(
        user_id=user.id,
        upload_id=upload.id,
        question="What is photosynthesis?",
        answer="The process by which plants convert sunlight into energy.",
        topic="Biology",
        difficulty="easy",
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    print(f"[OK] Created flashcard: {card}")
    print(f"     Accuracy rate (new card): {card.accuracy_rate()}")

    # ── 8. Create a test study stat ─────────────────────────
    stat = StudyStat(
        user_id=user.id,
        study_date=datetime.now(datetime.UTC),
        cards_reviewed=10,
        cards_correct=8,
        docs_uploaded=1,
        summaries_generated=1,
        study_minutes=25.5,
    )
    db.add(stat)
    db.commit()
    db.refresh(stat)
    print(f"[OK] Created study stat: {stat}")
    print(f"     Today's accuracy: {stat.accuracy_rate()}")

    # ── 9. Test relationships ───────────────────────────────
    fetched_user = db.query(User).filter(User.username == "test_student").first()
    assert len(fetched_user.uploads) == 1,    "Expected 1 upload"
    assert len(fetched_user.summaries) == 1,  "Expected 1 summary"
    assert len(fetched_user.flashcards) == 1, "Expected 1 flashcard"
    assert len(fetched_user.study_stats) == 1,"Expected 1 study stat"
    print("[OK] Relationships work correctly")

    # ── 10. Test cascade delete ─────────────────────────────
    db.delete(fetched_user)
    db.commit()
    remaining = db.query(Flashcard).filter(Flashcard.user_id == fetched_user.id).all()
    assert remaining == [], "Cascade delete failed — flashcards still exist"
    print("[OK] Cascade delete works (all user data removed)")

except Exception as e:
    db.rollback()
    print(f"\n[FAIL] Test failed: {e}")
    raise
finally:
    db.close()

# ── 11. Clean up test database ──────────────────────────────
try:
    os.remove(DATABASE_PATH)
    db_dir = os.path.dirname(DATABASE_PATH)
    if os.path.isdir(db_dir) and not os.listdir(db_dir):
        os.rmdir(db_dir)
    print("[OK] Test database cleaned up")
except Exception as e:
    print(f"[WARN] Could not clean up test DB: {e}")

print("\n" + "=" * 50)
print("All tests passed!")
print("=" * 50)
