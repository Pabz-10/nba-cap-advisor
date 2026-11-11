from src.graph import workflows
from src.graph.workflows import after_verify_static, build_static_graph, new_state


def fake_agents(monkeypatch, passed):
    # Fake the slow and paid parts so the test only checks the path through the graph.
    monkeypatch.setattr(workflows, "run_rules_agent", lambda q, k, t: {"passed": True, "chunks": []})
    monkeypatch.setattr(workflows, "run_data_agent", lambda team, trade: {"error": None})
    monkeypatch.setattr(
        workflows,
        "compose_answer",
        lambda q, r, d, f: {"answer": "a draft", "abstained": False, "sources": [], "evidence": ""},
    )
    monkeypatch.setattr(workflows, "verify_answer", lambda q, c: {"passed": passed, "reason": "test"})


def test_passed_verdict_goes_to_done():
    assert after_verify_static({"verdict": {"passed": True}}) == "done"


def test_failed_verdict_goes_to_abstain():
    assert after_verify_static({"verdict": {"passed": False}}) == "abstain"


def test_passing_answer_takes_the_straight_line(monkeypatch):
    fake_agents(monkeypatch, passed=True)

    result = build_static_graph().invoke(new_state("What is the Raptors payroll?"))

    assert result["steps"] == ["route", "rules", "data", "compose", "verify"]
    assert result["composed"]["answer"] == "a draft"


def test_failing_answer_abstains_and_the_draft_is_gone(monkeypatch):
    fake_agents(monkeypatch, passed=False)

    result = build_static_graph().invoke(new_state("What is the Raptors payroll?"))

    assert result["steps"] == ["route", "rules", "data", "compose", "verify", "abstain"]
    assert result["composed"]["abstained"] is True
    assert result["composed"]["answer"] != "a draft"


def test_static_takes_the_same_path_for_a_rules_question(monkeypatch):
    fake_agents(monkeypatch, passed=True)

    result = build_static_graph().invoke(new_state("How long until a rookie can be traded?"))

    assert result["steps"] == ["route", "rules", "data", "compose", "verify"]
