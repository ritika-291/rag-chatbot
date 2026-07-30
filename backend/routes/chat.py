# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Body, HTTPException
from typing import Optional
import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from langchain_openai import ChatOpenAI
# pyrefly: ignore [missing-import]
from langchain_classic.chains import RetrievalQA
# pyrefly: ignore [missing-import]
from fastapi.responses import StreamingResponse
import time
import logging
# pyrefly: ignore [missing-import]
import asyncio
import json
# pyrefly: ignore [missing-import]
import math

from backend.config import Settings

import backend.globals as g
from backend.database.chat_store import save_message, create_session, get_messages, get_token_balance, decrement_tokens, update_session_title
from backend.services.rag_chain import generate_suggestions, get_answer as rag_get_answer, retrieve_direct as rag_retrieve_direct
from backend.llm import get_llm

router = APIRouter()



logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# LLM function is provided by backend.llm.get_llm

def generate_chat_title(question: str) -> str:
    try:
        llm = get_llm()
        prompt = (
            "Based on the user's first message, create a short, descriptive chat title. "
            "Do NOT include quotation marks, formatting, or extra text. "
            "Return ONLY the title (maximum 6 words).\n\n"
            f"User's first message: {question}\n"
            "Title:"
        )
        resp = llm.invoke(prompt)
        title = resp.content.strip()
        # Clean up any quotes
        if title.startswith('"') and title.endswith('"'):
            title = title[1:-1].strip()
        if title.startswith("'") and title.endswith("'"):
            title = title[1:-1].strip()
        # limit to 6 words
        words = title.split()
        if len(words) > 6:
            title = " ".join(words[:6])
        return title
    except Exception as e:
        print(f"Error generating chat title: {e}")
        # fallback: first few words of the question
        words = question.split()
        if len(words) > 5:
            return " ".join(words[:5]) + "..."
        return question


# Chat endpoint

