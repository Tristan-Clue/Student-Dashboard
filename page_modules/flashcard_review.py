# ============================================================
# pages/flashcard_review.py
# Flashcard review session page.
#
# Features:
#   1. Filter cards by topic / difficulty / starred
#   2. Card flip interaction (question → answer reveal)
#   3. Mark correct / incorrect (updates spaced-repetition)
#   4. Session timer and live progress bar
#   5. End-of-session summary
# ============================================================

import time
import streamlit as st

from auth import require_login, get_current_user_id
from flashcards import (
    get_due_flashcards,
    get_all_flashcards,
    get_starred_flashcards,
    get_topic_list,
    record_review,
    toggle_star,
    log_study_time,
    get_flashcard_stats,
)


def render():
    require_login()
    user_id = get_current_user_id()

    st.title("🃏 Flashcard Review")

    tab_review, tab_browse = st.tabs(["Review Session", "Browse All Cards"])

    with tab_review:
        _render_review_session(user_id)

    with tab_browse:
        _render_browse(user_id)


# ============================================================
# REVIEW SESSION
# ============================================================

def _render_review_session(user_id: int):
    """
    Main review flow.

    Session state keys used:
        fc_queue        → list of card IDs to review
        fc_index        → current position in the queue
        fc_flipped      → whether the current card is showing answer
        fc_session_start→ epoch time when session began
        fc_correct      → count of correct answers this session
        fc_incorrect    → count of incorrect answers this session
    """

    # ── Filter options ───────────────────────────────────────
    with st.expander("🔧 Session options", expanded=False):
        topics   = ["All topics"] + get_topic_list(user_id)
        diffs    = ["All difficulties", "easy", "medium", "hard"]
        sources  = ["Due cards", "All cards", "Starred only"]

        col1, col2, col3 = st.columns(3)
        selected_topic  = col1.selectbox("Topic",       topics)
        selected_diff   = col2.selectbox("Difficulty",  diffs)
        selected_source = col3.selectbox("Card source", sources)

    # ── Load / reset queue ───────────────────────────────────
    start_btn = st.button("▶️ Start Session", type="primary", use_container_width=True)

    if start_btn or "fc_queue" not in st.session_state:
        cards = _load_cards(user_id, selected_source, selected_topic, selected_diff)

        if not cards:
            st.info("No cards match your filters. Try changing the options above.")
            return

        st.session_state["fc_queue"]         = [c.id for c in cards]
        st.session_state["fc_index"]         = 0
        st.session_state["fc_flipped"]       = False
        st.session_state["fc_session_start"] = time.time()
        st.session_state["fc_correct"]       = 0
        st.session_state["fc_incorrect"]     = 0

    queue = st.session_state.get("fc_queue", [])
    if not queue:
        st.info("No cards to review right now. Come back later or upload a new document.")
        return

    index = st.session_state.get("fc_index", 0)

    # ── Session complete ─────────────────────────────────────
    if index >= len(queue):
        _render_session_complete(user_id)
        return

    # ── Progress bar ─────────────────────────────────────────
    progress = index / len(queue)
    st.progress(progress, text=f"Card {index + 1} of {len(queue)}")

    # ── Fetch current card ───────────────────────────────────
    from flashcards import get_flashcard_by_id
    card = get_flashcard_by_id(queue[index], user_id)

    if not card:
        # Card was deleted mid-session — skip it.
        st.session_state["fc_index"] += 1
        st.rerun()
        return

    # ── Card display ─────────────────────────────────────────
    _render_card(card)

    # ── Action buttons ───────────────────────────────────────
    flipped = st.session_state.get("fc_flipped", False)

    if not flipped:
        # Show answer button.
        col_centre, = st.columns([1])
        if st.button("👁️ Reveal Answer", use_container_width=True):
            st.session_state["fc_flipped"] = True
            st.rerun()
    else:
        # Correct / incorrect buttons.
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            if st.button("✅ Correct", use_container_width=True, type="primary"):
                record_review(card.id, user_id, was_correct=True)
                st.session_state["fc_correct"]  += 1
                st.session_state["fc_index"]    += 1
                st.session_state["fc_flipped"]   = False
                st.rerun()

        with col2:
            if st.button("❌ Incorrect", use_container_width=True):
                record_review(card.id, user_id, was_correct=False)
                st.session_state["fc_incorrect"] += 1
                st.session_state["fc_index"]     += 1
                st.session_state["fc_flipped"]    = False
                st.rerun()

        with col3:
            # Star toggle — doesn't advance the card.
            star_label = "⭐" if card.is_starred else "☆ Star"
            if st.button(star_label, use_container_width=True):
                toggle_star(card.id, user_id)
                st.rerun()


