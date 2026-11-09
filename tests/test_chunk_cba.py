import pytest
from transformers import AutoTokenizer

from src.config import CBA_PDF_PATH, EMBEDDING_MODEL, MAX_CHUNK_TOKENS
from src.ingest.chunk_cba import chunk_cba, follows, nest_by_markers


@pytest.fixture(scope="module")
def chunks():
    return chunk_cba(CBA_PDF_PATH)


@pytest.fixture(scope="module")
def by_id(chunks):
    return {chunk["id"]: chunk for chunk in chunks}


def test_follows_label_sequences():
    assert follows("a", "b") and follows("z", "aa") and follows("1", "2")
    assert follows("i", "ii") and follows("iv", "v") and follows("A", "B")
    assert not follows("a", "c")


def test_nesting_ignores_wrong_bookmark_levels():
    children = [
        {"title": "(c) One", "level": 3, "position": 1},
        {"title": "(d)", "level": 4, "position": 2},  # bookmarked as if inside (c)
        {"title": "(ii) Two", "level": 4, "position": 3},
    ]
    assert [n["path"] for n in nest_by_markers(children)] == [("c",), ("d",), ("d", "ii")]


def test_every_chunk_fits_the_embedding_model(chunks):
    tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL)
    sizes = [len(tokenizer.encode(c["text"], add_special_tokens=False, verbose=False)) for c in chunks]
    assert max(sizes) <= MAX_CHUNK_TOKENS


def test_ids_are_unique(chunks):
    assert len({c["id"] for c in chunks}) == len(chunks)


def test_both_tiers_present(chunks):
    assert {c["metadata"]["tier"] for c in chunks} == {"core", "maybe"}


def test_trade_rule_citations_are_correct(by_id):
    assert "Article VII, Section 8(d)" in by_id
    assert "Article VII, Section 8(c)(d)" not in by_id
    assert by_id["Article VII, Section 8(d)"]["text"].splitlines()[1].startswith("(d)")


def test_section_cut_mid_page(chunks):
    # Section 2 ends partway down printed page 198, where Section 3 begins
    section_2 = [c for c in chunks if c["metadata"]["citation"].startswith("Article VII, Section 2")]
    section_3 = [c for c in chunks if c["metadata"]["citation"].startswith("Article VII, Section 3")]
    assert max(int(c["metadata"]["page_end"]) for c in section_2) == 198
    assert min(int(c["metadata"]["page_start"]) for c in section_3) == 198


def test_metadata_is_chroma_safe(chunks):
    for chunk in chunks:
        assert all(isinstance(v, (str, int)) for v in chunk["metadata"].values())
