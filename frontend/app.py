import os

if "CHAINLIT_AUTH_SECRET" not in os.environ:
    os.environ["CHAINLIT_AUTH_SECRET"] = "secret-key-32-chars-long-or-longer-to-sign-jwt-tokens-12345!"
import chainlit as cl
import requests
import base64
import json
import re
import mimetypes
import ast
from typing import Optional, List, Dict
import chainlit.data as cl_data
from chainlit.data import BaseDataLayer
from chainlit.types import PaginatedResponse, ThreadDict, PageInfo
from fastapi import Response
from config import BACKEND_URL
from utils.speech import listen_to_mic
from utils.tts import speak_text
from api.client import upload_file, get_sessions, delete_session, download_session_pdf, update_session_title, get_session_history

FALLBACK_SUGGESTIONS = [
    "Tell me more",
    "Give an example",
    "Explain simply"
]

class ChainlitFileWrapper:
    def __init__(self, cl_file):
        self.name = cl_file.name
        self.type = mimetypes.guess_type(cl_file.name)[0] or "application/octet-stream"
        with open(cl_file.path, "rb") as f:
            self._content = f.read()

    def getvalue(self):
        return self._content

# Thread ID mapping dictionary (UUID (str) -> session_id (int))
thread_id_map = {}

def resolve_session_id(thread_id: str) -> Optional[int]:
    if not thread_id:
        return None
    if thread_id.isdigit():
        return int(thread_id)
    return thread_id_map.get(thread_id)

class BackendDataLayer(BaseDataLayer):
    async def get_user(self, identifier: str) -> Optional[cl.PersistedUser]:
        return cl.PersistedUser(id=identifier, identifier=identifier, createdAt="2026-06-19T00:00:00Z")

    async def create_user(self, user: cl.User) -> cl.PersistedUser:
        return cl.PersistedUser(id=user.identifier, identifier=user.identifier, createdAt="2026-06-19T00:00:00Z")

    async def create_element(self, *args, **kwargs):
        pass

    async def delete_element(self, *args, **kwargs):
        pass

    async def get_element(self, *args, **kwargs):
        return None

    async def delete_feedback(self, *args, **kwargs):
        pass

    async def get_favorite_steps(self, *args, **kwargs):
        return []

    async def create_step(self, step_dict):
        pass

    async def update_step(self, step_dict):
        pass

    async def delete_step(self, step_id: str):
        pass

    async def get_thread_author(self, thread_id: str) -> str:
        return "default"

    async def delete_thread(self, thread_id: str):
        session_id = resolve_session_id(thread_id)
        if session_id:
            try:
                delete_session(session_id)
            except Exception as e:
                print(f"Error deleting session {session_id}: {e}")

    async def list_threads(self, pagination, filters) -> PaginatedResponse[ThreadDict]:
        try:
            res = get_sessions()
            if res.status_code == 200:
                sessions = res.json()
                threads = []
                for s in sessions:
                    if isinstance(s, dict):
                        sid = str(s.get("id"))
                        title = s.get("title", f"Session {sid}")
                        created_at = s.get("created_at")
                    else:
                        sid = str(s[0])
                        title = s[1] if len(s) > 1 else f"Session {sid}"
                        created_at = None
                        
                    # Filter matching search query if any
                    search_query = None
                    if filters:
                        for attr in ["search", "query", "name"]:
                            val = getattr(filters, attr, None)
                            if val:
                                search_query = str(val)
                                break
                    if search_query and search_query.lower() not in title.lower():
                        continue
                        
                    threads.append({
                        "id": sid,
                        "name": title,
                        "createdAt": created_at or "2026-06-19T00:00:00Z",
                        "userIdentifier": "default",
                        "steps": []
                    })
                
                # Sort descending by ID
                try:
                    threads.sort(key=lambda t: int(t["id"]), reverse=True)
                except Exception:
                    pass
                return PaginatedResponse(
                    data=threads,
                    pageInfo=PageInfo(hasNextPage=False, startCursor=None, endCursor=None)
                )
        except Exception as e:
            print(f"Error listing threads: {e}")
        return PaginatedResponse(
            data=[],
            pageInfo=PageInfo(hasNextPage=False, startCursor=None, endCursor=None)
        )

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        session_id = resolve_session_id(thread_id)
        if not session_id:
            return None
        
        # Ensure mapping is maintained
        thread_id_map[thread_id] = session_id
        
        try:
            res = get_session_history(session_id)
            history = []
            if res.status_code == 200:
                for m in res.json():
                    history.append({
                        "role": m.get("role"),
                        "content": m.get("content") or ""
                    })
            steps = []
            for idx, msg in enumerate(history):
                role = msg.get("role")
                content = msg.get("content")
                steps.append({
                    "id": f"{thread_id}_{idx}",
                    "threadId": thread_id,
                    "name": "User" if role == "user" else "Assistant",
                    "type": "user_message" if role == "user" else "assistant_message",
                    "output": content,
                    "input": "",
                    "createdAt": None
                })
            
            title = f"Session {session_id}"
            res = get_sessions()
            if res.status_code == 200:
                for s in res.json():
                    sid = s.get("id") if isinstance(s, dict) else s[0]
                    if int(sid) == session_id:
                        title = s.get("title") if isinstance(s, dict) else (s[1] if len(s) > 1 else title)
                        break
                        
            return {
                "id": thread_id,
                "name": title,
                "createdAt": "2026-06-19T00:00:00Z",
                "userIdentifier": "default",
                "steps": steps
            }
        except Exception as e:
            print(f"Error loading thread {thread_id}: {e}")
        return None

    async def update_thread(self, thread_id: str, name: Optional[str] = None, user_id: Optional[str] = None, metadata: Optional[dict] = None, tags: Optional[list[str]] = None):
        session_id = resolve_session_id(thread_id)
        if session_id and name:
            try:
                update_session_title(session_id, name)
            except Exception as e:
                print(f"Error updating session {session_id} title in update_thread: {e}")

    async def upsert_feedback(self, feedback):
        return "feedback_id"

    async def close(self):
        pass

    async def build_debug_url(self) -> str:
        return ""

