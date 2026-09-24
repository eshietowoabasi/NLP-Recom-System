"""Behaviour introduced to match the updated specification (docs/NLP_RS_Developer_Documentation_v2.pdf)."""
import io

import numpy as np
import pytest

from app.models import Document, FileType, Role, SourceCategory
from app.services.ingestion import parse_document

CORE_CSV = (
    "course_code,course_title,credit_units,description\n"
    "CSC 301,Computer and Network Security,3,\"Threats, penetration testing and incident response.\"\n"
    "CSC 405,Introduction to Data Science,3,Statistics and machine learning with Python.\n"
    "CSC 399,Industrial Training,,\n"
).encode()


# --- CSV ingestion (spec v2 §5 stage 1, §9 seed data) ------------------------------

def test_csv_course_list_becomes_one_block_per_course():
    blocks = parse_document(CORE_CSV, FileType.CSV).blocks
    assert blocks == [
        "CSC 301: Computer and Network Security. Threats, penetration testing and incident response.",
        "CSC 405: Introduction to Data Science. Statistics and machine learning with Python.",
        "CSC 399: Industrial Training",
    ]


@pytest.mark.parametrize(
    "data, expected",
    [
        (b"code;title\nCSC 101;Introduction to Computing\n", ["CSC 101: Introduction to Computing"]),
        (b"description\nWe need Python developers.\n", ["We need Python developers."]),
        (b"Python,Django,Lagos\nJava,Spring,Abuja\n", ["Python | Django | Lagos", "Java | Spring | Abuja"]),
    ],
    ids=["semicolon-course-list", "description-only", "no-header"],
)
def test_csv_variants(data, expected):
    assert parse_document(data, FileType.CSV).blocks == expected


def test_csv_upload_and_seed_core(app, client, db, make_user, login, tmp_path):
    admin = make_user("admin", role=Role.ADMIN)
    login("admin")
    resp = client.post("/api/documents", data={"file": (io.BytesIO(b"title,description\nJob,Python role\n"), "ads.csv"),
                                               "source_category": "Job Market Data"}, content_type="multipart/form-data")
    assert resp.status_code == 201 and resp.json["document"]["file_type"] == "csv"
    assert resp.json["document"]["processing_status"] == "Parsed"

    path = tmp_path / "core.csv"
    path.write_bytes(CORE_CSV)
    runner = app.test_cli_runner()
    result = runner.invoke(args=["seed-core", str(path), "--title", "CCMAS Computing Core"])
    assert result.exit_code == 0, result.output
    doc = db.session.query(Document).filter_by(title="CCMAS Computing Core").one()
    assert doc.source_category is SourceCategory.NUC_CORE and doc.user_id == admin.user_id
    assert doc.word_count > 10 and "(id=" in result.output
    again = runner.invoke(args=["seed-core", str(path)])
    assert again.exit_code != 0 and "already been uploaded" in again.output


def test_seed_core_needs_an_admin(app, tmp_path):
    path = tmp_path / "core.csv"
    path.write_bytes(CORE_CSV)
    result = app.test_cli_runner().invoke(args=["seed-core", str(path)])
    assert result.exit_code != 0 and "No active Admin" in result.output


def test_upload_limit_is_20_mb(app):
    assert app.config["MAX_DOCUMENT_BYTES"] == 20 * 1024 * 1024


# --- NLP defaults managed by Admins (spec v2 §1, §9) ---------------------------------

