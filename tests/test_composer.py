from src.agents import composer
from src.agents.composer import DATA_LABEL, compose_answer, format_chunks, format_data, NOT_FOUND

QUESTION = "How long after signing can a draft rookie be traded?"

ROOKIE_CHUNK = {
    "citation": "Article VII, Section 8(d)",
    "pages": "261-261",
    "text": "No Draft Rookie may be traded before thirty (30) days following signing.",
}
DEFINITION_CHUNK = {
    "citation": "Article I, Section 1",
    "pages": "1-1",
    "text": "Definitions.",
}

PASSED_RESULT = {"chunks": [ROOKIE_CHUNK, DEFINITION_CHUNK], "passed": True}
ABSTAINED_RESULT = {"chunks": [], "passed": False}


# Fake Gemini so these tests are free and give the same result every run.

class FakeReply:
    def __init__(self, text):
        self.text = text


class FakeModel:
    def __init__(self, reply_text):
        self.reply_text = reply_text

    def invoke(self, prompt):
        return FakeReply(self.reply_text)


class BrokenModel:
    def invoke(self, prompt):
        raise TimeoutError("pretend Gemini timed out")


def use_fake_model(monkeypatch, model):
    monkeypatch.setattr(composer, "get_llm", lambda model_name: model)


def test_chunks_are_labeled_with_citation_and_pages():
    text = format_chunks([ROOKIE_CHUNK])

    assert text.startswith("[Article VII, Section 8(d)] (pages 261-261)\n")


def test_chunks_are_separated_by_a_blank_line():
    text = format_chunks([ROOKIE_CHUNK, DEFINITION_CHUNK])

    assert "\n\n[Article I, Section 1]" in text


def test_abstained_search_skips_gemini(monkeypatch):
    # If Gemini were called, the broken model would raise. It shouldn't be called.
    use_fake_model(monkeypatch, BrokenModel())

    result = compose_answer(QUESTION, ABSTAINED_RESULT)

    assert result["answer"] == NOT_FOUND
    assert result["abstained"] is True
    assert result["sources"] == []


def test_good_answer_is_returned_with_sources(monkeypatch):
    use_fake_model(monkeypatch, FakeModel("  30 days [Article VII, Section 8(d)].  "))

    result = compose_answer(QUESTION, PASSED_RESULT)

    assert result["answer"] == "30 days [Article VII, Section 8(d)]."
    assert result["abstained"] is False
    assert result["sources"] == ["Article VII, Section 8(d)", "Article I, Section 1"]


def test_model_saying_not_found_counts_as_abstained(monkeypatch):
    use_fake_model(monkeypatch, FakeModel(NOT_FOUND))

    result = compose_answer(QUESTION, PASSED_RESULT)

    assert result["abstained"] is True


def test_gemini_error_fails_closed(monkeypatch):
    use_fake_model(monkeypatch, BrokenModel())

    result = compose_answer(QUESTION, PASSED_RESULT)

    assert result["answer"] == NOT_FOUND
    assert result["abstained"] is True
    assert result["sources"] == []


# Numbers from the data agent.

NO_TRADE_DATA = {
    "team": "TOR",
    "payroll": 201188888,
    "status": {"payroll": 201188888, "tier": "over_tax", "next_line": "first_apron", "room": 7826112},
    "trade_sides": None,
    "trade_passed": None,
    "error": None,
}
TORONTO_SIDE = {
    "team": "TOR",
    "payroll_before": 201188888,
    "payroll_after": 209688888,
    "tier_after": "over_first_apron",
    "outgoing_players": ["Jakob Poeltl"],
    "incoming_players": ["Jarrett Allen"],
    "outgoing_total": 19500000,
    "incoming_total": 28000000,
    "max_incoming": 19500000,
    "passed": False,
    "rule": "Article VII, Section 6(j)(3)",
}
CLEVELAND_SIDE = {
    "team": "CLE",
    "payroll_before": 208969955,
    "payroll_after": 200469955,
    "tier_after": "over_tax",
    "outgoing_players": ["Jarrett Allen"],
    "incoming_players": ["Jakob Poeltl"],
    "outgoing_total": 28000000,
    "incoming_total": 19500000,
    "max_incoming": 37095709,
    "passed": True,
    "rule": "Article VII, Section 6(j)(1)(iv)",
}
TRADE_DATA = dict(NO_TRADE_DATA, trade_sides=[TORONTO_SIDE, CLEVELAND_SIDE], trade_passed=False)
ERROR_DATA = dict(NO_TRADE_DATA, payroll=None, status=None, error="Unknown team: Raptors")


