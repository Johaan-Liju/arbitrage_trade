"""Persist real-data paper sessions and explicit abstentions without fake signals."""
import json
from uuid import uuid4
from . import alerts
from .public_sources import timestamp
from .reference import ReferenceFailure

REASON = "MODEL_NOT_EVALUATED: real source quotes are browsable, but verified terms, historical availability, liquidity and an evaluated real-data model are required for opportunity alerts."


def catalog(current):
    return {"dataset": "real", "default_as_of": current["as_of"],
        "contracts": current["contracts"], "model_version": "real-data-pending", "protocol_hash": "not-evaluated",
        "model_evaluated": False, "defaults": alerts.AlertSettings().model_dump(mode="json"),
        "calibration": {"evaluated": False, "probability": None, "reason": REASON},
        "evaluation": {"report_id": None, "as_of": current["as_of"], "metrics": {},
            "scope": "Real market data: evaluation pending", "evidence": {"missing_or_insufficient": [REASON]}},
        "disclaimer": alerts.DISCLAIMER}


def new_session(root, request):
    session = {"id": uuid4().hex, "dataset": "real", "created_at": timestamp(),
        "settings": request.settings.model_dump(mode="json"), "model_version": "real-data-pending",
        "protocol_hash": "not-evaluated", "report_id": None}
    with alerts.database(root, "real") as db:
        db.execute("INSERT INTO sessions VALUES(?,?,NULL)", (session["id"], json.dumps(session)))
    return session


def scan(root, request, current):
    with alerts.database(root, "real") as db:
        session = alerts.get_session(db, request.session_id)
        previous = db.execute("SELECT payload FROM scans WHERE session_id=? AND as_of=?",
                              (request.session_id, request.as_of)).fetchone()
        if previous:
            return {**json.loads(previous[0]), "repeated_scan": True}
        if session["last_as_of"] and request.as_of < session["last_as_of"]:
            raise ReferenceFailure("NON_MONOTONIC_SCAN", "Start a new session to scan an earlier cutoff")
        count = sum(len(rows) for rows in current["histories"].values())
        result = {"dataset": "real", "session_id": request.session_id, "as_of": request.as_of,
            "status": "SUPPRESSED", "reason": REASON if count else "NO_OBSERVATIONS: no real records were known at this cutoff.",
            "input_status": "UNVERIFIED" if count else "MISSING", "signal_eligible": False,
            "prediction": None, "new_alert_ids": [], "repeated_scan": False,
            "observations_reviewed": count, "contracts_reviewed": len(current["contracts"])}
        db.execute("INSERT INTO scans VALUES(?,?,?)", (request.session_id, request.as_of, json.dumps(result)))
        db.execute("UPDATE sessions SET last_as_of=? WHERE id=?", (request.as_of, request.session_id))
        return result
