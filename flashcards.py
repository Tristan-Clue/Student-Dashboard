# ============================================================
# flashcards.py
# Flashcard business logic for the Student Productivity App.
#
# Responsibilities:
#   1. Retrieve flashcards (all, due, by topic, by upload)
#   2. Spaced-repetition scheduling (simplified SM-2)
#   3. Record review results (correct / incorrect)
#   4. Star / unstar cards
#   5. Delete individual cards or all cards for an upload
#   6. Aggregate stats (accuracy, topic breakdown)
#   7. Update daily StudyStat records
#
# Spaced-repetition algorithm (simplified SM-2):
#   Correct   → next review in (interval × ease_factor) days
#   Incorrect → next review in 1 day (reset)
#   ease_factor starts at 2.5, nudged ±0.15 each review
#   Minimum ease_factor is 1.3 so cards never become trivial
# ============================================================

from datetime import datetime, timezone, timedelta

from sqlalchemy import func, or_

from database import get_db
from models import Flashcard, StudyStat


# ============================================================
# SECTION 1 — SPACED REPETITION SCHEDULER
# ============================================================

DEFAULT_EASE_FACTOR = 2.5
MIN_EASE_FACTOR     = 1.3
MAX_EASE_FACTOR     = 4.0

# Fixed intervals (days) for the first two correct answers
# before the exponential growth kicks in.
INITIAL_INTERVALS = [1, 3]


def calculate_next_review(
    times_correct:   int,
    times_incorrect: int,
    last_interval:   int   = 1,
    ease_factor:     float = DEFAULT_EASE_FACTOR,
    was_correct:     bool  = True,
) -> tuple[datetime, float, int]:
    """
    Calculates the next review date for a flashcard.

    Uses a simplified SM-2 algorithm:
      - Correct:   interval grows exponentially via ease_factor
      - Incorrect: interval resets to 1 day, ease_factor drops

    Args:
        times_correct:   total correct answers INCLUDING this one
        times_incorrect: total incorrect answers INCLUDING this one
        last_interval:   days between the previous and current review
        ease_factor:     current ease multiplier stored on the card
        was_correct:     whether the user just got this card right

    Returns:
        (next_review_datetime, new_ease_factor, new_interval_days)
    """
    now = datetime.now(timezone.utc)

    if not was_correct:
        # Wrong answer → reset to tomorrow, reduce ease slightly.
        new_ease     = max(MIN_EASE_FACTOR, ease_factor - 0.2)
        new_interval = 1

    else:
        # Correct → use SM-2 progression.
        if times_correct <= len(INITIAL_INTERVALS):
            # First few reviews use short fixed intervals.
            new_interval = INITIAL_INTERVALS[times_correct - 1]
        else:
            # After the initial phase, interval grows with ease_factor.
            new_interval = max(1, round(last_interval * ease_factor))

        new_ease = min(MAX_EASE_FACTOR, ease_factor + 0.15)

    next_review = now + timedelta(days=new_interval)
    return next_review, new_ease, new_interval


# ============================================================
# SECTION 2 — RECORDING REVIEW RESULTS
# ============================================================

def record_review(
    card_id:     int,
    user_id:     int,
    was_correct: bool,
) -> tuple[bool, str]:
    """
    Records the result of a single flashcard review and
    reschedules the card using the spaced-repetition algorithm.

    Also updates today's StudyStat row for the user.

    Returns:
        (True,  "Recorded. Next review in X day(s).")
        (False, "error message")
    """
    db = get_db()
    try:
        card = db.query(Flashcard).filter(
            Flashcard.id      == card_id,
            Flashcard.user_id == user_id,
        ).first()

        if not card:
            return False, "Flashcard not found."

        # ── Estimate last interval ──────────────────────────
        # If the card has been reviewed before, compute the gap
        # in days between then and now. Default to 1 for new cards.
        now = datetime.now(timezone.utc)

        if card.last_reviewed_at:
            last_reviewed = card.last_reviewed_at
            # Make aware if stored as naive datetime.
            if last_reviewed.tzinfo is None:
                last_reviewed = last_reviewed.replace(tzinfo=timezone.utc)
            last_interval = max(1, (now - last_reviewed).days)
        else:
            last_interval = 1

        # ── Update review counters ──────────────────────────
        if was_correct:
            card.times_correct += 1
        else:
            card.times_incorrect += 1

        card.last_reviewed_at = now

        # ── Schedule next review ────────────────────────────
        next_review, new_ease, new_interval = calculate_next_review(
            times_correct   = card.times_correct,
            times_incorrect = card.times_incorrect,
            last_interval   = last_interval,
            ease_factor     = DEFAULT_EASE_FACTOR,  # stored per-card in future
            was_correct     = was_correct,
        )
        card.next_review_at = next_review

        db.add(card)
        db.commit()

        # ── Update daily study stats ────────────────────────
        _upsert_study_stat(
            user_id     = user_id,
            correct     = 1 if was_correct else 0,
            reviewed    = 1,
        )

        direction = "✓ Correct" if was_correct else "✗ Incorrect"
        return True, f"{direction} — next review in {new_interval} day(s)."

    except Exception as e:
        db.rollback()
        return False, f"Failed to record review: {str(e)}"
    finally:
        db.close()


