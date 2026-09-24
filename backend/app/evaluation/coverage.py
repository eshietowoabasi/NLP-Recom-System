"""Recommendation coverage (spec v2 §5): share of recommendations planners judged
relevant (accepted) among those they decided on in UAT sessions. Target >= 85%."""
from sqlalchemy import func, select

from ..extensions import db
from ..models import AnalysisSession, PlannerDecision, Recommendation

TARGET = 0.85


def evaluate_coverage(session_ids: list[int]) -> dict:
    sessions = []
    totals = {"accepted": 0, "rejected": 0, "pending": 0}
    for session_id in session_ids:
        session = db.session.get(AnalysisSession, session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        counts = dict(db.session.execute(
            select(Recommendation.planner_decision, func.count())
            .where(Recommendation.session_id == session_id)
            .group_by(Recommendation.planner_decision)
        ).all())
        row = {
            "session_id": session_id,
            "session_name": session.session_name,
            "accepted": counts.get(PlannerDecision.ACCEPTED, 0),
            "rejected": counts.get(PlannerDecision.REJECTED, 0),
            "pending": counts.get(None, 0),
        }
        decided = row["accepted"] + row["rejected"]
        row["coverage"] = round(row["accepted"] / decided, 4) if decided else None
        sessions.append(row)
        for key in totals:
            totals[key] += row[key]
    decided = totals["accepted"] + totals["rejected"]
    coverage = round(totals["accepted"] / decided, 4) if decided else None
    warnings = []
    if totals["pending"]:
        warnings.append(f"{totals['pending']} recommendation(s) are still pending and are not counted.")
    if not decided:
        warnings.append("No decisions recorded yet.")
    return {
        **totals,
        "coverage": coverage,
        "target": TARGET,
        "meets_target": coverage is not None and coverage >= TARGET,
        "sessions": sessions,
        "warnings": warnings,
    }
