from fastapi import APIRouter
import backend.globals as g

router = APIRouter()


@router.get("/debug/indexed_docs")
def indexed_docs():
    """Return simple diagnostics about indexed documents and vectors."""
    try:
        global_count = len(g.global_docs) if getattr(g, "global_docs", None) is not None else 0
    except Exception:
        global_count = 0

    try:
        session_counts = {k: (len(v) if hasattr(v, "__len__") else None) for k, v in getattr(g, "session_docs", {}).items()}
    except Exception:
        session_counts = {}

    # Show first 5 metadata entries for quick inspection
    sample = []
    try:
        for d in (g.global_docs or [])[:5]:
            try:
                meta = getattr(d, "metadata", None) or (d.get("metadata") if isinstance(d, dict) else None)
                text = getattr(d, "page_content", None) or (d.get("page_content") if isinstance(d, dict) else None)
                sample.append({"meta": meta, "snippet": (text[:300] + "...") if text and len(text) > 300 else text})
            except Exception:
                sample.append({"meta": None, "snippet": None})
    except Exception:
        sample = []

    return {
        "global_count": global_count,
        "session_counts": session_counts,
        "sample": sample,
    }


@router.get("/debug/retrieve")
def debug_retrieve(session_id: int | None = None, q: str = ""):
    """Probe the retriever for a given session (or global) and query.
    Returns number of hits and top snippets so you can verify PDF content is retrievable.
    """
    try:
        vector = None
        if session_id is not None:
            vector = g.session_vectors.get(session_id)
        if vector is None:
            vector = getattr(g, "vector_db", None)

        if vector is None:
            return {"error": "no vector store available for this session or global"}

        try:
            from backend.services.hybrid_search import HybridRetriever
            bm25 = g.session_bm25.get(session_id) if session_id is not None else getattr(g, 'global_bm25', None)
            docs = g.session_docs.get(session_id) if session_id is not None else getattr(g, 'global_docs', None)
            retr = HybridRetriever(vector_store=vector, bm25_index=bm25, docs=docs)
        except Exception:
            try:
                retr = vector.as_retriever()
            except Exception as e:
                return {"error": f"failed to create retriever: {e}"}

        try:
            if hasattr(retr, 'get_relevant_documents'):
                hits = retr.get_relevant_documents(q or "test") or []
            elif hasattr(retr, 'retrieve'):
                hits = retr.retrieve(q or "test") or []
            else:
                # Try call as fallback
                hits = retr(q or "test") or []
        except Exception as e:
            return {"error": f"retrieval call failed: {e}"}

        sample = []
        for d in (hits or [])[:5]:
            try:
                meta = getattr(d, 'metadata', None) or (d.get('metadata') if isinstance(d, dict) else None)
                text = getattr(d, 'page_content', None) or (d.get('page_content') if isinstance(d, dict) else None)
                sample.append({"meta": meta, "snippet": (text[:500] + "...") if text and len(text) > 500 else text})
            except Exception:
                sample.append({"meta": None, "snippet": None})

        return {"hits": len(hits), "sample": sample}
    except Exception as e:
        return {"error": str(e)}
