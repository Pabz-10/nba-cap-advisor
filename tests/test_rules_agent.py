from src.agents.rules_agent import search_and_check

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

    assert len(result["chunks"]) == 5
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