class RecordingModel(FakeModel):
    # Keeps the prompt so a test can read what the model was sent.
    def invoke(self, prompt):
        self.prompt = prompt
        return FakeReply(self.reply_text)


def test_format_data_without_a_trade_shows_the_team_numbers():
    text = format_data(NO_TRADE_DATA)

    assert text.startswith("[Contracts data]")
    assert "$201,188,888" in text
    assert "over_tax" in text


def test_format_data_with_a_trade_has_one_line_per_team():
    lines = format_data(TRADE_DATA).split("\n")

    assert lines[1] == "Trade passes: False"
    assert lines[2].startswith("TOR:")
    assert lines[3].startswith("CLE:")
    assert "$19,500,000" in lines[2]
    assert "Article VII, Section 6(j)(3)" in lines[2]


def test_format_data_names_the_players_in_the_trade():
    # Without names the model can't connect the numbers to the question, and abstains.
    lines = format_data(TRADE_DATA).split("\n")

    assert "sends Jakob Poeltl ($19,500,000)" in lines[2]
    assert "takes Jarrett Allen ($28,000,000)" in lines[2]


def test_numbers_are_sent_to_the_model(monkeypatch):
    model = RecordingModel("Toronto fails.")
    use_fake_model(monkeypatch, model)

    compose_answer("trade?", None, TRADE_DATA)

    assert "Team numbers:" in model.prompt
    assert "$209,688,888" in model.prompt


def test_rules_only_prompt_has_no_team_numbers(monkeypatch):
    model = RecordingModel("Thirty days.")
    use_fake_model(monkeypatch, model)

    compose_answer(QUESTION, PASSED_RESULT)

    assert "Team numbers:" not in model.prompt


def test_weak_search_does_not_throw_away_good_numbers(monkeypatch):
    use_fake_model(monkeypatch, FakeModel("Toronto fails."))

    result = compose_answer("trade?", ABSTAINED_RESULT, TRADE_DATA)

    assert result["abstained"] is False
    assert result["answer"] == "Toronto fails."


def test_sources_include_the_data_label_and_trade_rules(monkeypatch):
    use_fake_model(monkeypatch, FakeModel("Toronto fails."))

    result = compose_answer("trade?", PASSED_RESULT, TRADE_DATA)

    assert result["sources"] == [
        "Article VII, Section 8(d)",
        "Article I, Section 1",
        DATA_LABEL,
        "Article VII, Section 6(j)(3)",
        "Article VII, Section 6(j)(1)(iv)",
    ]


def test_data_error_with_no_rules_abstains_without_calling_gemini(monkeypatch):
    use_fake_model(monkeypatch, BrokenModel())

    result = compose_answer("payroll?", None, ERROR_DATA)

    assert result["abstained"] is True
    assert result["sources"] == []


def test_no_inputs_abstains_without_calling_gemini(monkeypatch):
    use_fake_model(monkeypatch, BrokenModel())

    assert compose_answer("anything")["abstained"] is True


def test_gemini_failure_with_numbers_fails_closed(monkeypatch):
    use_fake_model(monkeypatch, BrokenModel())

    result = compose_answer("trade?", None, TRADE_DATA)

    assert result["abstained"] is True
    assert result["sources"] == []


def test_evidence_is_exactly_what_the_model_was_given(monkeypatch):
    model = RecordingModel("Toronto fails.")
    use_fake_model(monkeypatch, model)

    result = compose_answer("trade?", PASSED_RESULT, TRADE_DATA)

    assert "$209,688,888" in result["evidence"]
    assert "No Draft Rookie may be traded" in result["evidence"]
    assert result["evidence"] in model.prompt


def test_abstaining_without_calling_the_model_has_no_evidence():
    assert compose_answer("anything")["evidence"] == ""


def test_gemini_failure_has_no_evidence(monkeypatch):
    use_fake_model(monkeypatch, BrokenModel())

    assert compose_answer("trade?", None, TRADE_DATA)["evidence"] == ""
