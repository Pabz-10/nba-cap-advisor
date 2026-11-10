from functools import lru_cache

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import LLM_MAX_ATTEMPTS, LLM_TIMEOUT_SECONDS, ROOT


@lru_cache
def get_llm(model: str):
    # # sets up a Gemini model with our timeout and retry settings, once per model name
    load_dotenv(ROOT / ".env")
    llm = ChatGoogleGenerativeAI(model=model, timeout=LLM_TIMEOUT_SECONDS, max_retries=LLM_MAX_ATTEMPTS)
    return llm
