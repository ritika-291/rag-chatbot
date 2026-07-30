from fastapi import APIRouter, UploadFile, File, HTTPException, Form
import tempfile
import os
import backend.globals as g
from backend.services.pdf_processor import process_document
import backend.services.history_services as hs

router = APIRouter()

@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...), session_id: int | None = Form(None)):
    file_path = None

    try:
        # 1. Validate allowed extensions
        filename = file.filename or "uploaded_file.pdf"
        ext = os.path.splitext(filename)[1].lower()
        allowed = {".pdf", ".docx", ".doc"}

        if ext not in allowed:
            raise HTTPException(status_code=400, detail="Only PDF and DOCX files allowed")

        content = await file.read()

        if not content:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        # 2. Save temp file with appropriate suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            temp_file.write(content)
            file_path = temp_file.name

        # 3. Process document → FAISS (append to existing session vector if present)
        existing = None
        if session_id is not None:
            from backend.services.persistence import ensure_session_loaded
            try:
                ensure_session_loaded(session_id)
            except Exception as e:
                print(f"[ERROR] failed to ensure session loaded on upload: {e}")
            existing = g.session_vectors.get(session_id)
        else:
            # If no session_id provided, create a new conversation/session
            try:
                session_id = hs.create_conversation("upload")
            except Exception:
                session_id = None

        # Process document and get both vector DB and the chunks
        result = process_document(file_path, existing_vector=existing, original_filename=filename, session_id=session_id)
        # process_document may return (vector, chunks) or just vector for legacy; handle both
        try:
            if isinstance(result, tuple) or isinstance(result, list):
                vector, chunks = result[0], result[1]
            else:
                vector = result
                chunks = getattr(g, "global_docs", []) or []
        except Exception:
            vector = result
            chunks = getattr(g, "global_docs", []) or []

        # Debug: report indexed chunk count when available
        try:
            count = len(chunks) if chunks is not None else None
            print(f"[DEBUG] Indexed document -> vector present: {vector is not None}, chunks created: {count}")
        except Exception:
            pass

        # Quick retrieval probe to validate the index (useful for debugging)
        probe = None
        vector_info = None
        try:
            if vector is not None:
                try:
                    idx = getattr(vector, 'index', None) or getattr(vector, '_index', None)
                    if idx is not None:
                        nt = getattr(idx, 'ntotal', None) or getattr(idx, 'n_total', None)
                        vector_info = {"ntotal": int(nt) if nt is not None else None}
                except Exception:
                    vector_info = None
                try:
                    retr = None
                    try:
                        from backend.services.hybrid_search import HybridRetriever
                        bm25 = g.session_bm25.get(session_id) if session_id is not None else getattr(g, 'global_bm25', None)
                        docs = g.session_docs.get(session_id) if session_id is not None else getattr(g, 'global_docs', None)
                        retr = HybridRetriever(vector_store=vector, bm25_index=bm25, docs=docs)
                    except Exception:
                        retr = vector.as_retriever()

                    # Different retriever implementations expose different APIs
                    hits = []
                    if hasattr(retr, 'invoke') and callable(getattr(retr, 'invoke')):
                        hits = retr.invoke("Python") or []
                    elif hasattr(retr, 'get_relevant_documents') and callable(getattr(retr, 'get_relevant_documents')):
                        hits = retr.get_relevant_documents("Python") or []
                    elif hasattr(retr, 'retrieve') and callable(getattr(retr, 'retrieve')):
                        hits = retr.retrieve("Python") or []
                    else:
                        # last resort: try calling as function
                        try:
                            hits = retr("Python") or []
                        except Exception:
                            hits = []

                    # If retriever returns no hits, try vectorstore direct similarity search
                    if not hits and hasattr(vector, 'similarity_search'):
                        try:
                            hits = vector.similarity_search("Python", k=4) or []
                        except Exception:
                            try:
                                hits = vector.similarity_search_with_score("Python", k=4) or []
                            except Exception:
                                hits = []

                    probe = {
                        "hits": len(hits),
                        "top_snippet": (hits[0].page_content[:300] if hits else None),
                    }
                except Exception as e:
                    probe = {"error": str(e)}
        except Exception:
            probe = None

        # Attach vector DB to a specific session if provided, otherwise set global
        if (vector is None) or (not chunks):
            # If indexing produced no vector or no chunks, surface a clear error
            detail = {
                "indexed_count": len(chunks) if chunks is not None else 0,
                "vector_present": bool(vector is not None),
                "probe": probe,
            }
            raise HTTPException(status_code=500, detail=f"Indexing failed or produced no chunks: {detail}")

        if session_id is not None:
            g.session_vectors[session_id] = vector
            # Keep accumulated chunks
            try:
                full_chunks = g.session_docs.get(session_id) or []
            except Exception:
                full_chunks = chunks or []

            # Save the updated session data (FAISS index and ALL chunks) to disk
            try:
                from backend.services.persistence import save_session_data
                save_session_data(session_id, vector, full_chunks)
            except Exception as e:
                print(f"[ERROR] Failed to save session data to disk: {e}")

            # Also set a global fallback so chat without session id can access recent uploads
            try:
                g.vector_db = vector
                g.global_docs = full_chunks
            except Exception:
                pass
        else:
            g.vector_db = vector
            try:
                g.global_docs = chunks or []
            except Exception:
                pass

        # Build BM25 index for hybrid search if rank_bm25 is installed
        try:
            from backend.services.hybrid_search import build_bm25_from_docs

            if session_id is not None:
                docs = g.session_docs.get(session_id) or []
                if docs:
                    g.session_bm25[session_id] = build_bm25_from_docs(docs)
            else:
                docs = g.global_docs or []
                if docs:
                    g.global_bm25 = build_bm25_from_docs(docs)
        except Exception:
            # BM25 is optional; installation not required
            pass

        # Prepare a small sample of metadata to return in the response for verification
        try:
            if session_id is not None:
                docs = g.session_docs.get(session_id) or []
            else:
                docs = g.global_docs or []
        except Exception:
            docs = g.global_docs or []

        sample = []
        try:
            for d in (docs or [])[:5]:
                try:
                    meta = getattr(d, "metadata", None) or (d.get("metadata") if isinstance(d, dict) else None)
                    text = getattr(d, "page_content", None) or (d.get("page_content") if isinstance(d, dict) else None)
                    sample.append({"meta": meta, "snippet": (text[:300] + "...") if text and len(text) > 300 else text})
                except Exception:
                    sample.append({"meta": None, "snippet": None})
        except Exception:
            sample = []

        return {
            "message": "Document indexed successfully",
            "filename": file.filename,
            "indexed_count": len(docs) if docs is not None else 0,
            "sample": sample,
            "session_id": session_id,
            "probe": probe,
            "vector_info": vector_info,
        }

    except HTTPException:
        raise
    except Exception as e:
        err_msg = str(e)
        if "No text extracted" in err_msg or "empty chunks" in err_msg or "empty" in err_msg.lower():
            raise HTTPException(
                status_code=400,
                detail="No text could be extracted from this PDF. Please ensure the document is not scanned or image-only."
            )
        raise HTTPException(status_code=500, detail=err_msg)

    finally:
        # 4. Safe cleanup
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
