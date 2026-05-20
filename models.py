# ============================================================
# models.py
# SQLAlchemy ORM model definitions.
#
# Each class here maps to one database table.
# Relationships between tables are declared with
# SQLAlchemy's relationship() so you can navigate between
# related records in Python without writing JOIN queries.
#
# Tables defined here:
#   1. User          — registered accounts
#   2. Upload        — documents uploaded by a user
#   3. Summary       — AI-generated summaries of uploads
#   4. Flashcard     — AI-generated flashcards per upload
#   5. StudyStat     — daily study statistics per user
# ============================================================

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

# Import Base from database.py — all models must inherit it.
from database import Base


# ============================================================
# 1. USER
# ============================================================

class User(Base):
    """
    Represents a registered user account.

    Passwords are stored as bcrypt hashes — never plain text.
    The username and email columns are unique-constrained so
    two users cannot share the same login credentials.
    """

    __tablename__ = "users"

    # Primary key — auto-incremented integer ID.
    id = Column(Integer, primary_key=True, index=True)

    # Display name chosen at registration.
    username = Column(String(50), unique=True, nullable=False, index=True)

    # Used for future password-reset features.
    email = Column(String(120), unique=True, nullable=False, index=True)

    # bcrypt hash of the user's password (60-char string).
    password_hash = Column(String(128), nullable=False)

    # Account creation timestamp.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Soft-delete flag — False means the account is active.
    is_active = Column(Boolean, default=True, nullable=False)

    # ----------------------------------------------------------
    # Relationships — access related records as Python lists:
    #   user.uploads      → list of Upload objects
    #   user.flashcards   → list of Flashcard objects
    #   user.summaries    → list of Summary objects
    #   user.study_stats  → list of StudyStat objects
    #
    # cascade="all, delete-orphan" means if a User is deleted,
    # all their related records are deleted too.
    # ----------------------------------------------------------
    uploads     = relationship("Upload",    back_populates="user", cascade="all, delete-orphan")
    flashcards  = relationship("Flashcard", back_populates="user", cascade="all, delete-orphan")
    summaries   = relationship("Summary",   back_populates="user", cascade="all, delete-orphan")
    study_stats = relationship("StudyStat", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User id={self.id} username='{self.username}'>"


# ============================================================
# 2. UPLOAD
# ============================================================

class Upload(Base):
    """
    Represents a document that a user has uploaded.

    The file itself is stored on disk at `file_path`.
    The extracted plain text is stored in `extracted_text`
    so we never have to re-parse the file after the first time.
    """

    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign key linking this upload to its owner.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Original filename as uploaded by the user (e.g. "notes.pdf").
    filename = Column(String(255), nullable=False)

    # Absolute or relative path to the file on disk.
    file_path = Column(String(500), nullable=False)

    # File type: "pdf", "txt", or "docx".
    file_type = Column(String(10), nullable=False)

    # File size in bytes — useful for display and quota checks.
    file_size = Column(Integer, default=0)

    # Full plain text extracted from the document.
    # Text type in SQLite holds unlimited-length strings.
    extracted_text = Column(Text, nullable=True)

    # True once AI processing (summary + flashcards) is done.
    is_processed = Column(Boolean, default=False, nullable=False)

    # Timestamp of upload.
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # ----------------------------------------------------------
    # Relationships
    # ----------------------------------------------------------
    user       = relationship("User",      back_populates="uploads")
    summaries  = relationship("Summary",   back_populates="upload", cascade="all, delete-orphan")
    flashcards = relationship("Flashcard", back_populates="upload", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Upload id={self.id} filename='{self.filename}' user_id={self.user_id}>"


# ============================================================
# 3. SUMMARY
# ============================================================

class Summary(Base):
    """
    Stores an AI-generated summary for an uploaded document.

    A single upload can have multiple summaries if the user
    requests regeneration, so there is a one-to-many
    relationship between Upload and Summary.

    Also stores key concepts as a pipe-separated string
    (e.g. "photosynthesis|chlorophyll|ATP synthesis") for
    easy splitting and display.
    """

    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)

    # Link to the owning user (for fast per-user queries).
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Link to the source document.
    upload_id = Column(Integer, ForeignKey("uploads.id"), nullable=False, index=True)

    # The main AI-generated summary paragraph(s).
    summary_text = Column(Text, nullable=False)

    # Key concepts extracted by AI, stored as pipe-separated values.
    # Example: "Newton's laws|inertia|momentum|conservation of energy"
    # Split with: concepts = summary.key_concepts.split("|")
    key_concepts = Column(Text, nullable=True)

    # Which OpenAI model generated this (e.g. "gpt-4o").
    model_used = Column(String(50), default="gpt-4o")

    # Number of tokens consumed — useful for cost tracking.
    tokens_used = Column(Integer, default=0)

    # Generation timestamp.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # ----------------------------------------------------------
    # Relationships
    # ----------------------------------------------------------
    user   = relationship("User",   back_populates="summaries")
    upload = relationship("Upload", back_populates="summaries")

    def __repr__(self):
        return f"<Summary id={self.id} upload_id={self.upload_id}>"

    def get_key_concepts_list(self):
        """Returns key_concepts as a Python list."""
        if not self.key_concepts:
            return []
        return [c.strip() for c in self.key_concepts.split("|") if c.strip()]


# ============================================================
# 4. FLASHCARD
# ============================================================

class Flashcard(Base):
    """
    A single question-answer flashcard generated by AI.

    Each flashcard belongs to both a User (for quick
    per-user queries) and an Upload (its source document).

    The review fields (times_correct, times_incorrect,
    last_reviewed_at) support basic spaced-repetition logic
    in flashcards.py.
    """

    __tablename__ = "flashcards"

    id = Column(Integer, primary_key=True, index=True)

    # Owners
    user_id   = Column(Integer, ForeignKey("users.id"),    nullable=False, index=True)
    upload_id = Column(Integer, ForeignKey("uploads.id"),  nullable=False, index=True)

    # Card content
    question = Column(Text, nullable=False)
    answer   = Column(Text, nullable=False)

    # Topic tag (e.g. "Photosynthesis", "World War II").
    # Populated by AI during generation.
    topic = Column(String(100), nullable=True)

    # Difficulty rating: "easy", "medium", or "hard".
    difficulty = Column(String(10), default="medium")

    # ----------------------------------------------------------
    # Spaced-repetition tracking fields
    # ----------------------------------------------------------

    # How many times the user marked this card correct.
    times_correct = Column(Integer, default=0, nullable=False)

    # How many times the user marked this card incorrect.
    times_incorrect = Column(Integer, default=0, nullable=False)

    # Timestamp of the most recent review session.
    last_reviewed_at = Column(DateTime, nullable=True)

    # The next date this card should be shown.
    # Simple algorithm: correct → push out further, incorrect → show sooner.
    next_review_at = Column(DateTime, nullable=True)

    # Whether the user has starred/saved this card.
    is_starred = Column(Boolean, default=False, nullable=False)

    # Creation timestamp.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # ----------------------------------------------------------
    # Relationships
    # ----------------------------------------------------------
    user   = relationship("User",   back_populates="flashcards")
    upload = relationship("Upload", back_populates="flashcards")

    def __repr__(self):
        preview = self.question[:40] + "..." if len(self.question) > 40 else self.question
        return f"<Flashcard id={self.id} q='{preview}'>"

    def accuracy_rate(self):
        """
        Returns the user's accuracy rate for this card as a
        float between 0.0 and 1.0. Returns None if never reviewed.
        """
        total = self.times_correct + self.times_incorrect
        if total == 0:
            return None
        return self.times_correct / total


# ============================================================
# 5. STUDY STAT
# ============================================================

class StudyStat(Base):
    """
    Tracks daily study activity per user.

    One row per user per day. The dashboard reads from this
    table to show progress graphs and streaks.

    Upsert pattern: at the end of each study session,
    find today's row (or create it) and increment the counters.
    """

    __tablename__ = "study_stats"

    id = Column(Integer, primary_key=True, index=True)

    # Owner
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # The calendar date this row covers (stored as DateTime,
    # but only the date portion is meaningful).
    study_date = Column(DateTime, nullable=False)

    # How many flashcards were reviewed today.
    cards_reviewed = Column(Integer, default=0, nullable=False)

    # How many cards were answered correctly today.
    cards_correct = Column(Integer, default=0, nullable=False)

    # How many documents were uploaded today.
    docs_uploaded = Column(Integer, default=0, nullable=False)

    # How many AI summaries were generated today.
    summaries_generated = Column(Integer, default=0, nullable=False)

    # Total study time in minutes (tracked via session timer).
    study_minutes = Column(Float, default=0.0, nullable=False)

    # ----------------------------------------------------------
    # Relationships
    # ----------------------------------------------------------
    user = relationship("User", back_populates="study_stats")

    def __repr__(self):
        return (
            f"<StudyStat user_id={self.user_id} "
            f"date={self.study_date.date()} "
            f"cards={self.cards_reviewed}>"
        )

    def accuracy_rate(self):
        """Today's accuracy rate as a percentage string."""
        if self.cards_reviewed == 0:
            return "N/A"
        rate = (self.cards_correct / self.cards_reviewed) * 100
        return f"{rate:.0f}%"
