"""Text extraction for PDF, DOCX and TXT (spec §7.3).

Each parser returns a ParsedDocument whose ``blocks`` are paragraphs/table rows in
reading order. Repeating page furniture (running headers/footers, page numbers) is
removed here because only the parser knows where page boundaries are.
"""
import re
from collections import Counter
from dataclasses import dataclass, field

from ...models import FileType
from ..preprocessing.normalize import is_toc_line


class ParseError(Exception):
    """The file is in a supported format but its text could not be extracted."""


@dataclass
class ParsedDocument:
    blocks: list[str]
    page_count: int | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(self.blocks)

    @property
    def word_count(self) -> int:
        return sum(len(_WORD_RE.findall(b)) for b in self.blocks)


_WORD_RE = re.compile(r"\w+(?:['-]\w+)*")
_PAGE_NUMBER_RE = re.compile(r"^\s*(page\s*)?\d+(\s*(of|/)\s*\d+)?\s*$|^\s*[-\u2013\u2014]\s*\d+\s*[-\u2013\u2014]\s*$", re.I)


def _clean_block(text: str) -> str:
    # Tabs and newlines are kept: downstream cleanup uses them to spot TOC entries.
    return re.sub(r"[ \u00a0]+", " ", text).strip()


# --- TXT --------------------------------------------------------------------

def decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def parse_txt(data: bytes) -> ParsedDocument:
    text = decode_text(data).replace("\r\n", "\n").replace("\r", "\n")
    blocks = [_clean_block(b) for b in re.split(r"\n\s*\n", text)]
    return ParsedDocument(blocks=[b for b in blocks if b])


# --- DOCX -------------------------------------------------------------------

_TOC_STYLE_RE = re.compile(r"^toc\b|table of contents", re.I)


def parse_docx(data: bytes) -> ParsedDocument:
    import io

    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:  # python-docx raises a variety of zip/xml errors
        raise ParseError(f"Could not open DOCX: {exc}") from exc

    blocks: list[str] = []
    # Body content in document order; headers/footers are deliberately skipped
    # because they repeat on every page.
    for item in document.iter_inner_content():
        if isinstance(item, Paragraph):
            style = item.style.name if item.style is not None else ""
            if _TOC_STYLE_RE.search(style or ""):
                continue
            text = _clean_block(item.text)
            if text:
                blocks.append(text)
        elif isinstance(item, Table):
            blocks.extend(_table_rows(item))
    return ParsedDocument(blocks=blocks)


def _table_rows(table) -> list[str]:
    rows = []
    for row in table.rows:
        cells, seen = [], set()
        for cell in row.cells:
            # Merged cells are returned once per grid column; keep each only once.
            if id(cell._tc) in seen:
                continue
            seen.add(id(cell._tc))
            text = re.sub(r"\s+", " ", cell.text).strip()
            if text:
                cells.append(text)
        if cells:
            rows.append(" | ".join(cells))
    return rows


# --- PDF --------------------------------------------------------------------

_FURNITURE_LINES = 2  # lines at the top/bottom of each page checked for running headers/footers


def _normalise_furniture(line: str) -> str:
    # "Page 3 of 10" and "Page 4 of 10" should count as the same running footer.
    return re.sub(r"\d+", "#", line.strip().lower())


def parse_pdf(data: bytes) -> ParsedDocument:
    import pymupdf as fitz

    try:
        pdf = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ParseError(f"Could not open PDF: {exc}") from exc

    with pdf:
        if pdf.needs_pass:
            raise ParseError("PDF is password-protected")
        pages = []
        for page in pdf:
            lines = [ln.strip() for ln in page.get_text("text", sort=True).splitlines()]
            pages.append(lines)
        page_count = len(pages)

    # Running headers/footers: edge lines that recur on at least half the pages.
    edge_counts = Counter()
    for lines in pages:
        non_empty = [ln for ln in lines if ln]
        edges = non_empty[:_FURNITURE_LINES] + non_empty[-_FURNITURE_LINES:]
        edge_counts.update({_normalise_furniture(ln) for ln in edges})
    threshold = max(2, (page_count + 1) // 2)
    furniture = {key for key, n in edge_counts.items() if n >= threshold} if page_count >= 3 else set()

    blocks, current = [], []
    for lines in pages:
        for line in lines:
            if not line:
                if current:
                    blocks.append(_clean_block(" ".join(current)))
                    current = []
                continue
            if _PAGE_NUMBER_RE.match(line) or is_toc_line(line) or _normalise_furniture(line) in furniture:
                continue
            # Re-join words hyphenated across line breaks: "informa-" + "tion".
            if current and current[-1].endswith("-") and line[:1].islower():
                current[-1] = current[-1][:-1] + line
            else:
                current.append(line)
        if current:
            blocks.append(_clean_block(" ".join(current)))
            current = []

    parsed = ParsedDocument(blocks=[b for b in blocks if b], page_count=page_count)
    if parsed.word_count == 0:
        raise ParseError("No extractable text found; the PDF may be scanned images (OCR is not supported)")
    return parsed


# --- CSV --------------------------------------------------------------------

# Column names recognised in course lists (e.g. the NUC core curriculum, spec v2 §9).
_CODE_COLUMNS = ("course_code", "code", "course code", "course_id")
_TITLE_COLUMNS = ("course_title", "title", "course title", "course_name", "name")
_TEXT_COLUMNS = ("description", "course_description", "content", "outline", "course_content",
                 "synopsis", "learning_outcomes", "text", "body")


def _find_column(header, names):
    lookup = {h.strip().lower().replace("-", "_"): i for i, h in enumerate(header)}
    for name in names:
        if name.replace("-", "_") in lookup:
            return lookup[name.replace("-", "_")]
    return None


def parse_csv(data: bytes) -> ParsedDocument:
    """One block per row. Course lists become "CODE: Title. Description" so each course
    is its own segment for overlap detection; other CSVs keep all non-empty cells."""
    import csv
    import io

    text = decode_text(data)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if not rows:
        return ParsedDocument(blocks=[])

    header = rows[0]
    code_i, title_i = _find_column(header, _CODE_COLUMNS), _find_column(header, _TITLE_COLUMNS)
    text_cols = [i for i, h in enumerate(header) if h.strip().lower().replace("-", "_") in _TEXT_COLUMNS]
    has_header = code_i is not None or title_i is not None or bool(text_cols)
    body = rows[1:] if has_header else rows

    blocks = []
    for row in body:
        cell = lambda i: row[i].strip() if i is not None and i < len(row) else ""  # noqa: E731
        if has_header and (code_i is not None or title_i is not None):
            head = ": ".join(p for p in (cell(code_i), cell(title_i)) if p)
            details = " ".join(cell(i) for i in text_cols if cell(i))
            block = f"{head}. {details}" if head and details else head or details
        elif has_header:
            block = " ".join(cell(i) for i in text_cols if cell(i))
        else:
            block = " | ".join(c.strip() for c in row if c.strip())
        block = _clean_block(block)
        if block:
            blocks.append(block)
    return ParsedDocument(blocks=blocks)


PARSERS = {FileType.PDF: parse_pdf, FileType.DOCX: parse_docx, FileType.TXT: parse_txt, FileType.CSV: parse_csv}


def parse_document(data: bytes, file_type: FileType) -> ParsedDocument:
    parsed = PARSERS[file_type](data)
    if parsed.word_count == 0:
        raise ParseError("Document contains no text")
    return parsed
