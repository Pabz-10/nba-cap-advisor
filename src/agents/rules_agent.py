from src.config import SIMILARITY_THRESHOLD, TOP_K, REWRITE_MODEL
from src.tools.retrieval import search_cba 
from src.tools.llm import get_llm


def search_and_check(query: str, top_k: int = TOP_K, tier: str | None = None):
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

def rewrite_query(query):
    """Reword a question in the language of the CBA."""
    # write the prompt
    instructions = """Rewrite the question below using the wording of the NBA Collective Bargaining Agreement. Only use terms that match what the question is asking. Do not add new topics. Do not answer the question. Return only the rewritten question as plain text, with no other words or formatting.

Question: """
    prompt = instructions + query

    # send it to the model and return the rewritten question
    reply = get_llm(REWRITE_MODEL).invoke(prompt)
    return reply.text.strip()

def run_rules_agent(query: str, top_k: int = TOP_K, tier: str | None = None):
    """Find CBA chunks for a question. Retry once with a rewrite, abstain if still weak."""

    # 1. first search with the user's question
    first = search_and_check(query, top_k, tier)

    # 2. if it passed, we're done (no rewrite was needed)
    if first["passed"]:
        first["rewritten_query"] = None
        return first

    # 3. reword the question, and fail closed if Gemini errors or times out
    try:
        new_query = rewrite_query(query)
    except Exception:
        return {"chunks": [], "best_score": first["best_score"], "passed": False, "rewritten_query": None}

    # 4. search again with the reworded question
    second = search_and_check(new_query, top_k, tier)

    # 5. if it still fails, abstain: send no chunks onward
    if second["passed"] == False:
        second["chunks"] = []

    second["rewritten_query"] = new_query
    return second