from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse, FileResponse
from fastapi import HTTPException
from starlette.background import BackgroundTask
import io
import os
import backend.globals as g
from backend.database.chat_store import get_sessions, get_messages, delete_session
from backend.database.chat_store import get_analytics
from backend.services.pdf_generator import messages_to_pdf_bytes, messages_to_pdf_file

router = APIRouter()


@router.get("/sessions")
def sessions():
    return get_sessions()


@router.get("/session/{session_id}")
def session_messages(session_id: int):
    return get_messages(session_id)


@router.delete("/session/{session_id}")
def remove_session(session_id: int):
    # Remove from DB
    delete_session(session_id)

    # Remove from in-memory session vectors cache if present
    try:
        if session_id in g.session_vectors:
            del g.session_vectors[session_id]
    except Exception:
        pass

    return {"deleted": session_id}


@router.get("/session/{session_id}/pdf")
def download_session_pdf(session_id: int):
    # Fetch messages and render to PDF bytes
    messages = get_messages(session_id)
    try:
        # For large sessions, write to a temp file and stream it to avoid memory pressure
        pdf_path = messages_to_pdf_file(messages, title=f"Chat {session_id}")

        def _cleanup(path: str):
            try:
                os.remove(path)
            except Exception:
                pass

        return FileResponse(pdf_path, media_type="application/pdf", filename=f"chat_{session_id}.pdf", background=BackgroundTask(_cleanup, pdf_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics")
def analytics(session_id: int | None = None):
    try:
        return get_analytics(session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/session/{session_id}/title")
def update_title(session_id: int, title: str = Body(..., embed=True)):
    from backend.database.chat_store import update_session_title
    try:
        update_session_title(session_id, title)
        return {"updated": session_id, "title": title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))