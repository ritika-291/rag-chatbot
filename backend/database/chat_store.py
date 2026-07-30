from backend.database.db import get_connection
import json
from datetime import datetime
import backend.globals as g

# Import Document class compatible with LangChain vectorstores; provide a
# tiny fallback so static analysis and non-vector setups don't fail.
try:
    from langchain.schema import Document
except Exception:
    class Document:
        def __init__(self, page_content, metadata=None):
            self.page_content = page_content
            self.metadata = metadata or {}


def create_session(title="New Chat", user_id: str | None = None):
    """Create a new session. Optionally associate it with a `user_id`.

    Returns the new session id.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO sessions (user_id, title, token_balance) VALUES (?, ?, ?)",
        (user_id, title, g.DEFAULT_TOKENS)
    )
    session_id = cur.lastrowid

    conn.commit()
    conn.close()
    return session_id


def get_sessions():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, title, created_at, user_id, token_balance FROM sessions ORDER BY id DESC")
    rows = cur.fetchall()

    conn.close()

    result = []
    for r in rows:
        # r -> (id, title, created_at, user_id, token_balance)
        result.append({
            "id": r[0],
            "title": r[1],
            "created_at": r[2],
            "user_id": r[3],
            "token_balance": r[4]
        })

    return result


def get_or_create_session_by_user(user_id: str):
    """Return the most recent session id for `user_id` or create one."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM sessions WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,)
    )

    row = cur.fetchone()
    conn.close()

    if row:
        return row[0]

    return create_session(title=f"Chat with {user_id}", user_id=user_id)


def save_message(session_id, role, content, metadata=None):
    # Convert content safely
    if isinstance(content, (dict, list)):
        content = json.dumps(content)

    # Normalize metadata into a dict so we can inject a timestamp
    meta_obj = {}
    if metadata is not None:
        if isinstance(metadata, dict):
            meta_obj.update(metadata)
        else:
            try:
                meta_obj.update(json.loads(metadata))
            except Exception:
                meta_obj["raw_metadata"] = metadata

    # Add timestamp for chat history referencing
    try:
        meta_obj.setdefault("timestamp", datetime.utcnow().isoformat())
    except Exception:
        pass

    # Store JSON metadata in DB
    try:
        metadata_json = json.dumps(meta_obj)
    except Exception:
        metadata_json = None

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO messages (session_id, role, content, metadata)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, role, content, metadata_json)
    )

    conn.commit()
    conn.close()

    # Index the message into a vector store when available so RAG can
    # use per-session conversation history as retrieval context.
    try:
        # Normalize content to string for embedding
        text = content if isinstance(content, str) else json.dumps(content)

        doc_meta = {"role": role, "session_id": session_id}
        try:
            # merge the normalized metadata object
            if meta_obj:
                doc_meta.update(meta_obj)
        except Exception:
            pass

        doc = Document(page_content=str(text), metadata=doc_meta)

        # Prefer a per-session vector index if present
        session_vec = None
        try:
            session_vec = g.session_vectors.get(session_id)
        except Exception:
            session_vec = None

        if session_vec is not None:
            try:
                session_vec.add_documents([doc])
            except Exception:
                # ignore vector indexing failures
                pass
        else:
            # Fallback: add to global vector DB if available
            try:
                if getattr(g, "vector_db", None) is not None:
                    g.vector_db.add_documents([doc])
            except Exception:
                pass

    except Exception:
        # Never let indexing break chat storage
        pass


def get_messages(session_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT role, content, metadata 
        FROM messages 
        WHERE session_id=? 
        ORDER BY id ASC
        """,
        (session_id,)
    )

    rows = cur.fetchall()
    conn.close()

    result = []
    for role, content, metadata in rows:
        try:
            content = json.loads(content) if content else content
        except:
            pass

        try:
            metadata = json.loads(metadata) if metadata else None
        except:
            metadata = None

        result.append({
            "role": role,
            "content": content,
            "metadata": metadata
        })

    return result


def get_analytics(session_id: int | None = None):
    """Return analytics.

    If `session_id` is provided, return metrics for that session only.
    Otherwise return aggregate metrics across all sessions (legacy behavior).

    Fields (session-specific):
      - session_id: the session id
      - total_tokens_remaining: token_balance for the session or sum across sessions
      - tokens_allocated_estimate: DEFAULT_TOKENS (or DEFAULT_TOKENS * total_chats)
      - tokens_used: allocated - remaining
    """
    conn = get_connection()
    cur = conn.cursor()

    if session_id is not None:
        # per-session metrics
        cur.execute("SELECT COUNT(*), COALESCE(SUM(token_balance),0) FROM sessions WHERE id = ?", (session_id,))
        row = cur.fetchone() or (0, 0)
        total_chats = int(row[0] or 0)
        total_tokens_remaining = int(row[1] or 0)

        try:
            allocated = int(g.DEFAULT_TOKENS) if total_chats > 0 else 0
        except Exception:
            allocated = 0

        tokens_used = max(0, allocated - total_tokens_remaining)

        cur.execute("SELECT COUNT(*) FROM messages WHERE role = 'user' AND session_id = ?", (session_id,))
        q_row = cur.fetchone() or (0,)
        questions_asked = int(q_row[0] or 0)

        conn.close()

        return {
            "session_id": session_id,
            "total_tokens_remaining": total_tokens_remaining,
            "tokens_allocated_estimate": allocated,
            "tokens_used": tokens_used,
            "default_tokens_per_session": int(getattr(g, "DEFAULT_TOKENS", 0)),
        }

    # legacy: global aggregates
    cur.execute("SELECT COUNT(*), COALESCE(SUM(token_balance),0) FROM sessions")
    row = cur.fetchone() or (0, 0)
    total_chats = int(row[0] or 0)
    total_tokens_remaining = int(row[1] or 0)

    try:
        allocated = int(g.DEFAULT_TOKENS) * total_chats
    except Exception:
        allocated = 0

    tokens_used = max(0, allocated - total_tokens_remaining)

    cur.execute("SELECT COUNT(*) FROM messages WHERE role = 'user'")
    q_row = cur.fetchone() or (0,)
    questions_asked = int(q_row[0] or 0)

    conn.close()

    return {
        "total_tokens_remaining": total_tokens_remaining,
        "tokens_allocated_estimate": allocated,
        "tokens_used": tokens_used,
        "default_tokens_per_session": int(getattr(g, "DEFAULT_TOKENS", 0)),
    }


def delete_session(session_id):
    conn = get_connection()
    cur = conn.cursor()

    # Delete messages belonging to the session
    cur.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))

    # Delete the session entry
    cur.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    conn.commit()
    conn.close()


def get_token_balance(session_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT token_balance FROM sessions WHERE id = ?", (session_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return row[0]


def set_token_balance(session_id: int, value: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE sessions SET token_balance = ? WHERE id = ?", (int(value), session_id))
    conn.commit()
    conn.close()


def decrement_tokens(session_id: int, amount: int = 1):
    # Atomically decrement token_balance by amount, but ensure it doesn't go below zero
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT token_balance FROM sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return None
        current = row[0] or 0
        new_val = max(0, int(current) - int(amount))
        cur.execute("UPDATE sessions SET token_balance = ? WHERE id = ?", (new_val, session_id))
        conn.commit()
        return new_val
    finally:
        conn.close()


def update_session_title(session_id: int, title: str):
    """Update the title of an existing chat session."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))
    conn.commit()
    conn.close()