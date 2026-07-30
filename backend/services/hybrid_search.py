from typing import List, Any
import logging

logger = logging.getLogger(__name__)

try:
    from rank_bm25 import BM25Okapi
except Exception:
    BM25Okapi = None

from langchain_core.documents import Document
from pydantic import Field
from langchain_core.retrievers import BaseRetriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun


class HybridRetriever(BaseRetriever):
    """
    Hybrid retriever combining:
    1. FAISS semantic search
    2. BM25 keyword search
    """

    vector_store: Any = None
    bm25_index: Any = None
    docs: List[Document] = Field(default_factory=list)

    k_semantic: int = 5
    k_bm25: int = 5

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> List[Document]:

        logger.info("HybridRetriever query=%s", query)


        results = []
        seen_texts = set()

        # ----------------------------
        # Semantic Search (FAISS)
        # ----------------------------
        if self.vector_store is not None:
            try:
                if hasattr(self.vector_store, "as_retriever"):
                    retriever = self.vector_store.as_retriever(
                        search_kwargs={"k": self.k_semantic}
                    )
                else:
                    retriever = self.vector_store

                try:
                    if hasattr(retriever, "invoke"):
                        semantic_docs = retriever.invoke(query)
                    else:
                        semantic_docs = retriever.get_relevant_documents(query)
                except Exception:
                    semantic_docs = []

                logger.info(
                    "Semantic retrieval returned %s docs",
                    len(semantic_docs)
                )

                for doc in semantic_docs:
                    text = getattr(doc, "page_content", "")

                    if text and text not in seen_texts:
                        results.append(doc)
                        seen_texts.add(text)

            except Exception:
                logger.exception("Semantic retrieval failed")

        # ----------------------------
        # BM25 Search
        # ----------------------------
        if (
            BM25Okapi is not None
            and self.bm25_index is not None
            and self.docs
        ):
            try:
                # Use clean_tokenize for query split
                query_tokens = clean_tokenize(query)
                scores = self.bm25_index.get_scores(query_tokens)

                top_indices = sorted(
                    range(len(scores)),
                    key=lambda i: scores[i],
                    reverse=True
                )[: self.k_bm25]

                logger.info(
                    "BM25 retrieval returned %s docs",
                    len(top_indices)
                )

                for idx in top_indices:
                    doc = self.docs[idx]

                    text = getattr(doc, "page_content", "")

                    if text and text not in seen_texts:
                        results.append(doc)
                        seen_texts.add(text)

            except Exception:
                logger.exception("BM25 retrieval failed")

        logger.info(
            "HybridRetriever total returned %s docs",
            len(results)
        )

        for i, doc in enumerate(results[:10]):
            try:
                logger.info(
                    "DOC %s: %s",
                    i,
                    doc.page_content[:300]
                )
            except Exception:
                pass

        return results

    def _corpus_texts(self):
        return [
            getattr(doc, "page_content", "")
            for doc in self.docs
        ]


def clean_tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric words, ignoring punctuation."""
    import re
    if not text:
        return []
    return re.findall(r"\w+", text.lower())


def build_bm25_from_docs(docs: List[Document]):
    """
    Build BM25 index from document chunks.
    """

    if BM25Okapi is None:
        raise RuntimeError(
            "rank_bm25 is not installed. "
            "Install with: pip install rank_bm25"
        )

    corpus = [
        getattr(doc, "page_content", "")
        for doc in docs
    ]

    tokenized = [clean_tokenize(text) for text in corpus]

    return BM25Okapi(tokenized)