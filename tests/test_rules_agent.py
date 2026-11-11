from src.agents import rules_agent
from src.agents.rules_agent import search_and_check, run_rules_agent
from src.config import TOP_K

ROOKIE_QUESTION = "How long after signing can a draft rookie be traded?"
PIZZA_QUESTION = "What is the best pizza topping in Toronto?"
OLD_CAP_QUESTION = "What was the salary cap in 1995?"


def test_real_question_passes_the_threshold():
    result = search_and_check(ROOKIE_QUESTION)

    assert result["passed"] is True


def test_off_topic_question_fails_the_threshold():
    result = search_and_check(PIZZA_QUESTION)

    assert result["passed"] is False


def test_failed_search_still_returns_its_chunks_and_score():
    result = search_and_check(PIZZA_QUESTION)

    assert len(result["chunks"]) == TOP_K
    assert result["best_score"] < 0.55


def test_best_score_is_the_top_chunks_score():
    result = search_and_check(ROOKIE_QUESTION)
    top_chunk = result["chunks"][0]

    assert result["best_score"] == top_chunk["score"]


def test_top_k_and_tier_are_passed_through():
    result = search_and_check(ROOKIE_QUESTION, top_k=3, tier="core")

    assert len(result["chunks"]) == 3
    for chunk in result["chunks"]:
        assert chunk["tier"] == "core"


def test_threshold_cannot_catch_on_topic_unanswerable_questions():
    # Known limit: the CBA can't answer this, but it is on topic, so it passes.
    # The verifier has to catch these.
    result = search_and_check(OLD_CAP_QUESTION)

    assert result["passed"] is True


# Fake rewrites so these tests don't call Gemini (free, same result every run).

def fake_rewrite_that_breaks(query):
    raise TimeoutError("pretend Gemini timed out")


def fake_rewrite_to_rookie_question(query):
    return ROOKIE_QUESTION


def fake_rewrite_to_pizza_question(query):
    return PIZZA_QUESTION


def test_strong_question_skips_the_rewrite(monkeypatch):
    # If the rewrite ran, the fake would break it and the agent would abstain.
    monkeypatch.setattr(rules_agent, "rewrite_query", fake_rewrite_that_breaks)

    result = run_rules_agent(ROOKIE_QUESTION)

    assert result["passed"] is True
    assert result["rewritten_query"] is None


def test_weak_question_is_saved_by_a_good_rewrite(monkeypatch):
    monkeypatch.setattr(rules_agent, "rewrite_query", fake_rewrite_to_rookie_question)

    result = run_rules_agent(PIZZA_QUESTION)

    assert result["passed"] is True
    assert result["rewritten_query"] == ROOKIE_QUESTION
    assert len(result["chunks"]) == TOP_K


def test_rewrite_that_still_fails_abstains(monkeypatch):
    monkeypatch.setattr(rules_agent, "rewrite_query", fake_rewrite_to_pizza_question)

    result = run_rules_agent(PIZZA_QUESTION)

    assert result["passed"] is False
    assert result["chunks"] == []


def test_gemini_error_fails_closed(monkeypatch):
    monkeypatch.setattr(rules_agent, "rewrite_query", fake_rewrite_that_breaks)

    result = run_rules_agent(PIZZA_QUESTION)

    assert result["passed"] is False
    assert result["chunks"] == []
    assert result["rewritten_query"] is None
    assert result["best_score"] < 0.55


def test_retry_keeps_top_k_and_tier(monkeypatch):
    monkeypatch.setattr(rules_agent, "rewrite_query", fake_rewrite_to_rookie_question)

    result = run_rules_agent(PIZZA_QUESTION, top_k=3, tier="core")

    assert len(result["chunks"]) == 3
    for chunk in result["chunks"]:
        assert chunk["tier"] == "core"


def test_rewrite_is_given_the_question_text(monkeypatch):
    questions_sent = []

    def fake_rewrite_that_records(query):
        questions_sent.append(query)
        return ROOKIE_QUESTION

    monkeypatch.setattr(rules_agent, "rewrite_query", fake_rewrite_that_records)

    run_rules_agent(PIZZA_QUESTION)

    assert questions_sent == [PIZZA_QUESTION]
