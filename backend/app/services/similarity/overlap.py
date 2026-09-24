"""Semantic overlap detection against the NUC 70% core (spec §9).

Core Reference documents are split into short segments (course titles, outlines,
sentences) and embedded. Each candidate's embedding is compared with every segment;
the maximum cosine similarity decides the overlap status and gives novelty:

    novelty = 1 - max_similarity
    overlap_status = "Potential Duplicate" if max_similarity >= threshold   (spec v2 §5)
"""
import re
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np

from ...models import OverlapStatus
from ..preprocessing.normalize import clean_blocks, split_blocks

MIN_SEGMENT_WORDS = 3     # keeps course titles such as "Cloud Computing Systems"
MAX_SEGMENT_WORDS = 60    # longer blocks are split into sentence windows
TOP_MATCHES = 3
_SENTENCE_END_RE = re.compile(r"(?<=[.!?;])\s+")
# A course code at the start of a table row, e.g. "CSC 301" or "COS 101".
_COURSE_CODE_RE = re.compile(r"\b[A-Z]{3,4} ?\d{3}[A-Z]?\b")
MIN_TABLE_ROWS = 3
# Trailing table columns after a course title: units, status (C/E/R), lecture/practical hours.
_ROW_TAIL_RE = re.compile(r"\s+\d{1,2}(?:\s+(?:\d{1,3}|[CER]|-))*\s*$")
_CACHE_SIZE = 32


@dataclass
class CoreSegment:
    text: str
    document_id: int


@dataclass
class CoreIndex:
    segments: list[CoreSegment]
    vectors: np.ndarray
    document_ids: list[int]

    def __len__(self):
        return len(self.segments)


@dataclass
class OverlapResult:
    max_similarity: float
    novelty: float
    status: OverlapStatus
    matches: list[dict]  # [{"text", "document_id", "similarity"}], best first


def _table_rows(block: str) -> list[str] | None:
    """Split a course-structure table flattened into one block ("Course Code Course Title
    Units ... CSC 101 Introduction to Computing 3 C 30 45 CSC 102 ...") into one
    "CSC 101 Introduction to Computing" segment per course. None if it is not a table."""
    starts = [m.start() for m in _COURSE_CODE_RE.finditer(block)]
    if len(starts) < MIN_TABLE_ROWS:
        return None
    rows = [block[a:b].strip() for a, b in zip(starts, starts[1:] + [len(block)])]
    # Table rows are short and end in their numeric columns (units, hours); prose that
    # merely mentions several course codes does neither.
    tabular = sum(len(r.split()) <= 15 and _ROW_TAIL_RE.search(r) is not None for r in rows)
    if tabular < max(MIN_TABLE_ROWS, 0.7 * len(rows)):
        return None
    return [_ROW_TAIL_RE.sub("", row) for row in rows]


def _windows(block: str) -> list[str]:
    """Sentence windows of at most MAX_SEGMENT_WORDS; unpunctuated runs are cut by words."""
    pieces = []
    for sentence in _SENTENCE_END_RE.split(block):
        words = sentence.split()
        pieces.extend(" ".join(words[i:i + MAX_SEGMENT_WORDS]) for i in range(0, len(words), MAX_SEGMENT_WORDS))
    windows, window = [], []
    for piece in pieces:
        if window and len(" ".join(window + [piece]).split()) > MAX_SEGMENT_WORDS:
            windows.append(" ".join(window))
            window = []
        window.append(piece)
    if window:
        windows.append(" ".join(window))
    return windows


def segment_core_text(text: str) -> list[str]:
    segments = []
    for block in clean_blocks(split_blocks(text)):
        words = block.split()
        if len(words) < MIN_SEGMENT_WORDS:
            continue
        rows = _table_rows(block)
        if rows is not None:
            segments.extend(rows)
        elif len(words) <= MAX_SEGMENT_WORDS:
            segments.append(block)
        else:
            segments.extend(_windows(block))
    # Preserve order, drop exact repeats (running headers that survived cleanup etc.).
    return list(dict.fromkeys(s for s in segments if len(s.split()) >= MIN_SEGMENT_WORDS))


# Core documents rarely change and can be large (the CCMAS runs to hundreds of pages),
# so their segment embeddings are cached per worker process.
_cache: "OrderedDict[tuple, tuple[list[str], np.ndarray]]" = OrderedDict()


def _embed_document(document_id, content_key, text, embedder):
    key = (document_id, content_key, embedder.backend, embedder.model_name)
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    segments = segment_core_text(text)
    vectors = embedder.encode(segments)
    _cache[key] = (segments, vectors)
    if len(_cache) > _CACHE_SIZE:
        _cache.popitem(last=False)
    return segments, vectors


def clear_cache():
    _cache.clear()


def build_core_index(documents, embedder) -> CoreIndex:
    """``documents``: iterable of (document_id, content_key, text); content_key is e.g. a SHA-256."""
    segments, vectors, doc_ids = [], [], []
    for document_id, content_key, text in documents:
        texts, vecs = _embed_document(document_id, content_key, text, embedder)
        if not texts:
            continue
        segments.extend(CoreSegment(t, document_id) for t in texts)
        vectors.append(vecs)
        doc_ids.append(document_id)
    matrix = np.vstack(vectors).astype(np.float32) if vectors else np.zeros((0, 1), dtype=np.float32)
    return CoreIndex(segments, matrix, doc_ids)


def detect_overlap(candidate_vectors: np.ndarray, index: CoreIndex, threshold: float) -> list[OverlapResult]:
    """Compare L2-normalised candidate vectors with the core index (dot product = cosine)."""
    if len(index) == 0:
        raise ValueError("The core reference index is empty")
    candidate_vectors = np.asarray(candidate_vectors, dtype=np.float32)
    if candidate_vectors.size == 0:
        return []
    similarities = np.clip(candidate_vectors @ index.vectors.T, -1.0, 1.0)
    results = []
    for row in similarities:
        best = np.argsort(-row, kind="stable")[:TOP_MATCHES]
        # Rounded before comparing so float32 noise (0.8000000119) cannot cross the
        # threshold, and the reported value always agrees with the status.
        max_similarity = round(max(float(row[best[0]]), 0.0), 4)  # negative cosine = unrelated
        results.append(OverlapResult(
            max_similarity=max_similarity,
            novelty=round(1.0 - max_similarity, 4),
            status=OverlapStatus.POTENTIAL_DUPLICATE if max_similarity >= threshold else OverlapStatus.NO_SIGNIFICANT_OVERLAP,
            matches=[
                {"text": index.segments[i].text, "document_id": index.segments[i].document_id,
                 "similarity": round(float(row[i]), 4)}
                for i in best
            ],
        ))
    return results
