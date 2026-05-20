# ============================================================
# pages/upload.py
# Document upload and processing page.
#
# Allows users to:
#   1. Upload PDF, TXT, or DOCX files
#   2. Validate file size and format
#   3. Extract text from uploaded documents
#   4. Trigger AI processing (summary, flashcards, concepts)
#   5. View processing status and results
# ============================================================

import streamlit as st
from auth import require_login, get_current_user_id
from pdf_parser import process_upload
from ai_engine import process_document


def show_upload_page():
    """
    Renders the document upload page.
    """
    require_login()

    user_id = get_current_user_id()

    st.title("📤 Upload Documents")
    st.write(
        "Upload study materials (PDF, TXT, or DOCX) and let AI generate "
        "summaries, flashcards, and key concepts."
    )

    st.divider()

    # ──────────────────────────────────────────────────────
    # FILE UPLOAD SECTION
    # ──────────────────────────────────────────────────────

    st.subheader("📁 Choose a File")

    uploaded_file = st.file_uploader(
        "Upload a document",
        type=["pdf", "txt", "docx"],
        help="Supported formats: PDF, TXT, DOCX (max 20 MB)",
    )

    if uploaded_file:
        st.info(f"📄 **File selected:** {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")

        # ── Process button ──────────────────────────────────
        if st.button("⚙️ Process Document", use_container_width=True):
            with st.spinner("Uploading and processing..."):
                try:
                    # Step 1: Save file and extract text
                    success, message, upload = process_upload(
                        uploaded_file=uploaded_file,
                        user_id=user_id,
                    )

                    if not success:
                        st.error(f"❌ Upload failed: {message}")
                    else:
                        st.success(f"✅ Document uploaded successfully!")
                        st.info("📊 Processing with AI — generating summary and flashcards...")

                        # Step 2: Run AI pipeline
                        ai_success, ai_results = process_document(
                            upload_id=upload.id,
                            user_id=user_id,
                        )

                        if not ai_success:
                            st.error(f"❌ AI processing failed: {ai_results.get('error', 'Unknown error')}")
                        else:
                            # Display results
                            st.success("✅ AI processing complete!")

                            # Summary
                            if "summary" in ai_results and ai_results["summary"]:
                                st.subheader("📝 Generated Summary")
                                summary_text = ai_results["summary"].summary_text
                                st.write(summary_text[:500] + "..." if len(summary_text) > 500 else summary_text)
                                with st.expander("Read full summary"):
                                    st.write(summary_text)

                            # Key Concepts
                            if "concepts" in ai_results and ai_results["concepts"]:
                                st.subheader("🔑 Key Concepts")
                                concepts = ai_results["concepts"]
                                cols = st.columns(min(3, len(concepts)))
                                for i, concept in enumerate(concepts[:9]):
                                    cols[i % 3].write(f"• {concept}")

                            # Flashcards
                            if "flashcards" in ai_results and ai_results["flashcards"]:
                                st.subheader("🎴 Generated Flashcards")
                                num_cards = len(ai_results["flashcards"])
                                st.success(f"✅ Created {num_cards} flashcards!")

                            # Tokens used
                            if "tokens_used" in ai_results:
                                st.caption(f"🔌 Tokens used: {ai_results['tokens_used']}")

                            # Warning if flashcards failed
                            if "fc_warning" in ai_results:
                                st.warning(f"⚠️ {ai_results['fc_warning']}")

                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

    st.divider()

    # ──────────────────────────────────────────────────────
    # INSTRUCTIONS & TIPS
    # ──────────────────────────────────────────────────────

    with st.expander("ℹ️ How it works"):
        st.markdown("""
        1. **Upload** a study document (PDF, TXT, or DOCX)
        2. **Extract** — text is automatically extracted from the document
        3. **AI Processing** — our AI:
           - 📝 Generates a concise summary
           - 🔑 Extracts key concepts
           - 🎴 Creates study flashcards
        4. **Review** — view all results and start studying!

        **Tips for best results:**
        - Use clear, well-formatted documents
        - Longer documents get better summaries
        - Flashcards are generated from the main content
        """)

    with st.expander("💾 Supported formats"):
        st.markdown("""
        - **PDF** — PDFs with text layers (scanned PDFs may not work)
        - **TXT** — Plain text files
        - **DOCX** — Microsoft Word documents (optional support)
        """)
