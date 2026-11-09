import bisect
import re

import pymupdf
from transformers import AutoTokenizer

from src.config import CBA_VERSION, EMBEDDING_MODEL, MAX_CHUNK_TOKENS
from src.ingest.cba import FIRST_BODY_INDEX, load_pages

# (article, section or None for the whole article, tier)
SCOPE = [
    ("I", None, "core"),
    ("VII", 2, "core"), ("VII", 3, "core"), ("VII", 4, "core"), ("VII", 6, "core"), ("VII", 8, "core"),
    ("II", 6, "maybe"), ("II", 7, "maybe"), ("II", 9, "maybe"), ("II", 10, "maybe"), ("II", 11, "maybe"),
    ("VII", 5, "maybe"), ("VII", 7, "maybe"),
    ("VIII", None, "maybe"), ("IX", None, "maybe"), ("XI", None, "maybe"), ("XIII", None, "maybe"),
    ("XXIV", None, "maybe"),
    ("XXIX", 1, "maybe"), ("XXIX", 2, "maybe"), ("XXIX", 3, "maybe"), ("XXIX", 5, "maybe"),
    ("VI", 18, "maybe"),
    ("Exhibit B", None, "maybe"), ("Exhibit C", None, "maybe"),
]

MIN_LEAD_IN_TOKENS = 25  # shorter intros get merged into the next piece
OVERLAP_SENTENCES = 1
SEARCH_MARGIN = 80  # a heading can wrap across a page break


ROMAN = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv",
         "xvi", "xvii", "xviii", "xix", "xx", "xxi", "xxii", "xxiii", "xxiv", "xxv"]
FIRST_MARKERS = {"a", "1", "i", "A"}


def follows(previous: str, marker: str) -> bool:
    """True if marker is the next label after previous: (a)(b), (z)(aa), (1)(2), (i)(ii), (A)(B)."""
    if previous.isdigit() and marker.isdigit():
        return int(marker) == int(previous) + 1
    if previous in ROMAN and marker in ROMAN and ROMAN.index(marker) == ROMAN.index(previous) + 1:
        return True
    if previous.isalpha() and marker.isalpha() and len(set(previous)) == 1 and len(set(marker)) == 1:
        if previous[0] == "z" or previous[0] == "Z":
            return len(marker) == len(previous) + 1 and marker[0] in "aA"
        return len(marker) == len(previous) and ord(marker[0]) == ord(previous[0]) + 1
    return False


def nest_by_markers(children: list[dict]) -> list[dict]:
    """Work out each subsection's path from its labels.

    The PDF's bookmark levels are unreliable (Art VII s8(d) is nested under (c)),
    so nesting comes from the (a)/(1)/(i)/(A) sequence. Level only breaks the
    tie for (i), which can follow (h) or start a roman list.
    """
    stack, nested = [], []
    for child in children:
        markers = re.match(r"((?:\([^)]+\)\s*)+)", normalize(child["title"]))
        if not markers:  # unlabelled bookmark: leave it inside its parent's text
            continue
        labels = re.findall(r"\(([^)]+)\)", markers.group(1))

        first = labels[0]
        for depth in range(len(stack) - 1, -1, -1):
            previous, previous_level = stack[depth]
            if not follows(previous, first):
                continue
            if first == "i" and previous == "h" and child["level"] > previous_level:
                continue
            stack = stack[:depth]
            break
        stack += [(label, child["level"]) for label in labels]
        nested.append({"path": tuple(label for label, _ in stack), "position": child["position"]})
    return nested


