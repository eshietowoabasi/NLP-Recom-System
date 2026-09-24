# Evaluation data (spec §17)

The `*.sample.*` files are **synthetic examples of each file format**. They are
not evaluation results. Replace them with the real data collected for the project
and run the matching `flask eval` command from `backend/`. Each command prints a
summary and writes full results as JSON under `reports/evaluation/`.

| Evaluation | Spec | Command | Input |
|---|---|---|---|
| NER precision / recall / F1 and inter-annotator agreement | §17.1 | `flask eval ner FILE.jsonl [--mode strict\|lenient\|document]` | 50 annotated job adverts |
| BERTopic vs LDA (C_v coherence ≥ 0.50, topic diversity) | §8.5, §17.2 | `flask eval topics --input-dir DIR` or `--session-id N` | The analysis corpus |
| Semantic overlap AUC-ROC ≥ 0.80, recommended threshold | §17.3 | `flask eval similarity FILE.csv [--threshold 0.80]` | 30 expert-labelled topic pairs |
| Recommendation coverage (accepted ÷ reviewed ≥ 0.85) | spec v2 | `flask eval coverage --session-id N` (repeatable) | Planner decisions in completed sessions |
| System Usability Scale | §17.4 | `flask eval sus FILE.csv` | UAT questionnaires (5–10 participants) |
| Pipeline performance | §17.5 | `flask eval performance [--input-dir DIR]` | Synthetic 20 × 3,000 words, or real documents |

Run the similarity, topics and performance evaluations with the **SBERT
backend** (`EMBEDDING_BACKEND=sbert`). With `hashing`, the results don't
describe the real system, and the commands print a warning.

## NER annotations (`.jsonl`, one job advert per line)

```json
{"id": "ad-001", "text": "…advert text…",
 "annotator_a": [{"start": 10, "end": 16, "label": "TECHNOLOGY"}],
 "annotator_b": [{"start": 10, "end": 16, "label": "TECHNOLOGY"}],
 "gold":        [{"start": 10, "end": 16, "label": "TECHNOLOGY"}]}
```

- Labels (spec v2): `TECHNOLOGY` (languages, frameworks, platforms, tools),
  `SKILL` (knowledge areas and competencies, including certifications) and
  `METHODOLOGY` (Agile, DevOps, CI/CD, TDD and similar practices).
- `start` and `end` are character offsets, with `end` exclusive. If offsets are
  impractical to record, use `{"text": "Kubernetes", "label": "TECHNOLOGY"}` and run
  with `--mode document`.
- `gold` is the adjudicated set after the two annotators resolve their
  disagreements. Where it's missing, annotator A's labels are used and a
  warning is printed.
- The output reports agreement between the two annotators (pairwise F1 and
  token-level Cohen's kappa) alongside the system's scores.

## Similarity pairs (`.csv`)

`pair_id, candidate_topic, core_topic, expert_overlap`. Set `expert_overlap`
to 1 if the experts judge the candidate to duplicate the NUC core topic, and 0
otherwise. The output includes AUC-ROC, precision, recall and F1 at the
configured threshold, and the Youden-optimal threshold. Use that last figure to
calibrate `similarity_threshold`.

## SUS responses (`.csv`)

`respondent_id, q1 … q10`, each answer 1–5, using the standard SUS item order
(odd items positive, even items negative). The output gives each respondent's
score, the mean, SD and range, an adjective grade (Bangor et al., 2009), and
whether the target mean of at least 70 is met.
