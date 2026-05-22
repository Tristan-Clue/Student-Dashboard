# ============================================================
# pages/settings.py
# User settings and account management page.
#
# Features:
#   1. Display account info
#   2. Change password
#   3. Study statistics overview
#   4. Danger zone — delete all data
# ============================================================

import streamlit as st

from auth import (
    require_login,
    get_current_user_id,
    get_current_username,
    verify_password,
    hash_password,
    logout_user,
)
from database import get_db
from models import User, Upload, Flashcard, Summary, StudyStat
from flashcards import get_flashcard_stats, get_study_streak


def render():
    require_login()
    user_id  = get_current_user_id()
    username = get_current_username()

    st.title("⚙️ Settings")

    tab_account, tab_stats, tab_danger = st.tabs([
        "Account", "Study Stats", "Danger Zone"
    ])

    with tab_account:
        _render_account(user_id, username)

    with tab_stats:
        _render_stats(user_id)

    with tab_danger:
        _render_danger_zone(user_id)


# ============================================================
# ACCOUNT TAB
# ============================================================

def _render_account(user_id: int, username: str):
    st.subheader("Account information")

    db = get_db()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            st.error("User not found.")
            return

        col1, col2 = st.columns(2)
        col1.markdown(f"**Username:** {user.username}")
        col2.markdown(f"**Email:** {user.email}")
        st.caption(f"Member since: {user.created_at.strftime('%d %B %Y')}")
    finally:
        db.close()

    st.divider()

    # ── Change password ──────────────────────────────────────
    st.subheader("Change password")

    with st.form("change_password_form"):
        current_pw  = st.text_input("Current password",  type="password")
        new_pw      = st.text_input("New password",       type="password",
                                    help="Minimum 6 characters.")
        confirm_pw  = st.text_input("Confirm new password", type="password")
        submitted   = st.form_submit_button("Update password", use_container_width=True)

    if submitted:
        if not current_pw or not new_pw or not confirm_pw:
            st.error("Please fill in all fields.")
        elif new_pw != confirm_pw:
            st.error("New passwords do not match.")
        elif len(new_pw) < 6:
            st.error("New password must be at least 6 characters.")
        else:
            db = get_db()
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if not verify_password(current_pw, user.password_hash):
                    st.error("Current password is incorrect.")
                else:
                    user.password_hash = hash_password(new_pw)
                    db.commit()
                    st.success("Password updated successfully.")
            except Exception as e:
                db.rollback()
                st.error(f"Failed to update password: {e}")
            finally:
                db.close()


# ============================================================
# STUDY STATS TAB
# ============================================================

def _render_stats(user_id: int):
    st.subheader("Your study statistics")

    stats  = get_flashcard_stats(user_id)
    streak = get_study_streak(user_id)

    # ── Overview metrics ─────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    col1.metric("Total flashcards",  stats["total"])
    col2.metric("Total reviews",     stats["total_reviewed"])
    col3.metric("Overall accuracy",  f"{stats['accuracy_pct']}%")

    col4, col5, col6 = st.columns(3)
    col4.metric("Correct answers",   stats["total_correct"])
    col5.metric("Starred cards",     stats["starred"])
    col6.metric("Study streak",      f"{streak} day(s)")

    st.divider()

    # ── Topic breakdown ──────────────────────────────────────
    if stats["by_topic"]:
        st.subheader("Cards by topic")
        import pandas as pd
        df = pd.DataFrame(
            list(stats["by_topic"].items()),
            columns=["Topic", "Cards"]
        ).sort_values("Cards", ascending=False)
        st.bar_chart(df.set_index("Topic"), use_container_width=True)

    # ── Difficulty breakdown ─────────────────────────────────
    st.subheader("Cards by difficulty")
    diff = stats["by_difficulty"]
    c1, c2, c3 = st.columns(3)
    c1.metric("🟢 Easy",   diff.get("easy",   0))
    c2.metric("🟡 Medium", diff.get("medium", 0))
    c3.metric("🔴 Hard",   diff.get("hard",   0))


# ============================================================
# DANGER ZONE TAB
# ============================================================

def _render_danger_zone(user_id: int):
    st.subheader("⚠️ Danger Zone")
    st.warning(
        "Actions here are **permanent and cannot be undone**. "
        "Please be certain before proceeding."
    )

    # ── Delete all flashcards ────────────────────────────────
    st.markdown("#### Delete all flashcards")
    st.caption("Removes all your flashcards. Uploads and summaries are kept.")

    if st.button("🗑️ Delete all flashcards", key="del_cards"):
        st.session_state["confirm_del_cards"] = True

    if st.session_state.get("confirm_del_cards"):
        st.error("Are you sure? This will delete ALL your flashcards.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, delete all cards", key="confirm_cards"):
                db = get_db()
                try:
                    db.query(Flashcard).filter(
                        Flashcard.user_id == user_id
                    ).delete(synchronize_session=False)
                    db.commit()
                    st.success("All flashcards deleted.")
                except Exception as e:
                    db.rollback()
                    st.error(f"Failed: {e}")
                finally:
                    db.close()
                del st.session_state["confirm_del_cards"]
                st.rerun()
        with col2:
            if st.button("Cancel", key="cancel_cards"):
                del st.session_state["confirm_del_cards"]
                st.rerun()

    st.divider()

    # ── Delete account ───────────────────────────────────────
    st.markdown("#### Delete account")
    st.caption(
        "Permanently deletes your account, all uploads, summaries, "
        "flashcards, and study history."
    )

    if st.button("🗑️ Delete my account", key="del_account"):
        st.session_state["confirm_del_account"] = True

    if st.session_state.get("confirm_del_account"):
        st.error("This will permanently delete your account and all data.")
        password_confirm = st.text_input(
            "Enter your password to confirm",
            type="password",
            key="del_account_pw",
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, delete my account", key="confirm_account"):
                db = get_db()
                try:
                    user = db.query(User).filter(User.id == user_id).first()
                    if not verify_password(password_confirm, user.password_hash):
                        st.error("Incorrect password.")
                    else:
                        db.delete(user)
                        db.commit()
                        st.success("Account deleted. Goodbye!")
                        logout_user()
                        st.rerun()
                except Exception as e:
                    db.rollback()
                    st.error(f"Failed: {e}")
                finally:
                    db.close()
        with col2:
            if st.button("Cancel", key="cancel_account"):
                del st.session_state["confirm_del_account"]
                st.rerun()
