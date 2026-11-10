from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CBA_PDF_PATH = ROOT / "data" / "raw" / "NBA_CBA.pdf"

CBA_VERSION = "2023"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MAX_CHUNK_TOKENS = 230  # MiniLM reads 256 tokens; leaves room for special tokens

VECTORSTORE_DIR = ROOT / "vectorstore"
COLLECTION_NAME = "cba_2023"

TOP_K = 5
SIMILARITY_THRESHOLD = 0.55  # starting guess, the eval sets the final number

REWRITE_MODEL = "models/gemini-3.5-flash-lite"
COMPOSER_MODEL = "models/gemini-3.8-flash"
VERIFIER_MODEL = "models/gemini-3.8-flash"
LLM_TIMEOUT_SECONDS = 30
LLM_MAX_ATTEMPTS = 3