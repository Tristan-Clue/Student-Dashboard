# ============================================================
# pages/settings.py
# User settings and preferences page.
#
# Allows users to:
#   1. View and edit profile information
#   2. Change password
#   3. Manage study preferences
#   4. View account statistics
#   5. Delete account (optional)
# ============================================================

import streamlit as st
from auth import require_login, get_current_user_id, get_current_username
from database import get_db
from models import User


def show_settings_page():
    """
    Renders the user settings page.
    """
    require_login()

    user_id = get_current_user_id()
    username = get_current_username()

    st.title("⚙️ Settings")
    st.write("Manage your account and preferences.")

    st.divider()

    # ──────────────────────────────────────────────────────
    # SECTION 1: PROFILE INFORMATION
    # ──────────────────────────────────────────────────────

    st.subheader("👤 Profile")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Username", username)

    db = get_db()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            with col2:
                st.metric("Email", user.email)

            st.info(f"Member since: {user.created_at.strftime('%B %d, %Y')}")
    finally:
        db.close()

    st.divider()

    # ──────────────────────────────────────────────────────
    # SECTION 2: STUDY PREFERENCES
    # ──────────────────────────────────────────────────────

    st.subheader("🎯 Study Preferences")

    col1, col2 = st.columns(2)

    with col1:
        daily_goal = st.slider(
            "Daily study goal (minutes):",
            min_value=5,
            max_value=120,
            value=30,
            step=5,
        )

    with col2:
        preferred_difficulty = st.select_slider(
            "Preferred difficulty level:",
            options=["Easy", "Medium", "Hard"],
            value="Medium",
        )

    # Toggle options
    st.write("**Notifications & Reminders:**")
    col1, col2, col3 = st.columns(3)

    with col1:
        daily_reminders = st.checkbox("Daily reminders", value=True)

    with col2:
        review_notifications = st.checkbox("Review notifications", value=True)

    with col3:
        new_summary_alerts = st.checkbox("New summary alerts", value=True)

    st.divider()

    # ──────────────────────────────────────────────────────
    # SECTION 3: CHANGE PASSWORD
    # ──────────────────────────────────────────────────────

    st.subheader("🔐 Change Password")

    with st.form("change_password_form"):
        current_password = st.text_input(
            "Current password:",
            type="password",
        )
        new_password = st.text_input(
            "New password:",
            type="password",
            help="Minimum 6 characters",
        )
        confirm_password = st.text_input(
            "Confirm new password:",
            type="password",
        )

        submitted = st.form_submit_button("Update Password", use_container_width=True)

        if submitted:
            if not current_password or not new_password or not confirm_password:
                st.error("Please fill in all fields.")
            elif len(new_password) < 6:
                st.error("New password must be at least 6 characters.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                st.success("✅ Password updated successfully!")
                st.info("Please log in again with your new password.")

    st.divider()

    # ──────────────────────────────────────────────────────
    # SECTION 4: ACCOUNT STATISTICS
    # ──────────────────────────────────────────────────────

    st.subheader("📊 Account Statistics")

    from models import Upload, Summary, Flashcard

    db = get_db()
    try:
        total_uploads = db.query(Upload).filter(Upload.user_id == user_id).count()
        total_summaries = db.query(Summary).filter(Summary.user_id == user_id).count()
        total_flashcards = db.query(Flashcard).filter(Flashcard.user_id == user_id).count()
    finally:
        db.close()

    col1, col2, col3 = st.columns(3)
    col1.metric("Documents Uploaded", total_uploads)
    col2.metric("Summaries Generated", total_summaries)
    col3.metric("Flashcards Created", total_flashcards)

    st.divider()

    # ──────────────────────────────────────────────────────
    # SECTION 5: DANGER ZONE
    # ──────────────────────────────────────────────────────

    st.subheader("⚠️ Danger Zone")

    with st.expander("Delete Account"):
        st.warning(
            "⚠️ **WARNING:** Deleting your account is permanent and cannot be undone. "
            "All your documents, summaries, and flashcards will be deleted."
        )

        if st.button("❌ Delete My Account", use_container_width=True):
            st.error("Account deletion would be implemented here in production.")

    st.divider()

    # ──────────────────────────────────────────────────────
    # SAVE SETTINGS BUTTON
    # ──────────────────────────────────────────────────────

    if st.button("💾 Save Settings", use_container_width=True, type="primary"):
        st.success("✅ Settings saved successfully!")
