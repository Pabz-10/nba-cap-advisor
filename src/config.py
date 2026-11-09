from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CBA_PDF_PATH = ROOT / "data" / "raw" / "NBA_CBA.pdf"

CBA_VERSION = "2023"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MAX_CHUNK_TOKENS = 230  # MiniLM reads 256 tokens; leaves room for special tokens