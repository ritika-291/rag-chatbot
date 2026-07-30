import os
import logging
from dotenv import load_dotenv
import json
import ast
import backend.globals as g
from backend.services.web_search import search_web
import backend.services.history_services as hs
from backend.services.agent import get_answer_agent
from backend.services.hybrid_search import HybridRetriever

from langchain_openai import ChatOpenAI
from langchain_classic.chains import RetrievalQA
from langchain_core.prompts import ChatPromptTemplate

# Load environment
load_dotenv()

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def get_llm():
    """Return a configured ChatOpenAI instance."""
    model = os.getenv("LLM_MODEL_NAME")
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_URL")
    if not api_key:
        logger.warning("LLM API key not set (LLM_API_KEY)")
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0,
    )


#  NEW: Suggestion Generator
def generate_suggestions(question: str, answer: str):
    llm = get_llm()

    prompt = f"""
User asked: "{question}"

Assistant replied: "{answer}"

Suggest 3 short follow-up questions the user might ask next.
Keep them concise (max 8 words each).
Return ONLY a Python list.
"""

    try:
        response = llm.invoke(prompt)
        try:
            content = response.content
        except Exception:
            content = str(response)
        logger.debug("generate_suggestions: llm response len=%s", len(content) if content else 0)
        suggestions = []
        try:
            if isinstance(content, (bytes, bytearray)):
                content = content.decode("utf-8", errors="ignore")
            try:
                suggestions = json.loads(content)
            except Exception:
                try:
                    suggestions = ast.literal_eval(content)
                except Exception:
                    suggestions = []
        except Exception:
            suggestions = []

        if isinstance(suggestions, list) and len(suggestions) > 0:
            return suggestions[:3]
        else:
            return []
    except Exception:
        logger.exception("generate_suggestions: llm invocation failed")
        return []


def safe_log_message(convo_id: int, role: str, content: str, metadata: dict | None = None):
    """Log a message safely."""
    try:
        hs.append_message(convo_id, role, content, metadata=metadata)
    except Exception:
        logger.warning("Failed to save message", exc_info=True)


def get_answer(
    question: str,
    user_id: str = "default",
    convo_id: int | None = None,
    new_chat: bool = False
) -> dict:

    #  Conversation setup
    if new_chat:
        convo_id = hs.create_conversation(user_id)
    elif convo_id is None:
        convo_id = hs.get_or_create_conversation(user_id)



    llm = get_llm()
    # Always fetch recent messages for context and pass control to agent
    messages = hs.get_messages(convo_id)

    # Let the agent decide which tool(s) to use and synthesize a response
    agent_result = get_answer_agent(llm, question, convo_id, user_id=user_id, messages=messages)
    answer = agent_result.get("answer", "")
    source_type = agent_result.get("source", "chat")
    agent_sources = agent_result.get("sources") or []

    # ========= STRONG WEB FALLBACK =========

    def should_use_web(question: str, answer: str) -> bool:
        q = question.lower()
        a = (answer or "").lower()

        strong_web_queries = [
            "weather", "temperature", "latest", "news",
            "today", "now", "current", "score",
            "stock", "price", "live"
        ]

        if any(word in q for word in strong_web_queries):
            return True

        if (
            not answer
            or len(answer.strip()) < 40
            or "i don't know" in a
            or "not able" in a
            or "cannot" in a
            or "don't have access" in a
        ):
            return True

        return False

    # (web fallback and tool selection are now handled by the agent)



    #  GENERATE SUGGESTIONS (CORRECT PLACE)
    suggestions = generate_suggestions(question, answer)

    #  FALLBACK SUGGESTIONS
    if not suggestions:
        suggestions = [
            "Tell me more",
            "Give an example",
            "Explain simply"
        ]

    return {
        "answer": answer,
        "convo_id": convo_id,
        "suggestions": suggestions,
        "sources": agent_sources,
        "confidence_score": agent_result.get("confidence_score", 85)
    }


def retrieve_direct(question: str, convo_id: int | None = None) -> dict:
    """Direct RAG retrieval using session/global vectorstore. Bypasses the tool-selection agent.
    Returns a dict with at least the `answer` key (string).
    """
    llm = get_llm()

    # Prefer session-specific vector DB if available
    vector_store = None
    try:
        if convo_id is not None:
            vector_store = g.session_vectors.get(convo_id)
    except Exception:
        vector_store = None

    if vector_store is None:
        vector_store = getattr(g, "vector_db", None)

    if vector_store is None:
        logger.info("retrieve_direct: no vector store available for convo_id=%s", convo_id)
        return {"answer": "", "convo_id": convo_id}

    try:
        # prefer HybridRetriever when available
        try:
            bm25 = g.session_bm25.get(convo_id) if convo_id is not None else getattr(g, 'global_bm25', None)
            docs = g.session_docs.get(convo_id) if convo_id is not None else getattr(g, 'global_docs', None)
            retriever = HybridRetriever(vector_store=vector_store, bm25_index=bm25, docs=docs)
        except Exception:
            retriever = vector_store.as_retriever()
        # Probe retriever to see how many docs it returns for diagnostics
        try:
            # normalize query similarly to other codepaths
            q_norm = question.strip()
            if not q_norm.endswith("?"):
                q_norm = q_norm + "?"
            sem_results = []
            if hasattr(retriever, 'get_relevant_documents'):
                sem_results = retriever.get_relevant_documents(q_norm) or []
            elif hasattr(retriever, 'retrieve'):
                sem_results = retriever.retrieve(q_norm) or []
            logger.info("retrieve_direct: retriever returned %d documents for convo_id=%s", len(sem_results), convo_id)
            for i, d in enumerate(sem_results[:5]):
                try:
                    snippet = getattr(d, 'page_content', '')[:300]
                    meta = getattr(d, 'metadata', None) or (d.get('metadata') if isinstance(d, dict) else None)
                    logger.debug("retrieve_direct: doc %d meta=%s snippet=%s", i, meta, snippet)
                except Exception:
                    pass
        except Exception:
            logger.exception("retrieve_direct: probing retriever failed")

        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            retriever=retriever,
            return_source_documents=True,
        )

        result = qa_chain.invoke({"query": question})
        answer = result.get("result") or result.get("answer") or ""
        sources = result.get("source_documents", [])

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

        if unique_sources:
            sources_sentence = "Sources: " + ", ".join(unique_sources)
            answer_with_sources = f"{answer}\n\n{sources_sentence}"
        else:
            answer_with_sources = answer

        return {"answer": answer_with_sources, "convo_id": convo_id, "sources": sources}
    except Exception:
        return {"answer": "", "convo_id": convo_id}