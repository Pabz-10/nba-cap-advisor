import time

import chromadb
from sentence_transformers import SentenceTransformer

from src.config import CBA_PDF_PATH, COLLECTION_NAME, EMBEDDING_MODEL, VECTORSTORE_DIR
from src.ingest.chunk_cba import chunk_cba


def build_vectorstore() -> int:
    """Rebuild the collection from scratch. Rerun this whenever chunking changes."""
    chunks = chunk_cba(CBA_PDF_PATH)
    model = SentenceTransformer(EMBEDDING_MODEL)
    embeddings = model.encode([c["text"] for c in chunks], normalize_embeddings=True, show_progress_bar=True)

    client = chromadb.PersistentClient(path=str(VECTORSTORE_DIR))
    if COLLECTION_NAME in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION_NAME)
    collection = client.create_collection(COLLECTION_NAME, configuration={"hnsw": {"space": "cosine"}})
    collection.add(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
        embeddings=embeddings.tolist(),
    )
    return collection.count()


if __name__ == "__main__":
    started = time.perf_counter()
    count = build_vectorstore()
    print(f"Stored {count} chunks in {time.perf_counter() - started:.1f}s")
