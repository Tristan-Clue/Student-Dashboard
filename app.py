# ============================================================
# app.py
# Main entry point for the Student Productivity Dashboard.
#
# This file:
#   1. Configures the Streamlit page (title, layout, icon)
#   2. Implements authentication checks
#   3. Provides sidebar navigation
#   4. Routes users to different pages based on selection
#   5. Handles login/logout flows
#
# Pages available:
#   - 📊 Dashboard    → home page with stats
#   - 📤 Upload       → document upload and processing
#   - 🎴 Flashcards   → study flashcards
#   - 📝 Summaries    → view AI-generated summaries
#   - ⚙️ Settings      → user preferences
#
# Navigation is handled via Streamlit's multipage system.
# Each page is a separate file in the pages/ folder.
# ============================================================

import streamlit as st
from dotenv import load_dotenv
from auth import is_logged_in, get_current_user, show_logout_button
from database import init_db

# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

# Load .env file — this reads OPENAI_API_KEY, GEMINI_API_KEY, etc.
load_dotenv()

# ============================================================
# INITIALIZE DATABASE
# ============================================================

# Create all database tables on first run.
# This is safe to call multiple times — SQLAlchemy will only
# create tables that don't already exist.
init_db()

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Student Productivity Dashboard",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown(
    """
    <style>
    [data-testid="stSidebarNav"] {
        background-image: url('data:image/svg+xml,...');
        background-repeat: no-repeat;
    }
    .main {
        max-width: 1200px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# AUTHENTICATION CHECK
# ============================================================

if not is_logged_in():
    """
    User is not logged in — show the login/register page.
    """
    st.title("📚 Student Productivity Dashboard")
    st.write("Welcome! Please log in or create an account to get started.")

    # Create tabs for login and registration
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        st.subheader("Login")
        from auth import show_login_form
        show_login_form()

    with tab2:
        st.subheader("Create Account")
        from auth import show_registration_form
        show_registration_form()

else:
    # ── User IS logged in ─────────────────────────────────
    current_user = get_current_user()
    username = current_user.get("username", "User")

    # ── Sidebar Header ────────────────────────────────────
    st.sidebar.title("📚 Dashboard")
    st.sidebar.write(f"**Logged in as:** {username}")

    # ── Logout Button (top of sidebar) ────────────────────
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        show_logout_button()
        st.rerun()

    st.sidebar.divider()

    # ── Navigation Menu ──────────────────────────────────
    st.sidebar.subheader("Navigation")
    page = st.sidebar.radio(
        "Go to:",
        [
            "📊 Dashboard",
            "📤 Upload Documents",
            "🎴 Study Flashcards",
            "📝 View Summaries",
            "⚙️ Settings",
        ],
        label_visibility="collapsed",
    )

    st.sidebar.divider()

    # ── Quick Stats (sidebar) ────────────────────────────
    st.sidebar.subheader("Quick Stats")
    from ai_engine import get_summaries_for_user, get_flashcards_for_user

    user_id = st.session_state.get("user_id")
    summaries = get_summaries_for_user(user_id)
    flashcards = get_flashcards_for_user(user_id)

    col1, col2 = st.sidebar.columns(2)
    col1.metric("Summaries", len(summaries))
    col2.metric("Flashcards", len(flashcards))

    st.sidebar.divider()

    # ── Sidebar Footer ───────────────────────────────────
    st.sidebar.caption("Version 1.0.0 | Student Portfolio")

    # ── Route to Selected Page ───────────────────────────
    if page == "📊 Dashboard":
        from pages.dashboard import show_dashboard
        show_dashboard()

    elif page == "📤 Upload Documents":
        from pages.upload import show_upload_page
        show_upload_page()

    elif page == "🎴 Study Flashcards":
        from pages.flashcards import show_flashcards_page
        show_flashcards_page()

    elif page == "📝 View Summaries":
        from pages.summaries import show_summaries_page
        show_summaries_page()

    elif page == "⚙️ Settings":
        from pages.settings import show_settings_page
        show_settings_page()
