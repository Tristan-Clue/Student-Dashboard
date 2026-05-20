# ============================================================
# pages/flashcards.py
# Flashcard study and review page.
#
# Allows users to:
#   1. View all generated flashcards
#   2. Filter by topic or difficulty
#   3. Flip cards (question → answer)
#   4. Mark cards as correct/incorrect
#   5. Track study progress
# ============================================================

import streamlit as st
from auth import require_login, get_current_user_id
from ai_engine import get_flashcards_for_user


def show_flashcards_page():
    """
    Renders the flashcard study page.
    """
    require_login()

    user_id = get_current_user_id()

    st.title("🎴 Study Flashcards")
    st.write("Flip cards to test your knowledge!")

    st.divider()

    # ──────────────────────────────────────────────────────
    # FILTERS
    # ──────────────────────────────────────────────────────

    col1, col2 = st.columns(2)

    with col1:
        difficulty_filter = st.selectbox(
            "Filter by difficulty:",
            ["All", "Easy", "Medium", "Hard"],
        )

    with col2:
        topic_filter = st.text_input(
            "Filter by topic (optional):",
            placeholder="e.g., Biology, Math",
        )

    # ──────────────────────────────────────────────────────
    # FETCH FLASHCARDS
    # ──────────────────────────────────────────────────────

    flashcards = get_flashcards_for_user(user_id)

    # Apply filters
    if difficulty_filter != "All":
        difficulty_map = {"Easy": "easy", "Medium": "medium", "Hard": "hard"}
        flashcards = [
            fc for fc in flashcards
            if fc.difficulty == difficulty_map[difficulty_filter]
        ]

    if topic_filter:
        flashcards = [
            fc for fc in flashcards
            if topic_filter.lower() in fc.topic.lower()
        ]

    st.divider()

    # ──────────────────────────────────────────────────────
    # DISPLAY FLASHCARDS
    # ──────────────────────────────────────────────────────

    if not flashcards:
        st.info("No flashcards match your filters. Generate some from uploaded documents!")
    else:
        st.write(f"**{len(flashcards)} flashcard(s) found**")
        st.divider()

        # Initialize session state for flipped cards
        if "flipped" not in st.session_state:
            st.session_state.flipped = {}

        # Display each flashcard
        for idx, card in enumerate(flashcards):
            # Card header with metadata
            col1, col2, col3 = st.columns([2, 1, 1])

            with col1:
                st.write(f"**Card {idx + 1}** — {card.topic}")
            with col2:
                difficulty_emoji = {
                    "easy": "🟢",
                    "medium": "🟡",
                    "hard": "🔴",
                }
                st.caption(f"{difficulty_emoji.get(card.difficulty, '⚪')} {card.difficulty.capitalize()}")
            with col3:
                st.caption(f"Created: {card.created_at.strftime('%Y-%m-%d')}")

            # Flip state toggle
            flip_key = f"card_{card.id}"
            is_flipped = st.session_state.flipped.get(flip_key, False)

            # Card display
            if is_flipped:
                # Show answer
                st.markdown(f"""
                <div style="background-color: #e8f5e9; padding: 20px; border-radius: 10px; margin: 10px 0;">
                    <p><strong>Answer:</strong></p>
                    <p>{card.answer}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                # Show question
                st.markdown(f"""
                <div style="background-color: #e3f2fd; padding: 20px; border-radius: 10px; margin: 10px 0;">
                    <p><strong>Question:</strong></p>
                    <p>{card.question}</p>
                </div>
                """, unsafe_allow_html=True)

            # Action buttons
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                if st.button(
                    f"{'📖 Show Answer' if not is_flipped else '❓ Show Question'}",
                    key=f"flip_{card.id}",
                    use_container_width=True,
                ):
                    st.session_state.flipped[flip_key] = not is_flipped
                    st.rerun()

            with col2:
                st.button(
                    "✅ Correct",
                    key=f"correct_{card.id}",
                    use_container_width=True,
                )

            with col3:
                st.button(
                    "❌ Incorrect",
                    key=f"incorrect_{card.id}",
                    use_container_width=True,
                )

            with col4:
                st.button(
                    "🗑️ Delete",
                    key=f"delete_{card.id}",
                    use_container_width=True,
                )

            st.divider()

    # ──────────────────────────────────────────────────────
    # STUDY TIPS
    # ──────────────────────────────────────────────────────

    with st.expander("💡 Study Tips"):
        st.markdown("""
        - **Spaced Repetition** — Review cards regularly to build long-term memory
        - **Active Recall** — Try to answer before flipping the card
        - **Focus on Weak Areas** — Mark "Incorrect" on difficult cards and review them more
        - **Study Session** — Aim for 20-30 minute sessions for best retention
        """)