@cl.data_layer
def get_data_layer():
    return BackendDataLayer()

@cl.header_auth_callback
def header_auth_callback(headers: Dict) -> Optional[cl.User]:
    return cl.User(identifier="default")

from chainlit.server import app

@app.get("/api/token_usage")
def get_token_usage_api(session_id: Optional[str] = None):
    try:
        url = f"{BACKEND_URL}/analytics"
        resolved_id = None
        if session_id:
            resolved_id = resolve_session_id(session_id)
            if not resolved_id and session_id.isdigit():
                resolved_id = int(session_id)
        if resolved_id:
            url = f"{url}?session_id={resolved_id}"
        aresp = requests.get(url)
        if aresp.status_code == 200:
            an = aresp.json()
            if not resolved_id:
                allocated = an.get("default_tokens_per_session", an.get("tokens_allocated_estimate", 0)) or 0
                used = 0
            else:
                allocated = an.get("tokens_allocated_estimate", 0) or 0
                used = an.get("tokens_used", 0) or 0
            return {
                "allocated": allocated,
                "used": used,
                "remaining": max(0, allocated - used)
            }
    except Exception:
        pass
    return {"allocated": 0, "used": 0, "remaining": 0}

# Move token usage route to the front
app.routes.insert(0, app.routes.pop())

@app.get("/api/download_chat/{thread_id}")
def download_chat_api(thread_id: str):
    session_id = resolve_session_id(thread_id)
    if not session_id and thread_id.isdigit():
        session_id = int(thread_id)
        
    if not session_id:
        return Response(content="Session not found or not initialized", status_code=404)
        
    try:
        resp = download_session_pdf(session_id)
        if resp.status_code == 200:
            return Response(
                content=resp.content,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=chat_{session_id}.pdf"
                }
            )
        else:
            return Response(content=f"Error downloading PDF: {resp.status_code}", status_code=resp.status_code)
    except Exception as e:
        return Response(content=str(e), status_code=500)

# Move download route to the front
app.routes.insert(0, app.routes.pop())

@app.get("/api/welcome_markdown")
def get_welcome_markdown_api():
    paths = ["chainlit.md", "frontend/chainlit.md"]
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        return {"markdown": content}
            except Exception as e:
                print(f"Error reading welcome markdown from {path}: {e}")
    return {"markdown": "# Hello! 👋 DocBuddy"}

# Move welcome markdown route to the front
app.routes.insert(0, app.routes.pop())

@cl.on_chat_start
async def on_chat_start():
    thread_id = cl.context.session.thread_id
    session_id = resolve_session_id(thread_id)
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("token_exhausted", False)
    pass


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict):
    thread_id = thread["id"]
    session_id = resolve_session_id(thread_id)
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("token_exhausted", False)
    
    ws_thread_id = cl.context.session.thread_id
    if ws_thread_id:
        thread_id_map[ws_thread_id] = session_id