# ============================================================
# SECTION 3 — STUDY STAT HELPER (internal)
# ============================================================

def _upsert_study_stat(
    user_id:             int,
    reviewed:            int = 0,
    correct:             int = 0,
    docs_uploaded:       int = 0,
    summaries_generated: int = 0,
    study_minutes:       float = 0.0,
):
    """
    Creates or updates today's StudyStat row for a user.

    Called internally by record_review() and can be called
    from the upload/summary pages too.

    Uses today's date (UTC) as the key. If a row already exists
    for today it increments the counters; otherwise creates one.
    """
    db  = get_db()
    now = datetime.now(timezone.utc)

    # Normalise to midnight so all events today share one row.
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        stat = db.query(StudyStat).filter(
            StudyStat.user_id    == user_id,
            StudyStat.study_date == today,
        ).first()

        if stat:
            stat.cards_reviewed      += reviewed
            stat.cards_correct       += correct
            stat.docs_uploaded       += docs_uploaded
            stat.summaries_generated += summaries_generated
            stat.study_minutes       += study_minutes
        else:
            stat = StudyStat(
                user_id             = user_id,
                study_date          = today,
                cards_reviewed      = reviewed,
                cards_correct       = correct,
                docs_uploaded       = docs_uploaded,
                summaries_generated = summaries_generated,
                study_minutes       = study_minutes,
            )
            db.add(stat)

        db.commit()

    except Exception:
        db.rollback()
    finally:
        db.close()


# ============================================================
# SECTION 4 — FETCHING FLASHCARDS
# ============================================================

def get_all_flashcards(user_id: int) -> list[Flashcard]:
    """Returns all flashcards for a user, newest first."""
    db = get_db()
    try:
        return (
            db.query(Flashcard)
            .filter(Flashcard.user_id == user_id)
            .order_by(Flashcard.created_at.desc())
            .all()
        )
    finally:
        db.close()


def get_due_flashcards(user_id: int) -> list[Flashcard]:
    """
    Returns cards due for review right now.

    A card is due if:
      - next_review_at is NULL  (never reviewed), OR
      - next_review_at <= now   (scheduled time has passed)
    """
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
            .order_by(Flashcard.next_review_at.asc().nullsfirst())
            .all()
        )
    finally:
        db.close()


def get_flashcards_by_upload(upload_id: int, user_id: int) -> list[Flashcard]:
    """Returns all flashcards generated from a specific upload."""
    db = get_db()
    try:
        return (
            db.query(Flashcard)
            .filter(
                Flashcard.upload_id == upload_id,
                Flashcard.user_id   == user_id,
            )
            .order_by(Flashcard.created_at.asc())
            .all()
        )
    finally:
        db.close()


def get_flashcards_by_topic(topic: str, user_id: int) -> list[Flashcard]:
    """Returns all flashcards with a specific topic tag."""
    db = get_db()
    try:
        return (
            db.query(Flashcard)
            .filter(
                Flashcard.user_id == user_id,
                Flashcard.topic   == topic,
            )
            .order_by(Flashcard.created_at.desc())
            .all()
        )
    finally:
        db.close()


