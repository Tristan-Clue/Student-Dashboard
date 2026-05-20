# ============================================================
# pages/summaries.py
# View AI-generated summaries page.
#
# Allows users to:
#   1. Browse all generated summaries
#   2. View full summary text
#   3. See associated key concepts
#   4. Filter by date or source document
#   5. Export summaries
# ============================================================

import streamlit as st
from auth import require_login, get_current_user_id
from ai_engine import get_summaries_for_user


def show_summaries_page():
    """
    Renders the summaries viewing page.
    """
    require_login()

    user_id = get_current_user_id()

    st.title("📝 Your Summaries")
    st.write("Browse all AI-generated summaries from your uploaded documents.")

    st.divider()

    # ──────────────────────────────────────────────────────
    # FETCH SUMMARIES
    # ──────────────────────────────────────────────────────

    summaries = get_summaries_for_user(user_id)

    if not summaries:
        st.info("No summaries yet. Upload and process a document to generate summaries!")
    else:
        st.write(f"**{len(summaries)} summary(ies) found**")
        st.divider()

        # Display each summary
        for idx, summary in enumerate(summaries):
            # Summary header
            col1, col2 = st.columns([3, 1])

            with col1:
                st.subheader(f"Summary {idx + 1}")
                st.caption(f"📅 Generated: {summary.created_at.strftime('%Y-%m-%d %H:%M')}")

            with col2:
                st.caption(f"Model: {summary.model_used}")

            # Main summary content
            with st.expander("📖 View Full Summary", expanded=(idx == 0)):
                st.write(summary.summary_text)

                st.divider()

                # Metadata
                col1, col2, col3 = st.columns(3)
                col1.metric("Tokens Used", summary.tokens_used)
                col2.metric("Characters", len(summary.summary_text))
                if summary.upload_id:
                    col3.metric("Upload ID", summary.upload_id)

            # Key Concepts (if available)
            if summary.key_concepts:
                st.write("**🔑 Key Concepts:**")
                concepts = summary.key_concepts.split("|")
                cols = st.columns(min(3, len(concepts)))
                for i, concept in enumerate(concepts[:9]):
                    cols[i % 3].write(f"• {concept}")

            st.divider()

    # ──────────────────────────────────────────────────────
    # TIPS
    # ──────────────────────────────────────────────────────

    with st.expander("💡 How to use summaries effectively"):
        st.markdown("""
        1. **Before Class** — Read the summary to preview the topic
        2. **During Study** — Use summaries alongside the original material
        3. **Before Exams** — Review summaries to quickly recall key points
        4. **Combination** — Use summaries with flashcards for better retention

        💡 **Pro Tip:** Save important summaries in your notes app for quick reference!
        """)
