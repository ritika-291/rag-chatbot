import json
from api.client import get_session_history

def load_history(session_id):
    try:
        res = get_session_history(session_id)

        if res.status_code == 200:
            msgs = res.json()
            transformed = []

            for m in msgs:
                role = m.get("role")
                content = m.get("content") or ""
                metadata = m.get("metadata") or {}

                transformed.append({"role": role, "content": content})

            return transformed

    except Exception as e:
        print(f"Error loading history: {e}")

    return []