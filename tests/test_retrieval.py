from src.tools.retrieval import search_cba

ROOKIE_QUESTION = "How long after signing can a draft rookie be traded?"
PIZZA_QUESTION = "What is the best pizza topping in Toronto?"


def test_rookie_question_finds_the_trade_rule():
    results = search_cba(ROOKIE_QUESTION)
    best_match = results[0]

    assert best_match["citation"] == "Article VII, Section 8(d)"


def test_core_filter_only_returns_core_chunks():
    results = search_cba(ROOKIE_QUESTION, tier="core")

    for result in results:
        assert result["tier"] == "core"


def test_maybe_filter_only_returns_maybe_chunks():
    results = search_cba(ROOKIE_QUESTION, tier="maybe")

    for result in results:
        assert result["tier"] == "maybe"


def test_top_k_controls_how_many_results_come_back():
    results = search_cba(ROOKIE_QUESTION, top_k=3)

    assert len(results) == 3


def test_best_match_comes_first():
    results = search_cba(ROOKIE_QUESTION, top_k=3)

    assert results[0]["score"] >= results[1]["score"]
    assert results[1]["score"] >= results[2]["score"]


def test_result_includes_page_numbers():
    results = search_cba(ROOKIE_QUESTION)
    best_match = results[0]

    assert best_match["pages"] == "261-261"


def test_real_question_scores_higher_than_off_topic_question():
    rookie_score = search_cba(ROOKIE_QUESTION)[0]["score"]
    pizza_score = search_cba(PIZZA_QUESTION)[0]["score"]

    assert rookie_score > pizza_score