@router.post("/chat")
async def chat(
    question: str = Body(..., embed=True),
    session_id: Optional[int] = Body(None),
    user_id: str = Body("default"),
    new_chat: bool = Body(False)
):
 
    # 1. Ensure conversation
    if new_chat or session_id is None:
        session_id = create_session(title="New Chat")

    # Load persisted session vectors/chunks if any exist on disk
    from backend.services.persistence import ensure_session_loaded
    try:
        ensure_session_loaded(session_id)
    except Exception as e:
        print(f"[ERROR] failed to ensure session loaded: {e}")

    # Check if this is the first user message in the session to generate a title
    generated_title = None
    try:
        history = get_messages(session_id)
        if not history:
            generated_title = generate_chat_title(question)
            update_session_title(session_id, generated_title)
            print(f"[DEBUG] Generated title for session {session_id}: '{generated_title}'")
    except Exception as e:
        print(f"Error checking/updating session title: {e}")

    # Check token balance for session
    try:
        balance = get_token_balance(session_id)
    except Exception:
        balance = None

    if balance is not None and balance <= 0:
        raise HTTPException(
            status_code=403,
            detail="Token balance exhausted for this chat. Start a new conversation.",
            headers={"X-Token-Exhausted": "true"}
        )

   
    # 2. Save user question
    try:
        save_message(session_id, "user", question)
    except Exception as e:
        print(f"Warning: failed to save user message: {e}")

    llm = get_llm()

    # 3. Generate answer streaming
    llm = get_llm()
    
    try:
        from backend.services.agent import get_streaming_answer_agent, evaluate_response
        history = get_messages(session_id)
        token_stream, sources, source_type, context_for_synth = get_streaming_answer_agent(
            llm, question, session_id, user_id=user_id, messages=history
        )
    except Exception as e:
        logger.exception("Failed to initialize streaming agent")
        # Fail gracefully
        async def fallback_stream():
            yield "I encountered an error trying to process your request. Please try again."
        return StreamingResponse(fallback_stream(), media_type="text/plain", headers={"X-Session-Id": str(session_id)})

    async def generate_response_stream():
        full_answer_list = []
        try:
            for chunk in token_stream:
                try:
                    token = chunk.content
                except Exception:
                    token = str(chunk)
                
                if token:
                    full_answer_list.append(token)
                    yield token
        except Exception as e:
            logger.exception("Error during LLM token streaming")
            yield f"\n[Streaming Error: {e}]"
            
        full_answer = "".join(full_answer_list)
        
        # Background Evaluation
        try:
            eval_res = await asyncio.to_thread(
                evaluate_response, llm, question, context_for_synth, full_answer, source_type
            )
            confidence_score = eval_res.get("confidence_score", 85)
            confidence_level = "high" if confidence_score >= 80 else ("medium" if confidence_score >= 50 else "low")
        except Exception:
            logger.exception("Evaluation failed")
            eval_res = {}
            confidence_score = 85
            confidence_level = "high"
            
        # Build unique sources sentence
        unique_sources = []
        for doc in sources[:5]:
            meta = getattr(doc, 'metadata', None) or {}
            fname = meta.get("file_name") or meta.get("source_file") or meta.get("source")
            page = meta.get("page")
            if fname:
                import os
                fname_clean = os.path.basename(str(fname))
                src_str = fname_clean
                if page is not None:
                    src_str += f" (Page {page})"
                if src_str not in unique_sources:
                    unique_sources.append(src_str)
            else:
                content = getattr(doc, 'page_content', '')
                if content:
                    snippet = content[:30].strip()
                    src_str = f'"{snippet}..."'
                    if src_str not in unique_sources:
                        unique_sources.append(src_str)

        sources_sentence = ""
        if unique_sources:
            sources_sentence = "Sources: " + ", ".join(unique_sources)
            
        final_saved_answer = full_answer
        if sources_sentence and "Sources:" not in final_saved_answer:
            final_saved_answer = f"{final_saved_answer}\n\n{sources_sentence}"
            
        # Build sources details list for database saving
        sources_details = []
        for d in sources[:8]:
            meta = getattr(d, "metadata", None) or (d.get("metadata") if isinstance(d, dict) else None)
            content = getattr(d, "page_content", None) or (d.get("page_content") if isinstance(d, dict) else None)
            snippet = (content[:300] + "...") if content and len(content) > 300 else content
            src = None
            page = None
            if isinstance(meta, dict):
                src = meta.get("file_name") or meta.get("source_file") or meta.get("source")
                page = meta.get("page")
            entry = {"source": src, "page": page, "snippet": snippet}
            if isinstance(meta, dict) and meta.get("reference"):
                entry["reference"] = meta.get("reference")
            sources_details.append(entry)

        # Save message and decrement tokens
        try:
            meta_to_save = {"sources": sources_details if sources_details else unique_sources}
            save_message(session_id, "assistant", final_saved_answer, metadata=meta_to_save)
            
            try:
                settings = Settings()
                chars_per_token = int(getattr(settings, "TOKEN_CHAR_RATIO", 4)) or 4
            except Exception:
                chars_per_token = 4

            user_tokens = math.ceil(len(str(question)) / chars_per_token) if question else 0
            assistant_tokens = math.ceil(len(str(final_saved_answer)) / chars_per_token) if final_saved_answer else 0
            total_cost = int(user_tokens + assistant_tokens)
            
            new_balance = decrement_tokens(session_id, total_cost)
            token_exhausted = (new_balance is not None and int(new_balance) <= 0)
        except Exception as e:
            logger.warning("Failed to save assistant response or decrement tokens: %s", e)
            new_balance = None
            token_exhausted = False
            total_cost = 0

        # Generate suggestions
        try:
            if not token_exhausted:
                suggestions = await asyncio.to_thread(generate_suggestions, question, final_saved_answer)
            else:
                suggestions = []
        except Exception:
            suggestions = []
            
        if not token_exhausted and not suggestions:
            suggestions = ["Tell me more", "Give an example", "Explain simply"]

        metadata_payload = {
            "confidence_score": confidence_score,
            "confidence_level": confidence_level,
            "suggestions": suggestions,
            "token_balance": new_balance if new_balance is not None else 10000,
            "token_exhausted": token_exhausted
        }
        
        yield f"\n\n[METADATA]:{json.dumps(metadata_payload)}"

    resp_headers = {
        "X-Session-Id": str(session_id),
    }
    if generated_title:
        resp_headers["X-Session-Title"] = generated_title
        
    return StreamingResponse(
        generate_response_stream(),
        media_type="text/plain",
        headers=resp_headers,
    )