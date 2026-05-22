# ============================================================
# pages/upload.py
# Document upload page.
#
# Flow:
#   1. User selects a PDF, TXT, or DOCX file
#   2. File is saved to disk and text is extracted
#   3. User clicks "Generate AI Content"
#   4. AI engine produces summary + flashcards
#   5. Results are previewed inline
# ============================================================

import streamlit as st

from auth import require_login, get_current_user_id
from pdf_parser import process_upload, get_user_uploads, delete_upload, get_text_stats
from ai_engine import process_document
from flashcards import log_document_uploaded, log_summary_generated


def render():
    require_login()
    user_id = get_current_user_id()

    st.title("📤 Upload Document")
    st.caption("Upload a PDF, TXT, or DOCX file to generate summaries and flashcards.")

    tab_upload, tab_manage = st.tabs(["Upload New", "Manage Uploads"])

    with tab_upload:
        _render_upload_form(user_id)

    with tab_manage:
        _render_manage_uploads(user_id)


# ============================================================
# UPLOAD FORM
# ============================================================

def _render_upload_form(user_id: int):
    st.subheader("Upload a new document")

    uploaded_file = st.file_uploader(
        label       = "Choose a file",
        type        = ["pdf", "txt", "docx"],
        help        = "Maximum file size: 20 MB",
        label_visibility = "collapsed",
    )

    if not uploaded_file:
        # Show a placeholder when nothing is selected.
        st.info("👆 Select a PDF, TXT, or DOCX file to get started.")
        return

    # ── File preview ─────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    col1.metric("Filename", uploaded_file.name)
    col2.metric("Type",     uploaded_file.type.split("/")[-1].upper())
    col3.metric("Size",     f"{uploaded_file.size / 1024:.1f} KB")

    st.divider()

    # ── Save + extract ───────────────────────────────────────
    if st.button("📥 Save & Extract Text", use_container_width=True):
        with st.spinner("Saving file and extracting text..."):
            success, message, upload = process_upload(uploaded_file, user_id)

        if not success:
            st.error(f"Upload failed: {message}")
            return

        st.success(message)
        log_document_uploaded(user_id)

        # Store upload ID in session so the AI button can use it.
        st.session_state["last_upload_id"] = upload.id

        # Show text stats.
        if upload.extracted_text:
            stats = get_text_stats(upload.extracted_text)
            c1, c2, c3 = st.columns(3)
            c1.metric("Words extracted",  f"{stats['word_count']:,}")
            c2.metric("Pages detected",   stats["page_markers"] or "N/A")
            c3.metric("AI chunks",        stats["chunk_count"])

    # ── AI processing ─────────────────────────────────────────
    if st.session_state.get("last_upload_id"):
        st.divider()
        st.subheader("🤖 Generate AI Content")
        st.caption(
            "This will send your document to OpenAI to generate "
            "a summary, key concepts, and flashcards."
        )

        if st.button("✨ Generate Summary & Flashcards", use_container_width=True, type="primary"):
            upload_id = st.session_state["last_upload_id"]

            with st.spinner("Generating AI content — this may take 20–60 seconds..."):
                success, results = process_document(upload_id, user_id)

            if not success:
                st.error(f"AI processing failed: {results.get('error')}")
                return

            log_summary_generated(user_id)
            st.success("✅ AI content generated successfully!")

            # ── Show summary preview ─────────────────────────
            summary = results.get("summary")
            if summary:
                with st.expander("📝 Summary", expanded=True):
                    st.write(summary.summary_text)

                    concepts = summary.get_key_concepts_list()
                    if concepts:
                        st.markdown("**Key concepts:**")
                        st.markdown(" · ".join(f"`{c}`" for c in concepts))

            # ── Show flashcard preview ───────────────────────
            cards = results.get("flashcards", [])
            if cards:
                with st.expander(f"🃏 Flashcards ({len(cards)} generated)", expanded=True):
                    for i, card in enumerate(cards[:5]):
                        st.markdown(f"**Q{i+1}: {card.question}**")
                        st.markdown(f"*A: {card.answer}*")
                        st.caption(f"Topic: {card.topic} · Difficulty: {card.difficulty}")
                        if i < len(cards) - 1:
                            st.divider()

                    if len(cards) > 5:
                        st.caption(f"...and {len(cards) - 5} more. View all in Flashcard Review.")

            # Token usage info.
            tokens = results.get("tokens_used", 0)
            st.caption(f"Tokens used: {tokens:,}")

            # Clear session so the form is ready for next upload.
            del st.session_state["last_upload_id"]


# ============================================================
# MANAGE UPLOADS
# ============================================================

def _render_manage_uploads(user_id: int):
    st.subheader("Your uploaded documents")

    uploads = get_user_uploads(user_id)

    if not uploads:
        st.info("You haven't uploaded any documents yet.")
        return

    for upload in uploads:
        with st.expander(f"{'✅' if upload.is_processed else '⏳'} {upload.filename}"):
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f"**Type:** {upload.file_type.upper()}")
            c2.markdown(f"**Size:** {upload.file_size / 1024:.1f} KB")
            c3.markdown(f"**Processed:** {'Yes' if upload.is_processed else 'No'}")
            c4.markdown(f"**Uploaded:** {upload.uploaded_at.strftime('%d %b %Y')}")

            if upload.extracted_text:
                stats = get_text_stats(upload.extracted_text)
                st.caption(
                    f"{stats['word_count']:,} words · "
                    f"{stats['page_markers']} pages · "
                    f"{stats['chunk_count']} chunks"
                )

            # Danger zone — delete with confirmation.
            col_del, _ = st.columns([1, 3])
            with col_del:
                confirm_key = f"confirm_del_{upload.id}"
                if st.button("🗑️ Delete", key=f"del_{upload.id}"):
                    st.session_state[confirm_key] = True

            if st.session_state.get(confirm_key):
                st.warning(
                    f"Delete **{upload.filename}** and all its summaries and flashcards?"
                )
                col_yes, col_no, _ = st.columns([1, 1, 4])
                with col_yes:
                    if st.button("Yes, delete", key=f"yes_{upload.id}", type="primary"):
                        success, msg = delete_upload(upload.id, user_id)
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                        del st.session_state[confirm_key]
                        st.rerun()
                with col_no:
                    if st.button("Cancel", key=f"no_{upload.id}"):
                        del st.session_state[confirm_key]
                        st.rerun()
