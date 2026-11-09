from src.config import SIMILARITY_THRESHOLD, TOP_K
from src.tools.retrieval import search_cba


def search_and_check(query: str, top_k: int = TOP_K, tier: str | None = None) -> dict:
    """Search the CBA and decide if the results are strong enough to use."""

    # call search_cba and store the results which will be the top k chunks
    res = search_cba(query=query, top_k=top_k, tier=tier)

    # get the best score (results are already sorted, best first)
    best_score = res[0]["score"]

    # passed is True if the best score meets the threshold
    passed = best_score >= SIMILARITY_THRESHOLD
    return {
            "chunks": res,
            "best_score" : best_score,
            "passed" : passed
        }
