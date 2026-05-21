# ============================================================
# pages/summaries.py
# AI Summaries browser page.
#
# Features:
#   1. List all summaries with source document info
#   2. Full summary text with key concepts
#   3. Regenerate summary for a document
#   4. Token usage display
# ============================================================

import streamlit as st

from auth import require_login, get_current_user_id
from ai_engine import (
    get_summaries_for_user,
    get_summary_for_upload,
    process_document,
)
from pdf_parser import get_user_uploads
from flashcards import log_summary_generated


def render():
    require_login()
    user_id = get_current_user_id()

    st.title("📝 Summaries")
    st.caption("AI-generated summaries of your uploaded documents.")

    tab_summaries, tab_generate = st.tabs(["My Summaries", "Generate New"])

    with tab_summaries:
        _render_summaries_list(user_id)

    with tab_generate:
        _render_generate(user_id)


# ============================================================
# SUMMARIES LIST
# ============================================================

def _render_summaries_list(user_id: int):
    summaries = get_summaries_for_user(user_id)

    if not summaries:
        st.info(
            "No summaries yet. Go to the **Generate New** tab or "
            "upload a document and process it."
        )
        return

    st.caption(f"{len(summaries)} summary/summaries found.")

    for summary in summaries:
        upload_name = (
            summary.upload.filename
            if summary.upload else f"Document #{summary.upload_id}"
        )
        date_str = summary.created_at.strftime("%d %b %Y %H:%M")

        with st.expander(f"📄 {upload_name}  —  {date_str}"):

            # ── Key concepts as pills ────────────────────────
            concepts = summary.get_key_concepts_list()
            if concepts:
                st.markdown("**Key concepts:**")
                pills = " · ".join(f"`{c}`" for c in concepts)
                st.markdown(pills)
                st.divider()

            # ── Full summary text ────────────────────────────
            st.markdown(summary.summary_text)

            # ── Metadata footer ──────────────────────────────
            st.divider()
            col1, col2 = st.columns(2)
            col1.caption(f"Model: {summary.model_used}")
            col2.caption(f"Tokens used: {summary.tokens_used:,}")


# ============================================================
# GENERATE NEW SUMMARY
# ============================================================

def _render_generate(user_id: int):
    st.subheader("Generate a summary for a document")

    uploads = get_user_uploads(user_id)

    if not uploads:
        st.info("You haven't uploaded any documents yet. Go to the Upload page first.")
        return

    # ── Document selector ─────────────────────────────────────
    upload_options = {u.filename: u for u in uploads}
    selected_name  = st.selectbox(
        "Select a document",
        options = list(upload_options.keys()),
    )
    selected_upload = upload_options[selected_name]

    # Show existing summary if one exists.
    existing = get_summary_for_upload(selected_upload.id, user_id)
    if existing:
        st.info(
            f"A summary already exists for this document "
            f"(generated {existing.created_at.strftime('%d %b %Y')})."
        )
        with st.expander("View existing summary"):
            st.write(existing.summary_text)

    # ── Generate / regenerate ─────────────────────────────────
    label = "🔄 Regenerate Summary" if existing else "✨ Generate Summary"

    if not selected_upload.extracted_text:
        st.warning("This document has no extracted text. Re-upload it to process.")
        return

    if st.button(label, type="primary", use_container_width=True):
        with st.spinner("Generating summary — this may take 20–60 seconds..."):
            success, results = process_document(selected_upload.id, user_id)

        if not success:
            st.error(f"Failed: {results.get('error')}")
            return

        log_summary_generated(user_id)
        st.success("Summary generated!")

        summary  = results.get("summary")
        concepts = summary.get_key_concepts_list() if summary else []

        if summary:
            st.markdown("### Summary")
            st.write(summary.summary_text)

            if concepts:
                st.markdown("**Key concepts:**")
                st.markdown(" · ".join(f"`{c}`" for c in concepts))

        cards = results.get("flashcards", [])
        if cards:
            st.success(f"Also generated {len(cards)} new flashcards.")
