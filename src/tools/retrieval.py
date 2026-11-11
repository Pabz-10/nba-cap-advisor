import logging
import os
from functools import lru_cache

# Quiet the startup noise from the embedding libraries. This has to run before they're imported.
# Offline mode loads MiniLM from the local cache, so search works without internet.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
for noisy_logger in ["torch.distributed.elastic.multiprocessing.redirects", "sentence_transformers", "huggingface_hub"]:
    logging.getLogger(noisy_logger).setLevel(logging.ERROR)

import chromadb
from sentence_transformers import SentenceTransformer

from src.config import COLLECTION_NAME, EMBEDDING_MODEL, VECTORSTORE_DIR, TOP_K


@lru_cache
def get_collection():

    # Opens the Chroma database and grabs your chunks. Cached, so it only opens once.
    client = chromadb.PersistentClient(path=str(VECTORSTORE_DIR))
    return client.get_collection(COLLECTION_NAME)

@lru_cache
def get_model():
    # Loads MiniLM. Cached, so it only loads once.
    return SentenceTransformer(EMBEDDING_MODEL)



def search_cba(query: str, top_k: int = TOP_K, tier: str | None = None):
    """Return the top_k closest chunks, best first."""

    # embed the query, the same way the chunks were embedded
    model = get_model()
    query_embeddings = model.encode([query], normalize_embeddings=True).tolist()

    # call collection.query(...), filtering on tier if one was given
    collection = get_collection()
    if tier:
        where = {"tier": tier}
    else:
        where = None

    res = collection.query(query_embeddings=query_embeddings, n_results=top_k, where=where)
    

    #  return a list of {"id", "text", "citation", "pages", "tier", "score"}
    res_list = []
    for chunk_id, text, meta, distance in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):
        res_list.append({
            "id" : chunk_id,
            "text" : text,
            "citation" : meta["citation"],
            "tier" : meta["tier"],
            "score" : 1 - distance,
            "pages": f"{meta['page_start']}-{meta['page_end']}",

        })
    return res_list