@cl.action_callback("trigger_mic")
async def on_trigger_mic(action: cl.Action):
    if cl.user_session.get("token_exhausted"):
        await cl.Message(content="❌ Token balance exhausted for this chat. Start a new conversation to continue.").send()
        return
        
    listen_msg = cl.Message(content="🎤 Listening via microphone...")
    await listen_msg.send()
    
    try:
        spoken_text = listen_to_mic()
    except Exception:
        spoken_text = ""
        
    await listen_msg.remove()
    transcript = spoken_text or "(could not transcribe)"
    await cl.Message(author="User", content=transcript, type="user_message").send()
    
    if spoken_text and str(spoken_text).strip():
        await process_chat(spoken_text, is_mic=True)

@cl.on_audio_start
async def on_audio_start():
    cl.user_session.set("audio_buffer", bytes())
    return True

@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    if chunk.isStart:
        cl.user_session.set("audio_buffer", chunk.data)
    else:
        buffer = cl.user_session.get("audio_buffer")
        if buffer is not None:
            cl.user_session.set("audio_buffer", buffer + chunk.data)

@cl.on_audio_end
async def on_audio_end():
    if cl.user_session.get("token_exhausted"):
        await cl.Message(content="❌ Token balance exhausted for this chat. Start a new conversation to continue.").send()
        return

    buffer = cl.user_session.get("audio_buffer")
    if not buffer:
        return
        
    import speech_recognition as sr
    import asyncio
    
    # Run transcription in a thread to avoid blocking
    def transcribe(audio_bytes):
        try:
            # Chainlit sends raw PCM audio, 24000Hz, 16-bit (2 bytes)
            audio_data = sr.AudioData(audio_bytes, 24000, 2)
            recognizer = sr.Recognizer()
            return recognizer.recognize_google(audio_data)
        except Exception as e:
            print("STT Error:", e)
            return ""

    processing_msg = cl.Message(content="⏳ Transcribing audio...")
    await processing_msg.send()
    
    spoken_text = await asyncio.to_thread(transcribe, buffer)
    await processing_msg.remove()
    
    transcript = spoken_text or "(could not transcribe audio)"
    await cl.Message(author="User", content=transcript, type="user_message").send()
    
    if spoken_text and str(spoken_text).strip():
        await process_chat(spoken_text, is_mic=True)

@cl.action_callback("download_pdf")
async def on_download_pdf(action: cl.Action):
    session_id = cl.user_session.get("session_id")
    if not session_id:
        await cl.Message(content="❌ No active session to download. Please start a chat first.").send()
        return
    try:
        resp = download_session_pdf(session_id)
        if resp.status_code == 200:
            pdf_bytes = resp.content
            file_element = cl.File(content=pdf_bytes, name=f"chat_{session_id}.pdf")
            await cl.Message(
                content=f"📥 Download PDF export for session {session_id}:",
                elements=[file_element]
            ).send()
        else:
            await cl.Message(content=f"❌ Download failed: {resp.status_code}").send()
    except Exception as e:
        await cl.Message(content=f"❌ Download error: {e}").send()

@cl.action_callback("suggestion")
async def on_suggestion(action: cl.Action):
    await action.remove()
    payload = getattr(action, "payload", {}) or {}
    suggestion_text = payload.get("value") or getattr(action, "label", None) or ""
    await cl.Message(author="User", content=suggestion_text, type="user_message").send()
    await process_chat(suggestion_text)

@cl.action_callback("hitl_ask_human")
async def on_hitl_ask_human(action: cl.Action):
    await action.remove()
    payload = getattr(action, "payload", {}) or {}
    question = payload.get("question", "")
    await cl.Message(
        content=f"📨 **Question Routed to Human Support Queue:**\n\n*\"{question}\"*\n\nAn operator will review this and respond shortly."
    ).send()

@cl.action_callback("hitl_web_search")
async def on_hitl_web_search(action: cl.Action):
    await action.remove()
    payload = getattr(action, "payload", {}) or {}
    question = payload.get("question", "")
    query = f"Search the web for: {question}"
    await cl.Message(author="User", content=query, type="user_message").send()
    await process_chat(query)

@cl.action_callback("hitl_rephrase")
async def on_hitl_rephrase(action: cl.Action):
    await action.remove()
    await cl.Message(
        content="✍️ Please try rephrasing your question to be more specific or asking about a different topic."
    ).send()

