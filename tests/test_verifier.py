from src.agents import verifier
from src.agents.verifier import check_citations, check_numbers, check_with_model, find_dollars, verify_answer

EVIDENCE = "[Contracts data]\nTOR: sends Jakob Poeltl ($19,500,000), lands at $209,688,888, max incoming $19,500,000, passed: False"
SOURCES = ["Contracts data", "Article VII, Section 6(j)(3)"]
GOOD_ANSWER = "Toronto fails, landing at $209,688,888 [Contracts data] under [Article VII, Section 6(j)(3)]."


def composed(answer=GOOD_ANSWER, abstained=False):
    return {"answer": answer, "abstained": abstained, "sources": SOURCES, "evidence": EVIDENCE}


# Fake Gemini so these tests are free and give the same result every run.

class FakeReply:
    def __init__(self, text):
        self.text = text


class FakeModel:
    def __init__(self, reply_text):
        self.reply_text = reply_text
        self.calls = 0

    def invoke(self, prompt):
        self.calls = self.calls + 1
        self.prompt = prompt
        return FakeReply(self.reply_text)


class BrokenModel:
    def invoke(self, prompt):
        raise TimeoutError("pretend Gemini timed out")


def use_fake_model(monkeypatch, model):
    monkeypatch.setattr(verifier, "get_llm", lambda model_name: model)


# Citations

def test_real_citations_pass():
    assert check_citations(GOOD_ANSWER, SOURCES) is True


def test_made_up_citation_fails():
    assert check_citations("Toronto fails [Article 99, Section 1].", SOURCES) is False


def test_one_bad_citation_among_good_ones_fails():
    assert check_citations("Yes [Contracts data] and [Article 99].", SOURCES) is False


def test_no_citations_fails():
    assert check_citations("Toronto fails.", SOURCES) is False


# Numbers

def test_find_dollars_drops_the_trailing_comma():
    assert find_dollars("max $37,095,709, passed") == ["$37,095,709"]


def test_numbers_from_the_evidence_pass():
    assert check_numbers(GOOD_ANSWER, EVIDENCE) is True


def test_number_followed_by_a_comma_still_passes():
    assert check_numbers("It lands at $209,688,888, which is too high.", EVIDENCE) is True


def test_made_up_number_fails():
    assert check_numbers("Toronto lands at $1,000,000.", EVIDENCE) is False


def test_cut_off_number_fails():
    # The real mistake Gemini made: $19,500 instead of $19,500,000.
    assert check_numbers("Toronto can take back $19,500.", EVIDENCE) is False


def test_answer_with_no_dollars_passes():
    assert check_numbers("Thirty days after signing.", EVIDENCE) is True


# Model check

def test_model_says_supported(monkeypatch):
    use_fake_model(monkeypatch, FakeModel(" SUPPORTED \n"))

    assert check_with_model("q", GOOD_ANSWER, EVIDENCE) is True


def test_model_says_not_supported(monkeypatch):
    use_fake_model(monkeypatch, FakeModel("NOT_SUPPORTED"))

    assert check_with_model("q", GOOD_ANSWER, EVIDENCE) is False


def test_model_error_fails_closed(monkeypatch):
    use_fake_model(monkeypatch, BrokenModel())

    assert check_with_model("q", GOOD_ANSWER, EVIDENCE) is False


def test_model_is_shown_the_question_evidence_and_answer(monkeypatch):
    model = FakeModel("SUPPORTED")
    use_fake_model(monkeypatch, model)

    check_with_model("the question", GOOD_ANSWER, EVIDENCE)

    assert "the question" in model.prompt
    assert GOOD_ANSWER in model.prompt
    assert EVIDENCE in model.prompt


def test_model_is_told_team_codes_are_team_names(monkeypatch):
    # Without this it rejected "The Raptors payroll is..." because the evidence says TOR.
    model = FakeModel("SUPPORTED")
    use_fake_model(monkeypatch, model)

    check_with_model("q", GOOD_ANSWER, EVIDENCE)

    assert "standard NBA abbreviations" in model.prompt


# The whole verifier

def test_good_answer_passes(monkeypatch):
    use_fake_model(monkeypatch, FakeModel("SUPPORTED"))

    assert verify_answer("q", composed()) == {"passed": True, "reason": "ok"}


def test_abstain_passes_without_calling_the_model(monkeypatch):
    model = FakeModel("NOT_SUPPORTED")
    use_fake_model(monkeypatch, model)

    result = verify_answer("q", composed("I won't guess.", abstained=True))

    assert result == {"passed": True, "reason": "abstained"}
    assert model.calls == 0


def test_bad_citation_stops_before_the_paid_model_call(monkeypatch):
    model = FakeModel("SUPPORTED")
    use_fake_model(monkeypatch, model)

    result = verify_answer("q", composed("Toronto fails [Article 99]."))

    assert result == {"passed": False, "reason": "bad citation"}
    assert model.calls == 0


def test_bad_number_stops_before_the_paid_model_call(monkeypatch):
    model = FakeModel("SUPPORTED")
    use_fake_model(monkeypatch, model)

    result = verify_answer("q", composed("Max is $19,500 [Contracts data]."))

    assert result == {"passed": False, "reason": "number not in evidence"}
    assert model.calls == 0


def test_model_rejection_fails(monkeypatch):
    use_fake_model(monkeypatch, FakeModel("NOT_SUPPORTED"))

    assert verify_answer("q", composed()) == {"passed": False, "reason": "not supported"}