def format_path(path: tuple) -> str:
    return "".join(f"({label})" for label in path)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class Document:
    """All body pages as one string, so sections can be cut mid-page."""

    def __init__(self, pages: list[dict]):
        self.page_labels = [p["printed_page"] for p in pages]
        self.starts = {}
        self.offsets = []
        parts, position = [], 0
        for page in pages:
            text = normalize(page["text"]) + " "
            self.starts[page["pdf_index"]] = position
            self.offsets.append(position)
            parts.append(text)
            position += len(text)
        self.text = "".join(parts)

    def label_at(self, position: int) -> str:
        return self.page_labels[bisect.bisect_right(self.offsets, position) - 1]

    def locate(self, title: str, pdf_index: int, search_from: int = 0) -> int:
        """Find where a bookmark's text starts. Fails loudly rather than mis-cutting."""
        start = max(self.starts[pdf_index], search_from)
        next_page = self.starts.get(pdf_index + 1, len(self.text))
        probe = normalize(title).rstrip(".")[:40]
        position = self.text.find(probe, start, next_page + SEARCH_MARGIN)
        if position < 0:
            raise ValueError(f"Bookmark not found on page {pdf_index}: {probe!r}")
        return position


def read_bookmarks(pdf_path) -> list[dict]:
    """Body bookmarks as dicts, each tagged with its article or exhibit."""
    with pymupdf.open(pdf_path) as doc:
        toc = doc.get_toc()
    bookmarks, article = [], None
    for level, title, page in toc:
        pdf_index = page - 1  # bookmark pages are 1-based
        if pdf_index < FIRST_BODY_INDEX:
            continue
        if level == 1:
            match = re.match(r"Article\s+([IVXL]+)\b|EXHIBIT\s+([A-Z](?:-\d)?)\b", title)
            article = None
            if match:
                article = match.group(1) or f"Exhibit {match.group(2)}"
        bookmarks.append({"level": level, "title": title, "pdf_index": pdf_index, "article": article})
    return bookmarks


def find_section_spans(document: Document, bookmarks: list[dict]) -> list[dict]:
    """Turn SCOPE into text spans, each with its nested subsection bookmarks."""
    spans = []
    for article, section, tier in SCOPE:
        top = next(i for i, b in enumerate(bookmarks) if b["article"] == article and b["level"] == 1)
        article_end = next((i for i in range(top + 1, len(bookmarks)) if bookmarks[i]["level"] == 1), None)
        article_stop = bookmarks[article_end]["pdf_index"] if article_end else None
        members = bookmarks[top + 1:article_end]
        sections = [b for b in members if b["level"] == 2]
        if section is not None:
            sections = [b for b in sections if b["title"].startswith(f"Section {section}.")]

        if not sections:  # article or exhibit with no sections
            start = document.starts[bookmarks[top]["pdf_index"]]
            end = document.starts[article_stop] if article_stop else len(document.text)
            spans.append({"article": article, "section": None, "title": "", "tier": tier,
                          "start": start, "end": end, "children": []})
            continue

        for bookmark in sections:
            index = bookmarks.index(bookmark)
            following = next((i for i in range(index + 1, len(bookmarks)) if bookmarks[i]["level"] <= 2), None)
            start = document.locate(bookmark["title"], bookmark["pdf_index"])
            end = _section_end(document, bookmarks, following, start)

            children, cursor = [], start
            stop = following if following is not None else len(bookmarks)
            for child in bookmarks[index + 1:stop]:
                cursor = document.locate(child["title"], child["pdf_index"], cursor)
                children.append({"level": child["level"], "title": child["title"], "position": cursor})

            number = re.match(r"Section (\d+)\.\s*(.*)", normalize(bookmark["title"]))
            spans.append({"article": article, "section": int(number.group(1)), "title": number.group(2),
                          "tier": tier, "start": start, "end": end, "children": nest_by_markers(children)})
    return spans


def _section_end(document: Document, bookmarks: list[dict], following, start: int) -> int:
    if following is None:
        return len(document.text)
    next_bookmark = bookmarks[following]
    if next_bookmark["level"] == 1:  # articles and exhibits begin on a fresh page
        return document.starts[next_bookmark["pdf_index"]]
    return document.locate(next_bookmark["title"], next_bookmark["pdf_index"], start + 1)


