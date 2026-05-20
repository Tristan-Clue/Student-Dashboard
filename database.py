# ============================================================
# database.py
# SQLAlchemy engine setup and session factory.
#
# This file is responsible for:
#   1. Creating the SQLite database engine
#   2. Providing a reusable session factory (SessionLocal)
#   3. Providing a Base class that all models inherit from
#   4. Exposing init_db() to create all tables on first run
#
# Other modules import `SessionLocal` and `Base` from here.
# They do NOT import the engine directly.
# ============================================================

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ------------------------------------------------------------
# 1. DATABASE FILE PATH
# ------------------------------------------------------------

# Build an absolute path to the database file so the app
# works regardless of where it is launched from.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(BASE_DIR, "database")
DATABASE_PATH = os.path.join(DATABASE_DIR, "app.db")

# Create the database/ directory if it doesn't exist yet.
os.makedirs(DATABASE_DIR, exist_ok=True)

# SQLite connection URL format:
#   sqlite:///absolute/path/to/file.db
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"


# ------------------------------------------------------------
# 2. ENGINE
# ------------------------------------------------------------

engine = create_engine(
    DATABASE_URL,

    # connect_args is SQLite-specific.
    # check_same_thread=False is required because Streamlit
    # may access the database from different threads.
    connect_args={"check_same_thread": False},

    # echo=True prints all SQL statements to the console.
    # Useful for debugging — set to False in production.
    echo=False,
)


# ------------------------------------------------------------
# 3. SESSION FACTORY
# ------------------------------------------------------------

# SessionLocal is a factory: calling SessionLocal() creates
# a new database session (like a transaction handle).
#
# autocommit=False  → changes are only saved when you call session.commit()
# autoflush=False   → SQLAlchemy won't auto-flush pending changes mid-query
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


# ------------------------------------------------------------
# 4. DECLARATIVE BASE
# ------------------------------------------------------------

# All ORM model classes in models.py will inherit from Base.
# SQLAlchemy uses Base to track which classes map to which tables.
Base = declarative_base()


# ------------------------------------------------------------
# 5. HELPER: get a database session
# ------------------------------------------------------------

def get_db():
    """
    Returns a new SQLAlchemy session.

    Usage pattern (always use try/finally to guarantee close):

        db = get_db()
        try:
            result = db.query(User).all()
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    """
    db = SessionLocal()
    return db


# ------------------------------------------------------------
# 6. INIT: create all tables
# ------------------------------------------------------------

def init_db():
    """
    Creates all database tables defined in models.py.

    This is safe to call multiple times — SQLAlchemy uses
    CREATE TABLE IF NOT EXISTS under the hood, so existing
    tables and data are never overwritten.

    Call this once at app startup (inside app.py).
    """
    # Import models here so SQLAlchemy knows about all tables
    # before it calls create_all(). Without this import,
    # the tables would never be registered with Base.metadata.
    import models  # noqa: F401 — side-effect import

    Base.metadata.create_all(bind=engine)
    print(f"[database] Tables initialised at: {DATABASE_PATH}")
