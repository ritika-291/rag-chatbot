import requests
import mimetypes
from config import BACKEND_URL


def upload_file(file, session_id=None):
    # Try to use the provided MIME type, otherwise guess from filename
    content_type = getattr(file, "type", None) or mimetypes.guess_type(file.name)[0] or "application/octet-stream"

    files = {
        "file": (file.name, file.getvalue(), content_type)
    }

    data = {}
    if session_id:
        data["session_id"] = str(session_id)

    return requests.post(f"{BACKEND_URL}/upload", files=files, data=data or None)


def get_sessions():
    return requests.get(f"{BACKEND_URL}/sessions")


def get_session_history(session_id):
    return requests.get(f"{BACKEND_URL}/session/{session_id}")


def delete_session(session_id):
    return requests.delete(f"{BACKEND_URL}/session/{session_id}")


def download_session_pdf(session_id):
    return requests.get(f"{BACKEND_URL}/session/{session_id}/pdf")


def chat(question, session_id):
    return requests.post(
        f"{BACKEND_URL}/chat",
        json={"question": question, "session_id": session_id}
    )


def update_session_title(session_id, title):
    return requests.put(
        f"{BACKEND_URL}/session/{session_id}/title",
        json={"title": title}
    )