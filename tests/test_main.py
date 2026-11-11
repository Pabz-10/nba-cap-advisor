from src import main as cli
from src.graph.workflows import build_dynamic_graph, build_static_graph


def answered():
    return {"composed": {"answer": "done"}, "clarify_question": None, "clarify_count": 0}


def asking(count):
    return {"composed": None, "clarify_question": "Which player?", "clarify_count": count}


def fake_run(monkeypatch, results):
    # Hands back each result in turn and records how it was called.
    calls = []
    remaining = list(results)

    def run(graph, question, top_k, tier, clarify_count, on_step=None):
        calls.append((question, clarify_count))
        return remaining.pop(0)

    monkeypatch.setattr(cli, "run_workflow", run)
    return calls


def test_a_direct_answer_never_asks_the_user(monkeypatch):
    calls = fake_run(monkeypatch, [answered()])

    def no_input(prompt):
        raise AssertionError("should not ask")

    monkeypatch.setattr("builtins.input", no_input)

    question, result = cli.run_with_clarifying("graph", "q", 5, None)

    assert question == "q"
    assert result["composed"]["answer"] == "done"
    assert calls == [("q", 0)]


def test_the_reply_is_added_to_the_question(monkeypatch):
    calls = fake_run(monkeypatch, [asking(1), answered()])
    monkeypatch.setattr("builtins.input", lambda prompt: "Jakob Poeltl")

    question, result = cli.run_with_clarifying("graph", "trade him?", 5, None)

    assert question == "trade him? Jakob Poeltl"
    assert calls == [("trade him?", 0), ("trade him? Jakob Poeltl", 1)]


def test_clarify_count_carries_between_runs(monkeypatch):
    calls = fake_run(monkeypatch, [asking(1), asking(2), answered()])
    monkeypatch.setattr("builtins.input", lambda prompt: "x")

    cli.run_with_clarifying("graph", "q", 5, None)

    assert [count for _, count in calls] == [0, 1, 2]


def test_mode_picks_the_workflow(monkeypatch):
    monkeypatch.setattr(cli, "build_static_graph", lambda: "static graph")
    monkeypatch.setattr(cli, "build_dynamic_graph", lambda: "dynamic graph")

    assert cli.build_graph("static") == "static graph"
    assert cli.build_graph("dynamic") == "dynamic graph"


def test_result_prints_when_search_and_verifier_were_skipped(capsys):
    result = {
        "route": "clarify",
        "steps": ["route", "abstain"],
        "rules_result": None,
        "verdict": None,
        "composed": {"answer": "I won't guess."},
    }

    cli.print_result(result)

    output = capsys.readouterr().out
    assert "Steps: route -> abstain" in output
    assert "Answer: I won't guess." in output
    assert "Verified" not in output


REWORDED_SEARCH = {"best_score": 0.6, "passed": True, "rewritten_query": "a reworded search"}


def test_rewrite_is_hidden_by_default(capsys):
    cli.print_search(REWORDED_SEARCH, show_rewrite=False)

    assert "Reworded" not in capsys.readouterr().out


def test_rewrite_is_shown_when_asked(capsys):
    cli.print_search(REWORDED_SEARCH, show_rewrite=True)

    assert "Reworded as: a reworded search" in capsys.readouterr().out


def test_each_step_prints_a_readable_label(capsys):
    cli.show_step("rules")

    assert capsys.readouterr().out == "  - Searched the CBA\n"