def _load_cards(user_id, source, topic, difficulty):
    """Loads the card list based on the selected filters."""
    if source == "Due cards":
        cards = get_due_flashcards(user_id)
    elif source == "Starred only":
        cards = get_starred_flashcards(user_id)
    else:
        cards = get_all_flashcards(user_id)

    # Apply topic filter.
    if topic != "All topics":
        cards = [c for c in cards if c.topic == topic]

    # Apply difficulty filter.
    if difficulty != "All difficulties":
        cards = [c for c in cards if c.difficulty == difficulty]

    return cards


def _render_card(card):
    """
    Renders the flashcard as a styled container.
    Shows question always; shows answer only when flipped.
    """
    flipped = st.session_state.get("fc_flipped", False)

    # Difficulty colour badge.
    diff_colours = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}
    diff_dot     = diff_colours.get(card.difficulty, "⚪")

    # Card header.
    col1, col2 = st.columns([4, 1])
    col1.markdown(f"**Topic:** {card.topic or 'General'}")
    col2.markdown(f"{diff_dot} {card.difficulty.capitalize()}")

    # Card body — uses st.container for a visual boundary.
    with st.container(border=True):
        st.markdown("### ❓ Question")
        st.markdown(f"**{card.question}**")

        if flipped:
            st.divider()
            st.markdown("### 💡 Answer")
            st.markdown(card.answer)

    # Accuracy for this card.
    accuracy = card.accuracy_rate()
    if accuracy is not None:
        st.caption(
            f"Your accuracy on this card: {accuracy * 100:.0f}% "
            f"({card.times_correct}✅ / {card.times_incorrect}❌)"
        )


def _render_session_complete(user_id: int):
    """End-of-session results screen."""
    correct   = st.session_state.get("fc_correct",   0)
    incorrect = st.session_state.get("fc_incorrect",  0)
    total     = correct + incorrect
    start     = st.session_state.get("fc_session_start", time.time())
    elapsed   = (time.time() - start) / 60  # minutes

    # Log study time.
    log_study_time(user_id, minutes=elapsed)

    st.balloons()
    st.success("🎉 Session complete!")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Cards reviewed", total)
    col2.metric("✅ Correct",      correct)
    col3.metric("❌ Incorrect",    incorrect)
    col4.metric(
        "Accuracy",
        f"{(correct / total * 100):.0f}%" if total > 0 else "—"
    )
    st.metric("⏱️ Time spent", f"{elapsed:.1f} min")

    if st.button("🔄 Start another session", use_container_width=True):
        for key in ["fc_queue", "fc_index", "fc_flipped",
                    "fc_session_start", "fc_correct", "fc_incorrect"]:
            st.session_state.pop(key, None)
        st.rerun()


# ============================================================
# BROWSE ALL CARDS
# ============================================================

def _render_browse(user_id: int):
    """Browse and manage all flashcards in a searchable table."""
    st.subheader("All your flashcards")

    stats = get_flashcard_stats(user_id)
    if stats["total"] == 0:
        st.info("No flashcards yet. Upload and process a document to generate some.")
        return

    # ── Filters ──────────────────────────────────────────────
    col1, col2 = st.columns(2)
    topics    = ["All"] + get_topic_list(user_id)
    diffs     = ["All", "easy", "medium", "hard"]
    f_topic   = col1.selectbox("Filter by topic",      topics, key="browse_topic")
    f_diff    = col2.selectbox("Filter by difficulty",  diffs,  key="browse_diff")

    cards = get_all_flashcards(user_id)

    if f_topic != "All":
        cards = [c for c in cards if c.topic == f_topic]
    if f_diff != "All":
        cards = [c for c in cards if c.difficulty == f_diff]

    st.caption(f"Showing {len(cards)} card(s)")

    # ── Card list ────────────────────────────────────────────
    for card in cards:
        diff_dot = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}.get(card.difficulty, "⚪")
        star     = "⭐" if card.is_starred else ""

        with st.expander(f"{diff_dot} {star} {card.question[:80]}"):
            st.markdown(f"**Answer:** {card.answer}")
            st.caption(
                f"Topic: {card.topic} · "
                f"Difficulty: {card.difficulty} · "
                f"Reviewed: {card.times_correct + card.times_incorrect}x"
            )

            col_star, col_del, _ = st.columns([1, 1, 4])
            with col_star:
                if st.button("⭐ Star" if not card.is_starred else "Unstar",
                             key=f"star_{card.id}"):
                    toggle_star(card.id, user_id)
                    st.rerun()
            with col_del:
                if st.button("🗑️ Delete", key=f"browse_del_{card.id}"):
                    from flashcards import delete_flashcard
                    delete_flashcard(card.id, user_id)
                    st.rerun()