def get_starred_flashcards(user_id: int) -> list[Flashcard]:
    """Returns all starred (saved) flashcards for a user."""
    db = get_db()
    try:
        return (
            db.query(Flashcard)
            .filter(
                Flashcard.user_id    == user_id,
                Flashcard.is_starred == True,   # noqa: E712
            )
            .order_by(Flashcard.created_at.desc())
            .all()
        )
    finally:
        db.close()


def get_flashcard_by_id(card_id: int, user_id: int) -> Flashcard | None:
    """Fetches a single card scoped to the logged-in user."""
    db = get_db()
    try:
        return db.query(Flashcard).filter(
            Flashcard.id      == card_id,
            Flashcard.user_id == user_id,
        ).first()
    finally:
        db.close()


# ============================================================
# SECTION 5 — CARD ACTIONS
# ============================================================

def toggle_star(card_id: int, user_id: int) -> tuple[bool, str]:
    """
    Toggles the starred state of a flashcard.

    Returns:
        (True,  "Starred." or "Unstarred.")
        (False, "error message")
    """
    db = get_db()
    try:
        card = db.query(Flashcard).filter(
            Flashcard.id      == card_id,
            Flashcard.user_id == user_id,
        ).first()

        if not card:
            return False, "Flashcard not found."

        card.is_starred = not card.is_starred
        db.commit()

        status = "Starred ⭐" if card.is_starred else "Unstarred"
        return True, status

    except Exception as e:
        db.rollback()
        return False, f"Failed to update card: {str(e)}"
    finally:
        db.close()


def delete_flashcard(card_id: int, user_id: int) -> tuple[bool, str]:
    """
    Deletes a single flashcard scoped to the logged-in user.

    Returns:
        (True,  "Deleted.")
        (False, "error message")
    """
    db = get_db()
    try:
        card = db.query(Flashcard).filter(
            Flashcard.id      == card_id,
            Flashcard.user_id == user_id,
        ).first()

        if not card:
            return False, "Flashcard not found."

        db.delete(card)
        db.commit()
        return True, "Flashcard deleted."

    except Exception as e:
        db.rollback()
        return False, f"Failed to delete card: {str(e)}"
    finally:
        db.close()


def delete_flashcards_for_upload(upload_id: int, user_id: int) -> tuple[bool, str]:
    """
    Deletes ALL flashcards generated from a specific upload.

    Called when a user deletes an upload and wants to remove
    all associated cards at once.

    Returns:
        (True,  "X cards deleted.")
        (False, "error message")
    """
    db = get_db()
    try:
        deleted = (
            db.query(Flashcard)
            .filter(
                Flashcard.upload_id == upload_id,
                Flashcard.user_id   == user_id,
            )
            .delete(synchronize_session=False)
        )
        db.commit()
        return True, f"{deleted} flashcard(s) deleted."

    except Exception as e:
        db.rollback()
        return False, f"Failed to delete cards: {str(e)}"
    finally:
        db.close()


# ============================================================
# SECTION 6 — STATISTICS & AGGREGATES
# ============================================================

def get_topic_list(user_id: int) -> list[str]:
    """
    Returns a sorted list of all unique topic tags for a user.

    Used to populate the topic filter dropdown on the
    flashcard review page.
    """
    db = get_db()
    try:
        rows = (
            db.query(Flashcard.topic)
            .filter(
                Flashcard.user_id == user_id,
                Flashcard.topic   != None,   # noqa: E711
            )
            .distinct()
            .all()
        )
        return sorted([row[0] for row in rows if row[0]])
    finally:
        db.close()


