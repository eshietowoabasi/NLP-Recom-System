"""Candidate building and recommendation scoring (spec v2 §6; docs/DECISIONS.md, D4).

    S_c = 0.40 * N_c + 0.35 * B_c + 0.25 * V_c      (weights configurable per session)

All three components are normalised to [0, 1] across the session's candidates:
- N_c (NER demand):  count(entities_c) / max(count(entities) across candidates), where
                     the count is SKILL/TECHNOLOGY/METHODOLOGY mentions in the topic's passages.
- B_c (BERTopic relevance): the topic's c-TF-IDF score / the maximum across candidates.
- V_c (novelty):     1 - max cosine similarity to the NUC 70% core (spec v2 §5).

Candidates are ranked by S_c (descending) and the top ``max_recommendations`` are kept.
"""
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from ...models import OverlapStatus

DOMINANT_SKILL_SHARE = 0.2   # a skill in >= 20% of a topic's passages can name it
EVIDENCE_SKILLS = 10


@dataclass
class Candidate:
    topic_id: int
    topic_label: str
    embedding: np.ndarray
    passage_count: int
    distinct_passages: int
    document_ids: list[int]
    source_category_counts: dict
    keywords: list[str]
    representative_passages: list[dict]
    entity_mentions: Counter          # (name, label) -> mentions in the topic's passages
    entity_passages: Counter          # (name, label) -> distinct passages mentioning it
    ctfidf_score: float = 0.0         # BERTopic c-TF-IDF strength of the topic
    # Filled in by scoring:
    title: str = ""
    description: str = ""
    ner_score: float = 0.0
    topic_score: float = 0.0
    novelty_score: float = 0.0
    max_similarity: float = 0.0
    composite_score: float = 0.0
    overlap_status: OverlapStatus = OverlapStatus.NO_SIGNIFICANT_OVERLAP
    core_matches: list = field(default_factory=list)


def candidate_title(candidate: Candidate) -> str:
    """Prefer a dominant skill's canonical name ("Cloud Computing") over the raw topic label."""
    threshold = max(1, DOMINANT_SKILL_SHARE * candidate.distinct_passages)
    ranked = sorted(
        ((name, label, n) for (name, label), n in candidate.entity_passages.items() if n >= threshold),
        key=lambda x: (x[1] != "SKILL", -x[2], x[0]),  # skills before technologies/methodologies
    )
    names = [name for name, _, _ in ranked[:2]]
    if not names:
        return candidate.topic_label
    return " and ".join(names)


def candidate_description(candidate: Candidate) -> str:
    sources = ", ".join(f"{cat} ({n})" for cat, n in sorted(candidate.source_category_counts.items(), key=lambda kv: -kv[1]))
    skills = [name for (name, _), _ in candidate.entity_mentions.most_common(5)]
    parts = [
        f"Theme found in {candidate.passage_count} passages across {len(candidate.document_ids)} "
        f"source document(s): {sources}.",
        f"Key terms: {', '.join(candidate.keywords[:6])}.",
    ]
    if skills:
        parts.append(f"Most demanded skills and tools: {', '.join(skills)}.")
    return " ".join(parts)


def ner_scores(mentions: list[int]) -> list[float]:
    """N_c = count / max count (spec v2 §6)."""
    top = max(mentions, default=0)
    if top <= 0:
        return [0.0 for _ in mentions]
    return [round(m / top, 4) for m in mentions]


def topic_scores(ctfidf_scores: list[float]) -> list[float]:
    """B_c = topic c-TF-IDF score / max across candidates (spec v2 §6)."""
    top = max(ctfidf_scores, default=0.0)
    if top <= 0:
        return [0.0 for _ in ctfidf_scores]
    return [round(v / top, 4) for v in ctfidf_scores]


def composite_score(ner: float, topic: float, novelty: float, config: dict) -> float:
    value = config["ner_weight"] * ner + config["topic_weight"] * topic + config["novelty_weight"] * novelty
    return round(min(max(value, 0.0), 1.0), 4)


def score_candidates(candidates: list[Candidate], overlaps: list, config: dict) -> None:
    """Fill in scores, titles and descriptions in place. ``overlaps`` aligns with candidates."""
    ner = ner_scores([sum(c.entity_mentions.values()) for c in candidates])
    topic = topic_scores([c.ctfidf_score for c in candidates])
    used_titles = set()
    for candidate, overlap, n, t in zip(candidates, overlaps, ner, topic):
        candidate.ner_score = n
        candidate.topic_score = t
        candidate.novelty_score = overlap.novelty
        candidate.max_similarity = overlap.max_similarity
        candidate.overlap_status = overlap.status
        candidate.core_matches = overlap.matches
        candidate.composite_score = composite_score(n, t, overlap.novelty, config)
        title = candidate_title(candidate)
        if title.lower() in used_titles:
            title = f"{title}: {candidate.topic_label}"  # two themes around the same skill
        used_titles.add(title.lower())
        candidate.title = title[:255]
        candidate.description = candidate_description(candidate)


def rank_candidates(candidates: list[Candidate], limit: int) -> list[Candidate]:
    """Rank by composite score S_c, highest first, and keep the top ``limit`` (spec v2 §6).
    Potential duplicates stay in the ranking; their low novelty lowers S_c and the
    overlap badge marks them for the planner."""
    return sorted(candidates, key=lambda c: (-c.composite_score, c.topic_id))[:limit]
