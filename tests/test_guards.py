from src.agents.composer import NOT_FOUND
from src.config import TIME_LIMIT_SECONDS
from src.graph import workflows
from src.graph.workflows import (
    after_verify_dynamic,
    build_dynamic_graph,
    build_static_graph,
    new_state,
    run_workflow,
)

DATA_QUESTION = "What is the Raptors payroll?"


def fake_agents(monkeypatch, passed):
    monkeypatch.setattr(workflows, "run_rules_agent", lambda q, k, t: {"passed": True, "chunks": []})
    monkeypatch.setattr(workflows, "run_data_agent", lambda team, trade: {"error": None})
    monkeypatch.setattr(
        workflows,
        "compose_answer",
        lambda q, r, d, f: {"answer": "a draft", "abstained": False, "sources": [], "evidence": ""},
    )
    monkeypatch.setattr(workflows, "verify_answer", lambda q, c: {"passed": passed, "reason": "test"})


def test_new_state_records_the_start_time():
    assert new_state("q")["started_at"] > 0


def test_out_of_time_abstains_instead_of_retrying():
    state = {"verdict": {"passed": False}, "revise_count": 0, "started_at": 0}

    assert after_verify_dynamic(state) == "abstain"


def test_time_left_still_retries(monkeypatch):
    monkeypatch.setattr(workflows.time, "time", lambda: 100)
    state = {"verdict": {"passed": False}, "revise_count": 0, "started_at": 100}

    assert after_verify_dynamic(state) == "revise"


def test_just_past_the_limit_abstains(monkeypatch):
    monkeypatch.setattr(workflows.time, "time", lambda: 100 + TIME_LIMIT_SECONDS + 1)
    state = {"verdict": {"passed": False}, "revise_count": 0, "started_at": 100}

    assert after_verify_dynamic(state) == "abstain"


def test_a_passing_answer_is_kept_even_when_out_of_time():
    state = {"verdict": {"passed": True}, "revise_count": 0, "started_at": 0}

    assert after_verify_dynamic(state) == "done"


def test_run_workflow_returns_a_normal_result(monkeypatch):
    fake_agents(monkeypatch, passed=True)

    result = run_workflow(build_dynamic_graph(), DATA_QUESTION)

    assert result["steps"] == ["route", "data", "compose", "verify"]
    assert result["composed"]["answer"] == "a draft"


def test_run_workflow_passes_the_settings_along(monkeypatch):
    calls = []
    fake_agents(monkeypatch, passed=True)
    monkeypatch.setattr(workflows, "run_rules_agent", lambda q, k, t: calls.append((k, t)) or {"passed": True, "chunks": []})

    run_workflow(build_static_graph(), DATA_QUESTION, top_k=8, tier="core")

    assert calls == [(8, "core")]


def test_step_cap_stops_the_run_and_abstains(monkeypatch):
    fake_agents(monkeypatch, passed=True)
    monkeypatch.setattr(workflows, "MAX_STEPS", 2)

    result = run_workflow(build_static_graph(), DATA_QUESTION)

    assert result["composed"]["answer"] == NOT_FOUND
    assert result["composed"]["abstained"] is True
    assert result["steps"] == ["abstain", "stopped: GraphRecursionError"]


def test_runaway_retries_hit_the_step_cap(monkeypatch):
    # Pretend the revise limit is broken, so a failing answer loops forever.
    fake_agents(monkeypatch, passed=False)
    monkeypatch.setattr(workflows, "MAX_REVISES", 1000)

    result = run_workflow(build_dynamic_graph(), DATA_QUESTION)

    assert result["composed"]["abstained"] is True
    assert result["steps"][-1] == "stopped: GraphRecursionError"


def test_a_crash_inside_an_agent_abstains_and_says_why(monkeypatch):
    def broken(team, trade):
        raise TypeError("pretend bug")

    fake_agents(monkeypatch, passed=True)
    monkeypatch.setattr(workflows, "run_data_agent", broken)

    result = run_workflow(build_dynamic_graph(), DATA_QUESTION)

    assert result["composed"]["abstained"] is True
    assert result["steps"][-1] == "stopped: TypeError"


def test_on_step_hears_every_step_in_order(monkeypatch):
    fake_agents(monkeypatch, passed=True)
    heard = []

    result = run_workflow(build_dynamic_graph(), DATA_QUESTION, on_step=heard.append)

    assert heard == ["route", "data", "compose", "verify"]
    assert heard == result["steps"]