@cl.on_message
async def main(message: cl.Message):
    thread_id = cl.context.session.thread_id
    session_id = resolve_session_id(thread_id)
    
    # Process spontaneous file uploads
    if message.elements:
        indexing_msg = cl.Message(content="Processing & indexing document(s)...")
        await indexing_msg.send()
        
        success_files = []
        failed_files = []
        
        for element in message.elements:
            if getattr(element, "path", None):
                wrapped = ChainlitFileWrapper(element)
                try:
                    res = upload_file(wrapped, session_id)
                    if res.status_code == 200:
                        payload = res.json() if res.content else {}
                        if isinstance(payload, dict) and payload.get("session_id"):
                            session_id = payload.get("session_id")
                            cl.user_session.set("session_id", session_id)
                            thread_id_map[thread_id] = session_id
                        success_files.append(element.name)
                    else:
                        try:
                            err_detail = res.json().get("detail")
                        except Exception:
                            err_detail = None
                        if not err_detail:
                            err_detail = f"Status code {res.status_code}"
                        failed_files.append(f"{element.name} (Error: {err_detail})")
                except Exception as e:
                    failed_files.append(f"{element.name} ({e})")
                    
        await indexing_msg.remove()
        
        status_msg = ""
        if success_files:
            status_msg += f"✅ **Successfully indexed:** {', '.join(success_files)}\n"
        if failed_files:
            status_msg += f"❌ **Failed to index:** {', '.join(failed_files)}\n"
            
        await cl.Message(content=status_msg).send()
        
    if message.content:
        await process_chat(message.content)