def get_flashcard_stats(user_id: int) -> dict:
    """
    Returns aggregate flashcard statistics for a user.

    Used by the dashboard to display progress metrics.

    Returns a dict with:
        total:          total number of flashcards
        due_today:      cards due for review right now
        starred:        number of starred cards
        total_reviewed: total review sessions across all cards
        total_correct:  total correct answers across all cards
        accuracy_pct:   overall accuracy as a float (0–100)
        by_difficulty:  {"easy": N, "medium": N, "hard": N}
        by_topic:       {"Topic Name": N, ...}
    """
    db  = get_db()
    now = datetime.now(timezone.utc)

    try:
        # ── Totals ──────────────────────────────────────────
        total = db.query(func.count(Flashcard.id)).filter(
            Flashcard.user_id == user_id
        ).scalar() or 0

        due_today = db.query(func.count(Flashcard.id)).filter(
            Flashcard.user_id == user_id,
            or_(
                Flashcard.next_review_at == None,   # noqa: E711
                Flashcard.next_review_at <= now,
            ),
        ).scalar() or 0

        starred = db.query(func.count(Flashcard.id)).filter(
            Flashcard.user_id    == user_id,
            Flashcard.is_starred == True,           # noqa: E712
        ).scalar() or 0

        total_correct = db.query(
            func.sum(Flashcard.times_correct)
        ).filter(Flashcard.user_id == user_id).scalar() or 0

        total_incorrect = db.query(
            func.sum(Flashcard.times_incorrect)
        ).filter(Flashcard.user_id == user_id).scalar() or 0

        total_reviewed = total_correct + total_incorrect
        accuracy_pct   = (
            round((total_correct / total_reviewed) * 100, 1)
            if total_reviewed > 0 else 0.0
        )

        # ── By difficulty ───────────────────────────────────
        diff_rows = (
            db.query(Flashcard.difficulty, func.count(Flashcard.id))
            .filter(Flashcard.user_id == user_id)
            .group_by(Flashcard.difficulty)
            .all()
        )
        by_difficulty = {"easy": 0, "medium": 0, "hard": 0}
        for diff, count in diff_rows:
            if diff in by_difficulty:
                by_difficulty[diff] = count

        # ── By topic ────────────────────────────────────────
        topic_rows = (
            db.query(Flashcard.topic, func.count(Flashcard.id))
            .filter(
                Flashcard.user_id == user_id,
                Flashcard.topic   != None,          # noqa: E711
            )
            .group_by(Flashcard.topic)
            .order_by(func.count(Flashcard.id).desc())
            .all()
        )
        by_topic = {topic: count for topic, count in topic_rows if topic}

        return {
            "total":          total,
            "due_today":      due_today,
            "starred":        starred,
            "total_reviewed": total_reviewed,
            "total_correct":  total_correct,
            "accuracy_pct":   accuracy_pct,
            "by_difficulty":  by_difficulty,
            "by_topic":       by_topic,
        }

    finally:
        db.close()


def get_study_history(user_id: int, days: int = 14) -> list[StudyStat]:
    """
    Returns the last N days of study stats for a user.

    Used by the dashboard to render the study activity chart.

    Args:
        user_id: the logged-in user
        days:    how many days of history to return (default 14)
    """
    db    = get_db()
    since = datetime.now(timezone.utc) - timedelta(days=days)
    try:
        return (
            db.query(StudyStat)
            .filter(
                StudyStat.user_id    == user_id,
                StudyStat.study_date >= since,
            )
            .order_by(StudyStat.study_date.asc())
            .all()
        )
    finally:
        db.close()


def get_study_streak(user_id: int) -> int:
    """
    Returns the user's current study streak in days.

    A streak is the number of consecutive days (counting back
    from today) on which the user reviewed at least one card.

    Returns 0 if the user has never studied or missed yesterday.
    """
    db    = get_db()
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    try:
        streak  = 0
        check   = today

        while True:
            stat = db.query(StudyStat).filter(
                StudyStat.user_id    == user_id,
                StudyStat.study_date == check,
            ).first()

            if stat and stat.cards_reviewed > 0:
                streak += 1
                check  -= timedelta(days=1)
            else:
                break

        return streak

    finally:
        db.close()


def log_study_time(user_id: int, minutes: float):
    """
    Adds study minutes to today's stat row.

    Call this from the flashcard review page when a session ends,
    passing the elapsed time in minutes.
    """
    _upsert_study_stat(user_id=user_id, study_minutes=minutes)


def log_document_uploaded(user_id: int):
    """Increments today's docs_uploaded counter."""
    _upsert_study_stat(user_id=user_id, docs_uploaded=1)


def log_summary_generated(user_id: int):
    """Increments today's summaries_generated counter."""
    _upsert_study_stat(user_id=user_id, summaries_generated=1)
