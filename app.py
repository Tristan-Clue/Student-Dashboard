# ============================================================
# app.py
# Main entry point for the Student Productivity App.
#
# Responsibilities:
#   1. Initialise the database on first run
#   2. Load environment variables from .env
#   3. Show the auth page if no user is logged in
#   4. Show the sidebar navigation if logged in
#   5. Route to the correct page based on sidebar selection
#
# Run with:  streamlit run app.py
# ============================================================

import os
import streamlit as st
from dotenv import load_dotenv

# ── Load .env file for local development ────────────────────
# On Streamlit Cloud, secrets come from st.secrets instead.
load_dotenv()

# ── Page config (must be the very first Streamlit call) ──────
st.set_page_config(
    page_title       = "StudyAI",
    page_icon        = "📚",
    layout           = "wide",
    initial_sidebar_state = "expanded",
)

# ── Initialise database (creates tables if they don't exist) ─
from database import init_db
init_db()

# ── Import auth helpers ──────────────────────────────────────
from auth import is_logged_in, render_auth_page, render_logout_button


# ============================================================
# HELPER — Custom CSS
# ============================================================

def apply_custom_css():
    """
    Injects a small amount of CSS to polish the default
    Streamlit appearance without overriding the theme.
    """
    st.markdown("""
    <style>
        /* Tighten up sidebar padding */
        section[data-testid="stSidebar"] > div {
            padding-top: 1.5rem;
        }
        /* Make metric labels slightly smaller */
        div[data-testid="stMetricLabel"] p {
            font-size: 0.82rem;
        }
        /* Card-like containers */
        div[data-testid="stExpander"] {
            border-radius: 8px;
        }
        /* Hide the default Streamlit footer */
        footer { visibility: hidden; }
    </style>
    """, unsafe_allow_html=True)


# ============================================================
# HELPER — Sidebar navigation
# ============================================================

PAGES = {
    "🏠  Dashboard":        "dashboard",
    "📤  Upload Document":  "upload",
    "🃏  Flashcard Review": "flashcards",
    "📝  Summaries":        "summaries",
    "⚙️  Settings":         "settings",
}


def render_sidebar() -> str:
    """
    Renders the sidebar with user info, navigation, and logout.

    Returns the key of the selected page (e.g. "dashboard").
    """
    with st.sidebar:
        # ── App branding ────────────────────────────────────
        st.markdown("## 📚 StudyAI")
        st.caption("AI-powered study companion")
        st.divider()

        # ── User info ────────────────────────────────────────
        username = st.session_state.get("username", "Student")
        st.markdown(f"👤 **{username}**")
        st.divider()

        # ── Navigation ───────────────────────────────────────
        st.markdown("**Navigation**")
        selected_label = st.radio(
            label      = "nav",
            options    = list(PAGES.keys()),
            label_visibility = "collapsed",
        )

        # ── Logout button ────────────────────────────────────
        render_logout_button()

    return PAGES[selected_label]


# ============================================================
# PAGE ROUTING
# ============================================================

def route_to_page(page: str):
    """
    Imports and renders the selected page module.

    Pages are imported lazily (inside this function) so the
    app starts fast and only loads what it needs.
    """
    if page == "dashboard":
        import dashboard
        dashboard.render()

    elif page == "upload":
        from page_modules import upload
        upload.render()

    elif page == "flashcards":
        from page_modules import flashcard_review
        flashcard_review.render()

    elif page == "summaries":
        from page_modules import summaries
        summaries.render()

    elif page == "settings":
        from page_modules import settings
        settings.render()


# ============================================================
# MAIN
# ============================================================

def main():
    apply_custom_css()

    # ── Not logged in → show auth page ──────────────────────
    if not is_logged_in():
        render_auth_page()
        return

    # ── Logged in → show navigation and route to page ───────
    selected_page = render_sidebar()
    route_to_page(selected_page)


if __name__ == "__main__":
    main()
