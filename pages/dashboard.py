# ============================================================
# pages/dashboard.py
# Home page for the Student Productivity Dashboard.
#
# Displays:
#   1. Welcome message and user stats overview
#   2. Recent document uploads
#   3. Flashcards due for review
#   4. Study statistics and progress
#   5. Recently generated AI summaries
#
# This is the first page users see after logging in.
# ============================================================

import streamlit as st
from datetime import datetime, timedelta

from auth import require_login, get_current_user_id
from database import get_db
from models import Upload, Flashcard, Summary, StudyStat
from ai_engine import get_summaries_for_user, get_flashcards_for_user


def show_dashboard():
    """
    Renders the dashboard homepage with stats, recent uploads,
    and study progress.
    """
    # Gate access to logged-in users only.
    require_login()

    user_id = get_current_user_id()
    current_user = get_current_user_id()

    st.title("📊 Dashboard")
    st.write("Welcome back! Here's an overview of your study progress.")

    st.divider()

    # ──────────────────────────────────────────────────────
    # SECTION 1: KEY METRICS
    # ──────────────────────────────────────────────────────

    st.subheader("📈 Your Stats")

    db = get_db()
    try:
        # Fetch counts for key metrics
        total_uploads = db.query(Upload).filter(
            Upload.user_id == user_id
        ).count()

        total_summaries = db.query(Summary).filter(
            Summary.user_id == user_id
        ).count()

        total_flashcards = db.query(Flashcard).filter(
            Flashcard.user_id == user_id
        ).count()

        # Calculate study streak (simplified — days with any activity)
        study_days = db.query(StudyStat).filter(
            StudyStat.user_id == user_id
        ).count()

        # Display metrics in columns
        metric_cols = st.columns(4)
        metric_cols[0].metric("📤 Uploads", total_uploads)
        metric_cols[1].metric("📝 Summaries", total_summaries)
        metric_cols[2].metric("🎴 Flashcards", total_flashcards)
        metric_cols[3].metric("📅 Study Days", study_days)

    finally:
        db.close()

    st.divider()

    # ──────────────────────────────────────────────────────
    # SECTION 2: RECENT UPLOADS
    # ──────────────────────────────────────────────────────

    st.subheader("📤 Recent Uploads")

    db = get_db()
    try:
        recent_uploads = db.query(Upload).filter(
            Upload.user_id == user_id
        ).order_by(Upload.uploaded_at.desc()).limit(5).all()

        if recent_uploads:
            for upload in recent_uploads:
                col1, col2, col3 = st.columns([2, 1, 1])

                with col1:
                    # Show filename
                    status_icon = "✅" if upload.is_processed else "⏳"
                    st.write(f"{status_icon} **{upload.filename}**")
                    st.caption(upload.uploaded_at.strftime("%Y-%m-%d %H:%M"))

                with col2:
                    # Show file size
                    size_mb = upload.file_size / (1024 * 1024)
                    st.caption(f"{size_mb:.2f} MB")

                with col3:
                    # Show file type badge
                    st.caption(f"`{upload.file_type.upper()}`")

        else:
            st.info("No documents uploaded yet. Start by uploading a file!")

    finally:
        db.close()

    st.divider()

    # ──────────────────────────────────────────────────────
    # SECTION 3: RECENT SUMMARIES
    # ──────────────────────────────────────────────────────

    st.subheader("📝 Recent AI Summaries")

    summaries = get_summaries_for_user(user_id)
    if summaries:
        # Show the 3 most recent summaries
        for summary in summaries[:3]:
            with st.expander(f"Summary from {summary.created_at.strftime('%Y-%m-%d')}"):
                # Show the summary text (truncated for readability)
                preview = summary.summary_text[:300]
                if len(summary.summary_text) > 300:
                    preview += "..."
                st.write(preview)

                # Show key concepts if available
                if summary.key_concepts:
                    concepts = summary.key_concepts.split("|")
                    st.write("**Key Concepts:**")
                    cols = st.columns(min(3, len(concepts)))
                    for i, concept in enumerate(concepts[:6]):
                        cols[i % 3].write(f"• {concept}")

                # Token usage info
                st.caption(f"Generated with {summary.tokens_used} tokens using {summary.model_used}")

    else:
        st.info("No summaries yet. Upload a document and process it to generate summaries!")

    st.divider()

    # ──────────────────────────────────────────────────────
    # SECTION 4: FLASHCARD STATUS
    # ──────────────────────────────────────────────────────

    st.subheader("🎴 Flashcard Status")

    flashcards = get_flashcards_for_user(user_id)
    if flashcards:
        # Simple stats about flashcards
        total_cards = len(flashcards)

        # Count by difficulty
        easy_count = sum(1 for fc in flashcards if fc.difficulty == "easy")
        medium_count = sum(1 for fc in flashcards if fc.difficulty == "medium")
        hard_count = sum(1 for fc in flashcards if fc.difficulty == "hard")

        # Count by review status (marked correct/incorrect)
        # Note: this assumes the model has marked_correct column
        # If not, you can skip this or add the column later
        reviewed = sum(1 for fc in flashcards if getattr(fc, "is_reviewed", False))

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Cards", total_cards)
        col2.metric("Easy", easy_count, "🟢")
        col3.metric("Medium", medium_count, "🟡")
        col4.metric("Hard", hard_count, "🔴")

        # Progress bar for cards reviewed
        if total_cards > 0:
            review_pct = (reviewed / total_cards) * 100
            st.progress(review_pct / 100, text=f"{review_pct:.0f}% reviewed")

    else:
        st.info("No flashcards yet. Generate flashcards from an uploaded document!")

    st.divider()

    # ──────────────────────────────────────────────────────
    # SECTION 5: QUICK ACTIONS
    # ──────────────────────────────────────────────────────

    st.subheader("⚡ Quick Actions")

    quick_cols = st.columns(3)

    with quick_cols[0]:
        if st.button("📤 Upload a Document", use_container_width=True):
            st.session_state["page"] = "upload"
            st.rerun()

    with quick_cols[1]:
        if st.button("🎴 Study Flashcards", use_container_width=True):
            st.session_state["page"] = "flashcards"
            st.rerun()

    with quick_cols[2]:
        if st.button("📝 View Summaries", use_container_width=True):
            st.session_state["page"] = "summaries"
            st.rerun()

    st.divider()

    # ──────────────────────────────────────────────────────
    # FOOTER
    # ──────────────────────────────────────────────────────

    st.caption(
        "💡 **Tip:** Upload documents regularly and review flashcards daily "
        "for better retention!"
    )
