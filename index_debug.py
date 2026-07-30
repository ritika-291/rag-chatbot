import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.services.pdf_processor import process_document
import backend.globals as g


def main():
    if len(sys.argv) < 2:
        print("Usage: python index_debug.py <path-to-pdf>")
        return
    path = sys.argv[1]
    print("Indexing:", path)
    try:
        vec = process_document(path)
        print("process_document returned:", type(vec))
    except Exception as e:
        print("process_document raised:", repr(e))

    try:
        docs = getattr(g, "global_docs", None)
        print("g.global_docs type:", type(docs), "len:", len(docs) if docs is not None else None)
        if docs:
            for i, d in enumerate(docs[:5]):
                meta = getattr(d, "metadata", None) or (d.get("metadata") if isinstance(d, dict) else None)
                text = getattr(d, "page_content", None) or (d.get("page_content") if isinstance(d, dict) else None)
                print(f"DOC {i}: meta={meta} snippet={repr((text or '')[:200])}")
    except Exception as e:
        print("Reading g.global_docs failed:", repr(e))


if __name__ == "__main__":
    main()
