from src.agents.composer import NOT_FOUND
from src.graph import workflows
from src.graph.workflows import (
    abstain_node,
    compose_node,
    data_node,
    new_state,
    route_node,
    rules_node,
    verify_node,
)


def test_new_state_starts_empty():
    state = new_state("a question", top_k=3, tier="core")

    assert state["question"] == "a question"
    assert state["top_k"] == 3
    assert state["tier"] == "core"
    assert state["rules_result"] is None
    assert state["revise_count"] == 0
    assert state["steps"] == []


def test_route_node_fills_in_the_route_and_trade():
    update = route_node(new_state("Can we trade Jakob Poeltl for Dyson Daniels?"))

    assert update["route"] == "both"
    assert update["team"] == "TOR"
    assert update["trade"] == {"TOR": ["poeltja01"], "ATL": ["daniedy01"]}
    assert update["steps"] == ["route"]


def test_rules_node_passes_the_settings_to_the_agent(monkeypatch):
    calls = []

    def fake_rules_agent(question, top_k, tier):
        calls.append((question, top_k, tier))
        return {"passed": True}

    monkeypatch.setattr(workflows, "run_rules_agent", fake_rules_agent)

    update = rules_node(new_state("q", top_k=8, tier="core"))

    assert calls == [("q", 8, "core")]
    assert update == {"rules_result": {"passed": True}, "steps": ["rules"]}


def test_data_node_with_no_team_skips_the_lookup():
    update = data_node(new_state("q"))

    assert update == {"data_result": None, "steps": ["data"]}


def test_data_node_looks_up_the_team():
    state = dict(new_state("q"), team="TOR")

    update = data_node(state)

    assert update["data_result"]["payroll"] == 201188888
    assert update["steps"] == ["data"]


def test_data_node_checks_the_trade():
    state = dict(new_state("q"), team="TOR", trade={"TOR": ["poeltja01"], "CLE": ["allenja01"]})

    assert data_node(state)["data_result"]["trade_passed"] is False


def test_compose_node_reads_the_results_from_state(monkeypatch):
    calls = []

    def fake_compose(question, rules_result, data_result, feedback):
        calls.append((question, rules_result, data_result, feedback))
        return {"answer": "hi"}

    monkeypatch.setattr(workflows, "compose_answer", fake_compose)
    state = dict(new_state("q"), rules_result="the rules", data_result="the data", steps=["route"])

    update = compose_node(state)

    assert calls == [("q", "the rules", "the data", None)]
    assert update == {"composed": {"answer": "hi"}, "steps": ["route", "compose"]}


def test_verify_node_saves_the_verdict_and_keeps_the_answer(monkeypatch):
    monkeypatch.setattr(workflows, "verify_answer", lambda question, composed: {"passed": True, "reason": "ok"})
    state = dict(new_state("q"), composed={"answer": "hi"})

    update = verify_node(state)

    assert update == {"verdict": {"passed": True, "reason": "ok"}, "steps": ["verify"]}


def test_abstain_node_replaces_the_answer():
    state = dict(new_state("q"), composed={"answer": "a bad draft"}, steps=["verify"])

    update = abstain_node(state)

    assert update["composed"] == {"answer": NOT_FOUND, "abstained": True, "sources": [], "evidence": ""}
    assert update["steps"] == ["verify", "abstain"]


def test_compose_node_passes_feedback_on_a_retry(monkeypatch):
    calls = []

    def fake_compose(question, rules_result, data_result, feedback):
        calls.append(feedback)
        return {"answer": "better"}

    monkeypatch.setattr(workflows, "compose_answer", fake_compose)
    state = dict(
        new_state("q"),
        revise_count=1,
        verdict={"passed": False, "reason": "number not in evidence"},
        composed={"answer": "Max is $19,500."},
    )

    compose_node(state)

    assert calls == ["number not in evidence. Your answer was: Max is $19,500."]