def test_admin_sets_nlp_defaults_used_by_new_sessions(client, db, make_user, login):
    make_user("admin", role=Role.ADMIN)
    login("admin")
    defaults = client.get("/api/admin/settings/nlp-defaults").json["parameter_config"]
    assert defaults["topic_count"] == 10 and defaults["similarity_threshold"] == 0.8

    resp = client.put("/api/admin/settings/nlp-defaults", json={"topic_count": 6, "similarity_threshold": 0.75})
    assert resp.status_code == 200 and resp.json["parameter_config"]["topic_count"] == 6
    bad = client.put("/api/admin/settings/nlp-defaults", json={"ner_weight": 0.9})
    assert bad.status_code == 422 and "weights" in bad.json["error"]["details"]
    assert client.put("/api/admin/settings/nlp-defaults", json={"topic_count": 1}).status_code == 422

    client.post("/api/auth/logout")
    make_user("planner", role=Role.PLANNER)
    login("planner")
    assert client.get("/api/admin/settings/nlp-defaults").status_code == 403
    assert client.get("/api/sessions/defaults").json["parameter_config"]["topic_count"] == 6

    doc = Document(user_id=1, title="d", file_path="-", file_type=FileType.TXT, source_category=SourceCategory.JOB_MARKET,
                   processing_status="Parsed", extracted_text="x")
    db.session.add(doc)
    db.session.commit()
    session = client.post("/api/sessions", json={"session_name": "s", "document_ids": [doc.document_id]}).json["session"]
    assert session["parameter_config"]["topic_count"] == 6 and session["parameter_config"]["similarity_threshold"] == 0.75
    override = client.post("/api/sessions", json={"session_name": "s2", "document_ids": [doc.document_id],
                                                  "parameter_config": {"topic_count": 4}}).json["session"]
    assert override["parameter_config"]["topic_count"] == 4


def test_environment_defaults(app, client, make_user, login):
    app.config.update(DEFAULT_TOPIC_COUNT=12, DEFAULT_OVERLAP_THRESHOLD=0.7)
    make_user()
    login()
    config = client.get("/api/sessions/defaults").json["parameter_config"]
    assert config["topic_count"] == 12 and config["similarity_threshold"] == 0.7


# --- Topics, scoring, decisions, mapping ---------------------------------------------

def test_topic_count_caps_number_of_topics():
    import random

    from app.services.embeddings import HashingEmbedder
    from app.services.topics import Passage, model_topics

    from .corpus import THEMES

    rng = random.Random(3)
    passages = []
    for doc_id, sentences in enumerate(THEMES.values(), start=1):
        words = " ".join(sentences).lower().replace(".", "").replace(",", "").split()
        passages += [Passage(" ".join(rng.sample(words, 10)), doc_id, "Job Market Data") for _ in range(40)]
    vectors = HashingEmbedder().encode([p.text for p in passages])
    capped = model_topics(passages, vectors, nr_topics=2)
    assert 1 <= len(capped.topics) <= 2
    assert all(t["ctfidf_score"] > 0 for t in capped.topics)
    assert len(capped.assignments) == len(passages)


def test_topic_score_is_normalised_ctfidf(client, completed_session):
    topics = {t["topic_id"]: t for t in client.get(f"/api/sessions/{completed_session}/topics").json["topics"]}
    top = max(t["ctfidf_score"] for t in topics.values())
    recs = client.get(f"/api/sessions/{completed_session}/recommendations?include_evidence=1").json["items"]
    for rec in recs:
        expected = topics[rec["evidence"]["topic_id"]]["ctfidf_score"] / top
        assert rec["topic_score"] == pytest.approx(expected, abs=1e-3)


def test_decision_undo_and_single_mapping(client, completed_session):
    recs = client.get(f"/api/sessions/{completed_session}/recommendations").json["items"]
    rec = next(r for r in recs if r["overlap_status"] == "No Significant Overlap")
    url = f"/api/recommendations/{rec['rec_id']}"
    assert client.patch(f"{url}/decision", json={"decision": "Rejected"}).json["recommendation"]["planner_decision"] == "Rejected"
    assert client.patch(f"{url}/decision", json={"decision": None}).json["recommendation"]["planner_decision"] is None
    client.patch(f"{url}/decision", json={"decision": "Accepted"})

    mapping = {"course_code": "uuy-csc411", "course_title": "Cloud-Native Application Development with Python",
               "credit_units": 3, "learning_outcomes": ["Deploy a containerised API"], "prerequisites": ["UUY-CSC 201"]}
    created = client.post(f"{url}/mapping", json=mapping)
    assert created.status_code == 201 and created.json["mapping"]["course_code"] == "UUY-CSC 411"
    again = client.post(f"{url}/mapping", json={**mapping, "course_code": "CSC 499"})
    assert again.status_code == 409 and again.json["error"]["code"] == "MAPPING_EXISTS"
    assert again.json["error"]["details"]["map_id"] == created.json["mapping"]["map_id"]


