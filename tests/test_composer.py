from src.agents import composer
from src.agents.composer import compose_answer, format_chunks, NOT_FOUND

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
