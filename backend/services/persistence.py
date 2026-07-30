import os
import json
from langchain_community.vectorstores import FAISS
from backend.services.pdf_processor import get_embeddings
import backend.globals as g

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "sessions")

def get_session_dir(session_id):
    path = os.path.join(DATA_DIR, f"session_{session_id}")
    os.makedirs(path, exist_ok=True)
    return path

def save_session_data(session_id, vector_store, chunks):
    if session_id is None:
        return
    session_dir = get_session_dir(session_id)
    
    # Save FAISS index
    if vector_store is not None:
        try:
            vector_store.save_local(session_dir)
            print(f"[DEBUG] Saved FAISS index to disk for session {session_id}")
        except Exception as e:
            print(f"[ERROR] Failed to save FAISS index for session {session_id}: {e}")
        
    # Save chunks to JSON
    if chunks:
        chunks_file = os.path.join(session_dir, "chunks.json")
        serialized = []
        for doc in chunks:
            serialized.append({
                "page_content": getattr(doc, "page_content", ""),
                "metadata": getattr(doc, "metadata", {})
            })
        try:
            with open(chunks_file, "w", encoding="utf-8") as f:
                json.dump(serialized, f, ensure_ascii=False, indent=2)
            print(f"[DEBUG] Saved chunks to disk for session {session_id}: {len(chunks)} chunks")
        except Exception as e:
            print(f"[ERROR] Failed to save chunks for session {session_id}: {e}")

def load_session_data(session_id):
    if session_id is None:
        return None, None
        
    session_dir = os.path.join(DATA_DIR, f"session_{session_id}")
    if not os.path.exists(session_dir):
        return None, None
        
    # Load FAISS index
    vector_store = None
    index_file = os.path.join(session_dir, "index.faiss")
    if os.path.exists(index_file):
        try:
            embeddings = get_embeddings()
            vector_store = FAISS.load_local(session_dir, embeddings, allow_dangerous_deserialization=True)
            print(f"[DEBUG] Loaded FAISS index from disk for session {session_id}")
        except Exception as e:
            print(f"[ERROR] Failed to load FAISS index for session {session_id}: {e}")
            
    # Load chunks
    chunks = []
    chunks_file = os.path.join(session_dir, "chunks.json")
    if os.path.exists(chunks_file):
        try:
            from langchain.schema import Document
            with open(chunks_file, "r", encoding="utf-8") as f:
                serialized = json.load(f)
            for item in serialized:
                chunks.append(Document(
                    page_content=item.get("page_content", ""),
                    metadata=item.get("metadata", {})
                ))
            print(f"[DEBUG] Loaded chunks from disk for session {session_id}: {len(chunks)} chunks")
        except Exception as e:
            print(f"[ERROR] Failed to load chunks for session {session_id}: {e}")
            
    return vector_store, chunks

def ensure_session_loaded(session_id: int):
    if session_id is None:
        return
        
    if session_id not in g.session_vectors or g.session_vectors[session_id] is None:
        vector, chunks = load_session_data(session_id)
        if vector is not None:
            g.session_vectors[session_id] = vector
            g.session_docs[session_id] = chunks or []
            
            # Rebuild BM25 if needed
            try:
                from backend.services.hybrid_search import build_bm25_from_docs
                if chunks:
                    g.session_bm25[session_id] = build_bm25_from_docs(chunks)
                    print(f"[DEBUG] Rebuilt BM25 for session {session_id}")
            except Exception as e:
                print(f"[ERROR] Failed to build BM25 for session {session_id} after loading: {e}")
                
            print(f"[DEBUG] Loaded persisted session {session_id} from disk successfully.")
