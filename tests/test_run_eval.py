from eval.run_eval import check_answer, check_citation, check_retrieval, count_tokens, get_behavior, rate, summarize


def question(**changes):
    base = {
        "expected_behavior": "answer",
        "must_contain_any": ["thirty", "30"],
        "expected_trade_passed": None,
        "expected_citation": "Article VII, Section 8(d)",
    }
    return base | changes


def result(answer="Thirty days [Article VII, Section 8(d)].", abstained=False, trade_passed=None):
    return {
        "composed": {"answer": answer, "abstained": abstained, "sources": ["Article VII, Section 8(d)"]},
        "data_result": {"trade_passed": trade_passed},
        "rules_result": {"chunks": [{"citation": "Article VII, Section 8(d)(i)"}]},
    }


def test_behavior_is_clarify_when_there_is_no_answer():
    assert get_behavior({"composed": None}) == "clarify"


def test_behavior_is_abstain_or_answer():
    assert get_behavior(result(abstained=True)) == "abstain"
    assert get_behavior(result()) == "answer"


def test_right_answer_is_correct():
    assert check_answer(question(), result(), "answer") is True


def test_wrong_text_is_not_correct():
    assert check_answer(question(), result("Ninety days."), "answer") is False


def test_wrong_behavior_is_not_correct():
    assert check_answer(question(), result(abstained=True), "abstain") is False


def test_correct_abstain_needs_no_text():
    assert check_answer(question(expected_behavior="abstain"), result(abstained=True), "abstain") is True


def test_trade_result_has_to_match():
    trade = question(must_contain_any=["passes"], expected_trade_passed=True)

    assert check_answer(trade, result("It passes.", trade_passed=True), "answer") is True
    assert check_answer(trade, result("It passes.", trade_passed=False), "answer") is False


def test_a_subsection_counts_as_a_retrieval_hit():
    assert check_retrieval(question(), result()) is True


def test_missing_section_is_a_retrieval_miss():
    assert check_retrieval(question(expected_citation="Article I, Section 1"), result()) is False


def test_retrieval_does_not_apply_to_numbers_questions():
    assert check_retrieval(question(expected_citation="Contracts data"), result()) is None


def test_real_expected_citation_is_valid():
    assert check_citation(question(), result(), "answer") is True


def test_made_up_citation_is_not_valid():
    assert check_citation(question(), result("Thirty [Article 99]."), "answer") is False


def test_citation_does_not_apply_to_an_abstain():
    assert check_citation(question(), result(abstained=True), "abstain") is None


def test_tokens_add_up_across_models():
    usage = {"model-a": {"total_tokens": 10}, "model-b": {"total_tokens": 5}}

    assert count_tokens(usage) == 15


def test_rate_skips_questions_where_it_does_not_apply():
    assert rate([{"x": True}, {"x": False}, {"x": None}], "x") == "1/2"


def test_known_gaps_stay_out_of_the_headline():
    def row(correct, gap):
        return {
            "known_gap": gap, "correct": correct, "route_correct": True, "behavior_correct": True,
            "retrieval_hit": None, "citation_valid": None, "tokens": 1, "seconds": 1,
        }

    summary = summarize([row(True, False), row(False, True)])

    assert summary["correct"] == "1/1"
    assert summary["known_gaps_correct"] == "0/1"
