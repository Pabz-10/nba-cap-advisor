import chromadb
import pytest
from sentence_transformers import SentenceTransformer

from src.config import COLLECTION_NAME, EMBEDDING_MODEL, VECTORSTORE_DIR


@pytest.fixture(scope="module")
def collection():
    client = chromadb.PersistentClient(path=str(VECTORSTORE_DIR))
    return client.get_collection(COLLECTION_NAME)


@pytest.fixture(scope="module")
def model():
    return SentenceTransformer(EMBEDDING_MODEL)


def test_all_chunks_stored(collection):
    assert collection.count() == 799


def test_uses_cosine(collection):
    assert collection.configuration["hnsw"]["space"] == "cosine"


def test_trade_question_finds_trade_rules(collection, model):
    question = "How long after signing can a draft rookie be traded?"
    embedding = model.encode([question], normalize_embeddings=True).tolist()
    results = collection.query(query_embeddings=embedding, n_results=5)
    assert any(i.startswith("Article VII, Section 8") for i in results["ids"][0])
