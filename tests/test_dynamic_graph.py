from src.config import MAX_CLARIFY, MAX_REVISES
from src.graph import workflows
from src.graph.workflows import (
    after_route,
    after_rules,
    after_verify_dynamic,
    build_dynamic_graph,
    new_state,
)

TRADE_QUESTION = "Can we trade Jakob Poeltl for Dyson Daniels?"
DATA_QUESTION = "What is the Raptors payroll?"
RULES_QUESTION = "How long after signing can a draft rookie be traded?"
VAGUE_QUESTION = "can we trade him?"


def fake_agents(monkeypatch, verdicts):
    # Fake the slow and paid parts. verdicts is what the verifier says each time it's called.
    remaining = list(verdicts)
    monkeypatch.setattr(workflows, "run_rules_agent", lambda q, k, t: {"passed": True, "chunks": []})
    monkeypatch.setattr(workflows, "run_data_agent", lambda team, trade: {"error": None})
    monkeypatch.setattr(
        workflows,
        "compose_answer",
        lambda q, r, d: {"answer": "a draft", "abstained": False, "sources": [], "evidence": ""},
    )
    monkeypatch.setattr(workflows, "verify_answer", lambda q, c: {"passed": remaining.pop(0), "reason": "test"})


def run(question, clarify_count=0):
    return build_dynamic_graph().invoke(new_state(question, clarify_count=clarify_count))


# The small decision functions

def test_after_route_each_route():
    assert after_route({"route": "clarify", "clarify_count": 0}) == "clarify"
    assert after_route({"route": "data", "clarify_count": 0}) == "data"
    assert after_route({"route": "rules", "clarify_count": 0}) == "rules"
    assert after_route({"route": "both", "clarify_count": 0}) == "rules"


def test_after_route_stops_asking_at_the_limit():
    assert after_route({"route": "clarify", "clarify_count": MAX_CLARIFY}) == "abstain"


def test_after_rules_only_both_needs_numbers():
    assert after_rules({"route": "both"}) == "data"
    assert after_rules({"route": "rules"}) == "compose"


def test_after_verify_passed_is_done():
    assert after_verify_dynamic({"verdict": {"passed": True}, "revise_count": 0}) == "done"


def test_after_verify_first_failure_revises():
    assert after_verify_dynamic({"verdict": {"passed": False}, "revise_count": 0}) == "revise"


def test_after_verify_stops_revising_at_the_limit():
    assert after_verify_dynamic({"verdict": {"passed": False}, "revise_count": MAX_REVISES}) == "abstain"


# The paths through the graph

def test_rules_question_skips_the_data_agent(monkeypatch):
    fake_agents(monkeypatch, [True])

    assert run(RULES_QUESTION)["steps"] == ["route", "rules", "compose", "verify"]


def test_data_question_skips_the_cba_search(monkeypatch):
    fake_agents(monkeypatch, [True])

    assert run(DATA_QUESTION)["steps"] == ["route", "data", "compose", "verify"]


def test_trade_question_runs_both_agents(monkeypatch):
    fake_agents(monkeypatch, [True])

    assert run(TRADE_QUESTION)["steps"] == ["route", "rules", "data", "compose", "verify"]


def test_vague_question_asks_and_stops(monkeypatch):
    fake_agents(monkeypatch, [])

    result = run(VAGUE_QUESTION)

    assert result["steps"] == ["route", "clarify"]
    assert result["clarify_question"] == "Which player or trade do you mean?"
    assert result["clarify_count"] == 1
    assert result["composed"] is None


def test_third_clarify_abstains_instead_of_asking(monkeypatch):
    fake_agents(monkeypatch, [])

    result = run(VAGUE_QUESTION, clarify_count=MAX_CLARIFY)

    assert result["steps"] == ["route", "abstain"]
    assert result["composed"]["abstained"] is True


def test_failed_answer_that_passes_on_retry(monkeypatch):
    fake_agents(monkeypatch, [False, True])

    result = run(DATA_QUESTION)

    assert result["steps"] == ["route", "data", "compose", "verify", "revise", "compose", "verify"]
    assert result["composed"]["abstained"] is False


def test_failing_twice_abstains_and_the_draft_is_gone(monkeypatch):
    fake_agents(monkeypatch, [False, False])

    result = run(DATA_QUESTION)

    assert result["steps"] == ["route", "data", "compose", "verify", "revise", "compose", "verify", "abstain"]
    assert result["composed"]["abstained"] is True
    assert result["composed"]["answer"] != "a draft"