async def process_chat(prompt: str, is_mic: bool = False):
    if cl.user_session.get("token_exhausted"):
        await cl.Message(content="❌ Token balance exhausted for this chat. Start a new conversation to continue.").send()
        return
        
    thread_id = cl.context.session.thread_id
    session_id = resolve_session_id(thread_id)
    
    # Pre-populate session state messages list
    messages = cl.user_session.get("messages") or []
    messages.append({"role": "user", "content": prompt})
    cl.user_session.set("messages", messages)
    
    msg = cl.Message(content="", author="Assistant")
    await msg.send()
    
    full_text = ""
    streaming_error = False
    
    def sanitize_for_tts(text: str) -> str:
        if not text:
            return text
        try:
            return text.encode('ascii', errors='ignore').decode('ascii')
        except Exception:
            return re.sub(r'[^\x20-\x7E]', '', text)
 
    try:
        response = requests.post(
            f"{BACKEND_URL}/chat",
            json={"question": prompt, "session_id": session_id},
            stream=True,
        )
        
        try:
            if response is not None:
                token_exh = response.headers.get("X-Token-Exhausted") or response.headers.get("x-token-exhausted")
                if token_exh and str(token_exh).lower() == "true":
                    cl.user_session.set("token_exhausted", True)
        except Exception:
            pass

        if response is None:
            await cl.Message(content="❌ No response from backend.").send()
            streaming_error = True
        elif response.status_code != 200:
            try:
                detail = response.json().get("detail")
            except Exception:
                detail = response.text
            await cl.Message(content=f"❌ Chat error: {detail}").send()
            response.close()
            streaming_error = True
            
        llm_error = None
        conf_score = None
        conf_level = None
        suggestions = None
        
        if response is not None and not streaming_error:
            llm_error = response.headers.get("X-LLM-Error")
            
        # Parse stream body and extract metadata using a single-loop consumer
        metadata_payload = None
        if not streaming_error:
            buffer = ""
            marker = "[METADATA]:"
            marker_len = len(marker)
            
            for chunk in response.iter_content(chunk_size=1024, decode_unicode=True):
                if chunk:
                    buffer += chunk
                    
                    if marker not in buffer:
                        if len(buffer) > marker_len:
                            safe_length = len(buffer) - marker_len
                            safe_text = buffer[:safe_length]
                            diff = safe_text[len(full_text):]
                            if diff:
                                full_text += diff
                                await msg.stream_token(diff)
                    else:
                        normal_text, json_part = buffer.split(marker, 1)
                        diff = normal_text[len(full_text):]
                        if diff:
                            full_text += diff
                            await msg.stream_token(diff)

            # Process metadata or final buffer flush after stream ends
            if marker in buffer:
                normal_text, json_part = buffer.split(marker, 1)
                try:
                    metadata_payload = json.loads(json_part.strip())
                except Exception:
                    print(f"[ERROR] Failed to parse metadata JSON: {json_part}")
            else:
                diff = buffer[len(full_text):]
                if diff:
                    full_text += diff
                    await msg.stream_token(diff)

            # Extract parsed metadata if available
            if metadata_payload:
                conf_score = metadata_payload.get("confidence_score")
                conf_level = metadata_payload.get("confidence_level")
                suggestions = metadata_payload.get("suggestions")
                token_balance = metadata_payload.get("token_balance")
                token_exh = metadata_payload.get("token_exhausted")
                if token_exh:
                    cl.user_session.set("token_exhausted", True)
            else:
                # Fallback to headers (for legacy compatibility)
                if response is not None:
                    conf_score = response.headers.get("X-Confidence-Score") or response.headers.get("x-confidence-score")
                    conf_level = response.headers.get("X-Confidence-Level") or response.headers.get("x-confidence-level")
                    suggestions_header = response.headers.get("X-Suggestions") or response.headers.get("x-suggestions")
                    if suggestions_header:
                        try:
                            suggestions = json.loads(suggestions_header)
                        except Exception:
                            suggestions = []
            
            # Apply confidence score formatting at the end of the text
            if conf_level == "high" and conf_score:
                full_text += f"\n\n✅ **Note:** This response has high confidence ({conf_score}%)."
            elif conf_level == "medium" and conf_score:
                full_text += f"\n\n⚠️ **Note:** This response has moderate confidence ({conf_score}%). Please verify important facts."
            elif conf_level == "low" and conf_score:
                full_text += f"\n\n❌ **Attention:** The model has low confidence ({conf_score}%) in this answer."

            msg.content = full_text
            await msg.update()
            
            fetched_history = False
            sid = response.headers.get("X-Session-Id") or response.headers.get("x-session-id")
            if sid:
                session_id = int(sid)
                cl.user_session.set("session_id", session_id)
                thread_id_map[thread_id] = session_id
                
            title = response.headers.get("X-Session-Title") or response.headers.get("x-session-title")
            if title:
                try:
                    await cl.context.emitter.emit("reload_chat_history", {})
                except Exception as e:
                    print(f"Error emitting reload_chat_history: {e}")
                
            if session_id:
                try:
                    h = requests.get(f"{BACKEND_URL}/session/{session_id}")
                    if h.status_code == 200:
                        msgs_history = h.json()
                        cl.user_session.set("messages", msgs_history)
                        fetched_history = True
                except Exception:
                    fetched_history = False
                    
            if not fetched_history:
                messages.append({"role": "assistant", "content": full_text})
                cl.user_session.set("messages", messages)
                
            if is_mic and not llm_error:
                import asyncio
                audio_bytes = await asyncio.to_thread(speak_text, full_text)
                if audio_bytes:
                    audio_element = cl.Audio(content=audio_bytes, name="TTS Response", mime="audio/mp3", display="inline", auto_play=True)
                    msg.elements = (msg.elements or []) + [audio_element]
                    await msg.update()
                    
            suggestions_list = []
            if suggestions is not None:
                suggestions_list = suggestions
            else:
                try:
                    header = response.headers.get("X-Suggestions") or response.headers.get("x-suggestions")
                    if header:
                        try:
                            suggestions_list = json.loads(header)
                        except Exception:
                            try:
                                suggestions_list = ast.literal_eval(header)
                            except Exception:
                                suggestions_list = []
                except Exception:
                    suggestions_list = []
                
            if cl.user_session.get("token_exhausted"):
                suggestions_list = []
            if not suggestions_list and not cl.user_session.get("token_exhausted"):
                suggestions_list = FALLBACK_SUGGESTIONS
                
            cl.user_session.set("suggestions", suggestions_list)
            
            # Show Low-Confidence HITL options OR suggestions
            if conf_level == "low" and not cl.user_session.get("token_exhausted"):
                hitl_actions = [
                    cl.Action(name="hitl_ask_human", label="🙋 Ask a Human", value=prompt, payload={"question": prompt}),
                    cl.Action(name="hitl_web_search", label="🔍 Search Web Instead", value=prompt, payload={"question": prompt}),
                    cl.Action(name="hitl_rephrase", label="✍️ Rephrase Question", value=prompt, payload={"question": prompt})
                ]
                await cl.Message(
                    content="*Low confidence detected. How would you like to proceed?*",
                    actions=hitl_actions
                ).send()
            elif suggestions_list and conf_level != "low":
                suggestion_actions = [
                    cl.Action(name="suggestion", label=sugg, value=sugg, payload={"value": sugg})
                    for sugg in suggestions_list
                ]
                await cl.Message(
                    content="*Suggested follow-ups:*",
                    actions=suggestion_actions
                ).send()
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        await cl.Message(content=f"❌ Error during response generation: {e}").send()