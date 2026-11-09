import pytest

from src.config import CBA_PDF_PATH
from src.ingest.cba import HEADER_PREFIXES, load_pages, split_header


@pytest.fixture(scope="module")
def pages():
    return load_pages(CBA_PDF_PATH)


def test_split_header_handles_both_orders():
    assert split_header(["2", "Article I", "body"]) == ("2", ["body"])
    assert split_header(["Article I", "7", "body"]) == ("7", ["body"])
    assert split_header(["Exhibit A", "A-1", "body"]) == ("A-1", ["body"])


def test_page_count(pages):
    assert len(pages) == 652


def test_first_page(pages):
    assert pages[0]["pdf_index"] == 24
    assert pages[0]["printed_page"] == "1"


def test_section_2_page(pages):
    page = next(p for p in pages if p["printed_page"] == "169")
    assert page["pdf_index"] == 192
    assert "Section 2" in page["text"]


def test_no_leftover_headers(pages):
    assert not [p["printed_page"] for p in pages if p["text"].startswith(HEADER_PREFIXES)]