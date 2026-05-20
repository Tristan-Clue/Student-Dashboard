# ============================================================
# auth.py
# Authentication system for the Student Productivity App.
#
# Responsibilities:
#   1. Register new users (with bcrypt password hashing)
#   2. Login existing users (verify password + start session)
#   3. Logout (clear Streamlit session state)
#   4. Session helpers (is_logged_in, get_current_user)
#   5. Streamlit UI forms for login and registration pages
#
# Session state keys used:
#   st.session_state["user_id"]       → int, logged-in user's DB id
#   st.session_state["username"]      → str, display name
#   st.session_state["authenticated"] → bool
# ============================================================

import bcrypt
import streamlit as st

from database import get_db
from models import User


# ============================================================
# SECTION 1 — PASSWORD UTILITIES
# ============================================================

def hash_password(plain_password: str) -> str:
    """
    Hashes a plain-text password using bcrypt.

    bcrypt automatically:
      - Generates a random salt
      - Applies a work factor (cost) to slow down brute-force
      - Embeds the salt into the returned hash string

    Returns a 60-character string safe to store in the database.

    Example:
        hash_password("mypassword123")
        → "$2b$12$KIXo...randomhash..."
    """
    # encode() converts the string to bytes, which bcrypt requires.
    # gensalt() default work factor is 12 — good balance of security/speed.
    password_bytes = plain_password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())

    # Decode back to a string for storage in the SQLite Text column.
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Checks a plain-text password against a stored bcrypt hash.

    Returns True if the password matches, False otherwise.
    Never raises an exception on mismatch — always returns bool.

    Example:
        verify_password("mypassword123", stored_hash) → True
        verify_password("wrongpassword", stored_hash) → False
    """
    try:
        password_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        # If the stored hash is malformed or empty, fail safely.
        return False


# ============================================================
# SECTION 2 — USER REGISTRATION
# ============================================================

def register_user(username: str, email: str, password: str) -> tuple[bool, str]:
    """
    Creates a new user account in the database.

    Validates:
      - Username and email are not already taken
      - Password meets minimum length requirement

    Returns:
        (True, "success message")  on success
        (False, "error message")   on failure

    Usage:
        success, message = register_user("alice", "alice@example.com", "secret123")
    """
    # ── Basic input validation ──────────────────────────────
    username = username.strip()
    email = email.strip().lower()

    if len(username) < 3:
        return False, "Username must be at least 3 characters."

    if len(username) > 50:
        return False, "Username must be 50 characters or fewer."

    if "@" not in email or "." not in email:
        return False, "Please enter a valid email address."

    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    # ── Check for existing username / email ─────────────────
    db = get_db()
    try:
        existing_username = db.query(User).filter(
            User.username == username
        ).first()
        if existing_username:
            return False, f"Username '{username}' is already taken."

        existing_email = db.query(User).filter(
            User.email == email
        ).first()
        if existing_email:
            return False, "An account with that email already exists."

        # ── Hash password and create user ───────────────────
        new_user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return True, f"Account created! Welcome, {username}."

    except Exception as e:
        db.rollback()
        return False, f"Registration failed: {str(e)}"
    finally:
        db.close()


# ============================================================
# SECTION 3 — LOGIN
# ============================================================

def login_user(username: str, password: str) -> tuple[bool, str]:
    """
    Verifies credentials and starts a Streamlit session on success.

    On success:
      - Sets st.session_state["authenticated"] = True
      - Sets st.session_state["user_id"] = user.id
      - Sets st.session_state["username"] = user.username

    Returns:
        (True, "Welcome back!")  on success
        (False, "error message") on failure
    """
    username = username.strip()

    if not username or not password:
        return False, "Please enter both username and password."

    db = get_db()
    try:
        user = db.query(User).filter(
            User.username == username,
            User.is_active == True,        # noqa: E712 — SQLAlchemy needs ==
        ).first()

        # Use a generic error message — don't reveal whether the
        # username exists or the password was wrong (security best practice).
        if not user:
            return False, "Invalid username or password."

        if not verify_password(password, user.password_hash):
            return False, "Invalid username or password."

        # ── Write session state ─────────────────────────────
        st.session_state["authenticated"] = True
        st.session_state["user_id"] = user.id
        st.session_state["username"] = user.username

        return True, f"Welcome back, {user.username}!"

    except Exception as e:
        return False, f"Login failed: {str(e)}"
    finally:
        db.close()


# ============================================================
# SECTION 4 — LOGOUT
# ============================================================

def logout_user():
    """
    Clears all authentication-related session state keys.

    Call this when the user clicks the logout button.
    Streamlit will re-render the page, showing the login form.
    """
    for key in ["authenticated", "user_id", "username"]:
        if key in st.session_state:
            del st.session_state[key]


# ============================================================
# SECTION 5 — SESSION HELPERS
# ============================================================

def is_logged_in() -> bool:
    """
    Returns True if a user is currently authenticated.

    Use this at the top of every page to gate access:

        if not is_logged_in():
            st.warning("Please log in to continue.")
            st.stop()
    """
    return st.session_state.get("authenticated", False)


def get_current_user_id() -> int | None:
    """
    Returns the logged-in user's database ID, or None if not logged in.

    Usage:
        user_id = get_current_user_id()
        uploads = db.query(Upload).filter(Upload.user_id == user_id).all()
    """
    return st.session_state.get("user_id", None)


def get_current_username() -> str | None:
    """
    Returns the logged-in user's display name, or None.

    Usage:
        st.write(f"Hello, {get_current_username()}!")
    """
    return st.session_state.get("username", None)


def require_login():
    """
    Convenience guard: stops page execution if not logged in.

    Place at the top of any page that requires authentication:

        from auth import require_login
        require_login()
        # ... rest of page code only runs if logged in
    """
    if not is_logged_in():
        st.warning("Please log in to access this page.")
        st.stop()


# ============================================================
# SECTION 6 — STREAMLIT UI COMPONENTS
# ============================================================

def render_login_form():
    """
    Renders the login form inside whatever Streamlit container
    it is called from (e.g. a column, expander, or full page).

    On successful login, calls st.rerun() to reload the app
    so the dashboard is shown immediately.
    """
    st.subheader("Log in")

    # Use a Streamlit form so pressing Enter submits it.
    with st.form("login_form", clear_on_submit=False):
        username = st.text_input(
            "Username",
            placeholder="your_username",
            autocomplete="username",
        )
        password = st.text_input(
            "Password",
            type="password",
            placeholder="••••••••",
            autocomplete="current-password",
        )
        submitted = st.form_submit_button("Log in", use_container_width=True)

    if submitted:
        if not username or not password:
            st.error("Please fill in both fields.")
        else:
            success, message = login_user(username, password)
            if success:
                st.success(message)
                # Rerun triggers a full re-render so the dashboard
                # appears without the user needing to click anything.
                st.rerun()
            else:
                st.error(message)


def render_register_form():
    """
    Renders the registration form.

    On successful registration, shows a success message and
    prompts the user to log in (does not auto-login for clarity).
    """
    st.subheader("Create an account")

    with st.form("register_form", clear_on_submit=True):
        username = st.text_input(
            "Username",
            placeholder="choose_a_username",
            help="3–50 characters.",
        )
        email = st.text_input(
            "Email",
            placeholder="you@example.com",
        )
        password = st.text_input(
            "Password",
            type="password",
            placeholder="at least 6 characters",
            help="Minimum 6 characters.",
        )
        password_confirm = st.text_input(
            "Confirm password",
            type="password",
            placeholder="repeat your password",
        )
        submitted = st.form_submit_button(
            "Create account", use_container_width=True
        )

    if submitted:
        # Client-side password match check before hitting the DB.
        if password != password_confirm:
            st.error("Passwords do not match.")
        else:
            success, message = register_user(username, email, password)
            if success:
                st.success(message + " Please log in below.")
            else:
                st.error(message)


def render_auth_page():
    """
    Full authentication page with toggle between Login and Register.

    This is what app.py renders when no user is logged in.

    Layout:
      - Centered logo / app title
      - Tab switcher: "Log in" | "Register"
      - Appropriate form under each tab
    """
    # Centre the auth card using columns.
    _, col, _ = st.columns([1, 2, 1])

    with col:
        st.markdown("## 📚 StudyAI")
        st.caption("Your AI-powered study companion")
        st.divider()

        # Tabs let the user switch between login and registration
        # without navigating to a different page.
        tab_login, tab_register = st.tabs(["Log in", "Register"])

        with tab_login:
            render_login_form()

        with tab_register:
            render_register_form()


def render_logout_button():
    """
    Renders a compact logout button, designed for the sidebar.

    Usage in app.py:
        with st.sidebar:
            render_logout_button()
    """
    st.sidebar.divider()
    if st.sidebar.button("Log out", use_container_width=True):
        logout_user()
        st.rerun()
