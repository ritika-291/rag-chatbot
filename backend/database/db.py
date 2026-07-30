import sqlite3
import os
import backend.globals as g

DB_PATH = "chat.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Include token_balance column with a sensible default for new DBs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        title TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        token_balance INTEGER DEFAULT 1000
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        role TEXT,
        content TEXT,
        metadata TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Migrations: add missing columns to older DBs when possible
    try:
        cursor.execute("PRAGMA table_info(sessions)")
        cols = [row[1] for row in cursor.fetchall()]
        if "user_id" not in cols:
            cursor.execute("ALTER TABLE sessions ADD COLUMN user_id TEXT")
        if "token_balance" not in cols:
            # Use configured default from globals
            cursor.execute(f"ALTER TABLE sessions ADD COLUMN token_balance INTEGER DEFAULT {g.DEFAULT_TOKENS}")
            try:
                cursor.execute(f"UPDATE sessions SET token_balance = {g.DEFAULT_TOKENS} WHERE token_balance IS NULL")
            except Exception:
                pass
        try:
            cursor.execute(f"UPDATE sessions SET token_balance = {g.DEFAULT_TOKENS} WHERE token_balance = 3000")
        except Exception:
            pass
    except Exception:
        # best-effort migration; ignore failures
        pass

    conn.commit()
    conn.close()