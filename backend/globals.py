vector_db = None
# In-memory mapping of session_id -> vector DB (for per-session document indexes)
session_vectors = {}

# Keep last indexed documents and per-session document lists for keyword indexing
global_docs = []
session_docs = {}

# BM25 indexes (global or per-session). Objects created by `rank_bm25.BM25Okapi`.
global_bm25 = None
session_bm25 = {}

# Default token allocation per new chat session
DEFAULT_TOKENS = 10000