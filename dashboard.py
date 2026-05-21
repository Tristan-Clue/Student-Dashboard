# ============================================================
# dashboard.py
# Dashboard home page for the Student Productivity App.
#
# Displays:
#   1. Welcome header + today's date
#   2. Key metric tiles (cards due, total cards, streak, accuracy)
#   3. Study activity chart (last 14 days)
#   4. Recent uploads table
#   5. Recently generated summaries
# ============================================================

from datetime import datetime, timezone

import streamlit as st
import pandas as pd

from auth import require_login, get_current_user_id, get_current_username
from flashcards import (
    get_flashcard_stats,
    get_study_history,
    get_study_streak,
)
from pdf_parser import get_user_uploads
from ai_engine import get_summaries_for_user


# ============================================================
# MAIN RENDER
# ============================================================

def render():
    """Entry point called by app.py for the dashboard page."""
    require_login()

    user_id  = get_current_user_id()
    username = get_current_username()

    _render_header(username)
    _render_metrics(user_id)
    st.divider()

    col_left, col_right = st.columns([1.6, 1], gap="large")

    with col_left:
        _render_activity_chart(user_id)
        _render_recent_uploads(user_id)

    with col_right:
        _render_due_cards_callout(user_id)
        _render_recent_summaries(user_id)


# ============================================================
# SECTION 1 — HEADER
# ============================================================

def _render_header(username: str):
    today = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
    st.title(f"Welcome back, {username} 👋")
    st.caption(f"📅 {today}")


# ============================================================
# SECTION 2 — METRIC TILES
# ============================================================

def _render_metrics(user_id: int):
    """Four top-level KPI tiles."""
    stats  = get_flashcard_stats(user_id)
    streak = get_study_streak(user_id)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label = "🃏 Cards Due Today",
            value = stats["due_today"],
            help  = "Flashcards scheduled for review right now.",
        )
    with col2:
        st.metric(
            label = "📚 Total Flashcards",
            value = stats["total"],
            help  = "All flashcards across all your documents.",
        )
    with col3:
        st.metric(
            label = "🔥 Study Streak",
            value = f"{streak} day{'s' if streak != 1 else ''}",
            help  = "Consecutive days you've reviewed at least one card.",
        )
    with col4:
        accuracy = stats["accuracy_pct"]
        st.metric(
            label = "🎯 Overall Accuracy",
            value = f"{accuracy}%",
            help  = "Correct answers as a percentage of all reviews.",
        )


# ============================================================
# SECTION 3 — ACTIVITY CHART
# ============================================================

def _render_activity_chart(user_id: int):
    """Bar chart of cards reviewed over the last 14 days."""
    st.subheader("📊 Study Activity — Last 14 Days")

    history = get_study_history(user_id, days=14)

    if not history:
        st.info("No study activity yet. Upload a document and start reviewing flashcards!")
        return

    # Build a DataFrame with one row per day.
    data = {
        "Date":           [s.study_date.strftime("%d %b") for s in history],
        "Cards Reviewed": [s.cards_reviewed for s in history],
        "Cards Correct":  [s.cards_correct  for s in history],
    }
    df = pd.DataFrame(data).set_index("Date")

    st.bar_chart(df, use_container_width=True)


# ============================================================
# SECTION 4 — RECENT UPLOADS
# ============================================================

def _render_recent_uploads(user_id: int):
    """Table of the five most recently uploaded documents."""
    st.subheader("📤 Recent Uploads")

    uploads = get_user_uploads(user_id)

    if not uploads:
        st.info("You haven't uploaded any documents yet.")
        if st.button("Upload your first document →"):
            # Signal app.py to switch to the upload page by
            # storing the target in session state.
            st.session_state["nav_to"] = "upload"
            st.rerun()
        return

    # Show only the five most recent.
    recent = uploads[:5]

    rows = []
    for u in recent:
        size_kb = f"{u.file_size / 1024:.1f} KB" if u.file_size else "—"
        rows.append({
            "Filename":   u.filename,
            "Type":       u.file_type.upper(),
            "Size":       size_kb,
            "Processed":  "✅" if u.is_processed else "⏳",
            "Uploaded":   u.uploaded_at.strftime("%d %b %Y %H:%M"),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    if len(uploads) > 5:
        st.caption(f"Showing 5 of {len(uploads)} uploads.")


# ============================================================
# SECTION 5 — DUE CARDS CALLOUT
# ============================================================

def _render_due_cards_callout(user_id: int):
    """
    Prominent call-to-action if cards are due.
    Shown in the right column to grab attention.
    """
    stats     = get_flashcard_stats(user_id)
    due_count = stats["due_today"]

    if due_count == 0:
        st.success("✅ You're all caught up! No cards due right now.")
        return

    st.warning(f"🃏 You have **{due_count}** card{'s' if due_count != 1 else ''} due for review.")

    if st.button("Start Review Session →", use_container_width=True, type="primary"):
        st.session_state["nav_to"] = "flashcards"
        st.rerun()

    st.divider()

    # Difficulty breakdown.
    st.markdown("**Your flashcards by difficulty**")
    diff = stats["by_difficulty"]
    cols = st.columns(3)
    cols[0].metric("🟢 Easy",   diff.get("easy",   0))
    cols[1].metric("🟡 Medium", diff.get("medium", 0))
    cols[2].metric("🔴 Hard",   diff.get("hard",   0))

    # Top topics.
    if stats["by_topic"]:
        st.divider()
        st.markdown("**Top topics**")
        for topic, count in list(stats["by_topic"].items())[:5]:
            st.markdown(f"- **{topic}** — {count} card{'s' if count != 1 else ''}")


# ============================================================
# SECTION 6 — RECENT SUMMARIES
# ============================================================

def _render_recent_summaries(user_id: int):
    """Shows the three most recently generated summaries."""
    st.subheader("📝 Recent Summaries")

    summaries = get_summaries_for_user(user_id)

    if not summaries:
        st.info("No summaries yet. Upload and process a document to generate one.")
        return

    for summary in summaries[:3]:
        # Fetch the related upload filename for context.
        upload_name = (
            summary.upload.filename
            if summary.upload else f"Document #{summary.upload_id}"
        )
        with st.expander(f"📄 {upload_name}"):
            st.caption(f"Generated: {summary.created_at.strftime('%d %b %Y %H:%M')}")
            st.write(summary.summary_text)

            concepts = summary.get_key_concepts_list()
            if concepts:
                st.markdown("**Key concepts:**")
                st.markdown(" · ".join(f"`{c}`" for c in concepts))