class Chunker:
    def __init__(self, document: Document):
        self.document = document
        self.tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL)
        self.chunks = []

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False, verbose=False))

    def split(self, span: dict, start: int, end: int, nodes: list[dict], path: tuple = ()):
        """Keep a piece whole if it fits, otherwise go one label deeper."""
        body = self.document.text[start:end].strip()
        if not body:
            return
        if self.count_tokens(self.header(span, path) + body) <= MAX_CHUNK_TOKENS:
            self.emit(span, start, body, path)
            return
        if not nodes:
            self.split_sentences(span, start, body, path)
            return

        groups = {}
        for node in nodes:
            groups.setdefault(node["path"][len(path)], []).append(node)
        direct = [(label, members[0]["position"], members) for label, members in groups.items()]

        lead_in = self.document.text[start:direct[0][1]].strip()
        merge_lead_in = self.count_tokens(lead_in) < MIN_LEAD_IN_TOKENS
        if lead_in and not merge_lead_in:
            self.split(span, start, direct[0][1], [], path)

        for i, (label, position, members) in enumerate(direct):
            child_start = start if i == 0 and merge_lead_in else position
            child_end = direct[i + 1][1] if i + 1 < len(direct) else end
            deeper = [m for m in members if len(m["path"]) > len(path) + 1]
            self.split(span, child_start, child_end, deeper, path + (label,))

    def split_sentences(self, span: dict, start: int, body: str, path: tuple):
        """Last resort for text with no smaller subsection: pack sentences, overlapping one."""
        limit = MAX_CHUNK_TOKENS - self.count_tokens(self.header(span, path))
        units = []
        for sentence in re.split(r"(?<=[.;:])\s+", body):
            units.extend(self.split_long_sentence(sentence, limit))

        current, part = [], 1
        for unit in units:
            if current and self.count_tokens(" ".join(current + [unit])) > limit:
                self.emit(span, self.document.text.find(current[0], start), " ".join(current), path, part)
                part += 1
                overlap = current[-OVERLAP_SENTENCES:]
                fits = self.count_tokens(" ".join(overlap + [unit])) <= limit
                current = overlap if fits else []
            current.append(unit)
        if current:
            position = self.document.text.find(current[0], start)
            self.emit(span, position, " ".join(current), path, part if part > 1 else None)

    def split_long_sentence(self, sentence: str, limit: int) -> list[str]:
        if self.count_tokens(sentence) <= limit:
            return [sentence]
        pieces, current = [], []
        for word in sentence.split():
            if current and self.count_tokens(" ".join(current + [word])) > limit:
                pieces.append(" ".join(current))
                current = []
            current.append(word)
        pieces.append(" ".join(current))
        return pieces

    @staticmethod
    def citation(span: dict, path: tuple) -> str:
        if span["article"].startswith("Exhibit"):
            return span["article"]
        if span["section"] is None:
            return f"Article {span['article']}"
        return f"Article {span['article']}, Section {span['section']}{format_path(path)}"

    def header(self, span: dict, path: tuple) -> str:
        title = f": {span['title']}" if span["title"] else ""
        return f"{self.citation(span, path)}{title}\n"

    def emit(self, span: dict, start: int, body: str, path: tuple, part: int | None = None):
        citation = self.citation(span, path)
        chunk_id = f"{citation}#{part}" if part else citation
        end = min(start + len(body), len(self.document.text) - 1)
        self.chunks.append({
            "id": chunk_id,
            "text": self.header(span, path) + body,
            "metadata": {
                "citation": citation,
                "article": span["article"],
                "section": span["section"] if span["section"] is not None else -1,
                "page_start": self.document.label_at(start),
                "page_end": self.document.label_at(end),
                "cba_version": CBA_VERSION,
                "tier": span["tier"],
            },
        })


def chunk_cba(pdf_path) -> list[dict]:
    document = Document(load_pages(pdf_path))
    chunker = Chunker(document)
    for span in find_section_spans(document, read_bookmarks(pdf_path)):
        chunker.split(span, span["start"], span["end"], span["children"])
    return chunker.chunks