def test_pipeline_time_limits_configured(app):
    celery = app.extensions["celery"]
    limits = celery.conf.task_annotations["analysis.run"]
    assert limits["soft_time_limit"] == app.config["PIPELINE_SOFT_TIME_LIMIT"]
    assert limits["time_limit"] > limits["soft_time_limit"]


def test_soft_time_limit_message(client, db, core_document, make_user, login, monkeypatch):
    from celery.exceptions import SoftTimeLimitExceeded

    import app.services.analysis as analysis

    from .corpus import theme_text

    make_user("p", role=Role.PLANNER)
    login("p")
    doc_id = client.post("/api/documents", data={"file": (io.BytesIO(theme_text("cloud").encode()), "c.txt"),
                                                 "source_category": "Job Market Data"},
                         content_type="multipart/form-data").json["document"]["document_id"]
    session_id = client.post("/api/sessions", json={"session_name": "s", "document_ids": [doc_id]}).json["session"]["session_id"]

    def too_slow(*args, **kwargs):
        raise SoftTimeLimitExceeded()

    monkeypatch.setattr(analysis, "model_topics", too_slow)
    client.post(f"/api/sessions/{session_id}/run")
    session = client.get(f"/api/sessions/{session_id}").json["session"]
    assert session["status"] == "Failed" and "time limit" in session["error_message"]


# --- Evaluation additions ---------------------------------------------------------------

def test_coverage_evaluation(app, client, completed_session):
    from app.evaluation.coverage import evaluate_coverage

    recs = client.get(f"/api/sessions/{completed_session}/recommendations").json["items"]
    novel = [r for r in recs if r["overlap_status"] == "No Significant Overlap"]
    for rec in novel[:3]:
        client.patch(f"/api/recommendations/{rec['rec_id']}/decision", json={"decision": "Accepted"})
    client.patch(f"/api/recommendations/{novel[3]['rec_id']}/decision", json={"decision": "Rejected"})
    result = evaluate_coverage([completed_session])
    assert (result["accepted"], result["rejected"]) == (3, 1)
    assert result["coverage"] == 0.75 and not result["meets_target"] and result["target"] == 0.85
    assert result["pending"] == len(recs) - 4 and result["warnings"]

    cli = app.test_cli_runner().invoke(args=["eval", "coverage", "--session-id", str(completed_session), "--output", "/dev/null"])
    assert cli.exit_code == 0 and "75.0%" in cli.output and "NOT met" in cli.output
    with pytest.raises(ValueError):
        evaluate_coverage([999])


def test_similarity_and_topic_targets():
    from app.evaluation.similarity import evaluate_similarity
    from app.services.embeddings import HashingEmbedder

    rows = [{"pair_id": str(i), "candidate_topic": a, "core_topic": b, "expert_overlap": str(y)} for i, (a, b, y) in enumerate([
        ("network security firewalls", "network security firewalls", 1), ("cloud kubernetes", "discrete mathematics", 0),
        ("sql databases", "sql databases design", 1), ("mobile flutter apps", "operating systems", 0)])]
    result = evaluate_similarity(rows, HashingEmbedder(), 0.8)
    assert result["target_auc_roc"] == 0.80 and result["meets_target"] == (result["auc_roc"] > 0.80)
    # Inclusive threshold: identical texts (similarity 1.0) are predicted overlapping.
    assert result["per_pair"][0]["predicted_overlap"] is True
    assert np.isclose(result["per_pair"][0]["similarity"], 1.0)
