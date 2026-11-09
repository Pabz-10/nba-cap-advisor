import pymupdf

FIRST_BODY_INDEX = 24  # indexes 0-23 are the roman-numeral table of contents
HEADER_PREFIXES = ("Article", "Exhibit")


def split_header(lines: list[str]) -> tuple[str, list[str]]:
    """Return (printed_page, body_lines) from a page's non-blank lines."""
    first, second = lines[0], lines[1]
    printed_page = second if first.startswith(HEADER_PREFIXES) else first
    return printed_page, lines[2:]


def load_pages(pdf_path) -> list[dict]:
    """Return one dict per body page: pdf_index, printed_page, text."""
    pages = []
    with pymupdf.open(pdf_path) as doc:
        for pdf_index in range(FIRST_BODY_INDEX, len(doc)):
            raw_text = doc[pdf_index].get_text()
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            printed_page, body_lines = split_header(lines)
            pages.append({
                "pdf_index": pdf_index,
                "printed_page": printed_page,
                "text": "\n".join(body_lines),
            })
    return pages