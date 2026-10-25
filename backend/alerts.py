"""Local paper notifications. Frozen signals and append-only as-of outcome journals."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from . import opportunity, opportunity_evaluation
from .domain import DEFAULT_AS_OF, utc
from .opportunity import OpportunityRequest, PairResearch, PROTOCOL, PROTOCOL_HASH, timestamp
from .reference import ReferenceFailure, canonical_hash
from .research import contract_view, snapshot

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/research/evaluations/synthetic/328f38620dca811605488161635a4c3bfd9ffb89e4072caf2655cbaab42ac4b1.json"
DISCLAIMER = "Paper research only. Daily prices are hypothetical execution proxies. Costs, liquidity, execution and settlement remain uncertain. No trades are executed."


class AlertSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy: Literal["model", "baseline"] = "model"
    min_abs_z: Decimal = Field(default=Decimal("2.5"), ge=Decimal("2.5"), le=100, allow_inf_nan=False)
    min_severe_net_bps: Decimal = Field(default=Decimal("10"), ge=10, le=10000, allow_inf_nan=False)
    max_age_hours: int = Field(default=24, ge=1, le=24, strict=True)
    cooldown_hours: int = Field(default=24, ge=0, le=720, strict=True)
    expires_hours: int = Field(default=12, ge=1, le=24, strict=True)


class NewSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: Literal["synthetic", "real"]
    settings: AlertSettings = Field(default_factory=AlertSettings)


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: Literal["synthetic", "real"]
    session_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    as_of: str

    @model_validator(mode="after")
    def validate_time(self):
        utc(self.as_of)
        return self


def iso(value):
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def evidence(dataset):
    if dataset != "synthetic":
        raise ReferenceFailure("MODEL_NOT_EVALUATED", "No evaluated real-data model is registered; opportunity alerts are suppressed")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    digest = canonical_hash({k: v for k, v in report.items() if k != "report_id"})
    implementation = sha256(Path(opportunity_evaluation.__file__).read_bytes() + Path(opportunity.__file__).read_bytes()).hexdigest()
    if digest != report["report_id"] or report["protocol_hash"] != PROTOCOL_HASH or implementation != report["implementation_hash"]:
        raise ReferenceFailure("EVALUATION_MISMATCH", "Model implementation or evaluation report changed; evaluate and register the new version before issuing alerts")
    return report


@contextmanager
def database(root, dataset):
    if dataset not in ("synthetic", "real"):
        raise ValueError("Unknown alert dataset")
    path = Path(root) / dataset / "alerts.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    try:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, payload TEXT NOT NULL, last_as_of TEXT);
            CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY, session_id TEXT NOT NULL, dedup_key TEXT NOT NULL,
                signal_at TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(session_id,dedup_key));
            CREATE TABLE IF NOT EXISTS scans(session_id TEXT NOT NULL, as_of TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(session_id,as_of));
            CREATE TABLE IF NOT EXISTS outcomes(alert_id TEXT NOT NULL, as_of TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(alert_id,as_of));
            CREATE TABLE IF NOT EXISTS receipts(alert_id TEXT PRIMARY KEY, read_at TEXT NOT NULL);
        """)
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def catalog(path, dataset, as_of):
    utc(as_of)
    registry, _ = snapshot(path, dataset, as_of)
    report = evidence(dataset)
    selection = report["request"]["pairs"][0]
    request = OpportunityRequest.model_validate({**report["request"], "as_of": as_of})
    pair = PairResearch(registry, [], request, request.pairs[0])
    return {"dataset": dataset, "default_as_of": DEFAULT_AS_OF,
            "contracts": [contract_view(s, c) for s, c in zip(pair.specs, pair.listings)],
            "pair": selection, "model_version": PROTOCOL["version"], "protocol_hash": PROTOCOL_HASH,
            "evaluation": {"report_id": report["report_id"], "as_of": report["as_of"],
                           "metrics": report["held_out"]["metrics"], "evidence": report["evidence"],
                           "scope": "Synthetic GOLDTEN/GOLDGUINEA, exact expiry 2026-11-20, demo-v4"},
            "calibration": {"evaluated": False, "probability": None,
                            "reason": "Deterministic scores; probability calibration has not been evaluated"},
            "defaults": AlertSettings().model_dump(mode="json"), "disclaimer": DISCLAIMER}


def new_session(path, root, request):
    # Fail before creating storage when the dataset or evaluated model is unavailable.
    catalog(path, request.dataset, DEFAULT_AS_OF)
    report = evidence(request.dataset)
    session = {"id": uuid4().hex, "dataset": request.dataset,
               "created_at": iso(datetime.now(timezone.utc)), "settings": request.settings.model_dump(mode="json"),
               "report_id": report["report_id"], "model_version": PROTOCOL["version"],
               "protocol_hash": PROTOCOL_HASH, "pair": report["request"]["pairs"][0]}
    with database(root, request.dataset) as db:
        db.execute("INSERT INTO sessions VALUES(?,?,NULL)", (session["id"], json.dumps(session)))
    return session


def sessions(root, dataset):
    if not (Path(root) / dataset / "alerts.sqlite3").exists():
        return {"sessions": []}
    with database(root, dataset) as db:
        return {"sessions": [{**json.loads(r["payload"]), "last_as_of": r["last_as_of"]}
                             for r in db.execute("SELECT * FROM sessions ORDER BY rowid DESC")]}


def get_session(db, identifier):
    row = db.execute("SELECT * FROM sessions WHERE id=?", (identifier,)).fetchone()
    if not row:
        raise ReferenceFailure("UNKNOWN_SESSION", "Paper session is not in this dataset")
    return {**json.loads(row["payload"]), "last_as_of": row["last_as_of"]}


def threshold_reason(record, settings, as_of):
    if record["eligibility"] != "ELIGIBLE":
        return record["reason"]
    if any((timestamp(as_of) - timestamp(r["observed_at"])).total_seconds() > settings.max_age_hours * 3600
           for r in record["features"]["current"]):
        return "STALE: source exceeds your freshness limit"
    if abs(Decimal(record["features"]["z_score"])) < settings.min_abs_z:
        return "THRESHOLD: spread score is below your minimum absolute z"
    package = record.get("forecast", {}).get("estimated_package")
    if package is None:
        return "MISSING_COSTS: a valid estimated package is required"
    if settings.policy == "model" and (not record["model_alert"] or
            Decimal(package["scenarios"]["SEVERE"]["net_return"]) * 10000 <= settings.min_severe_net_bps):
        return "COST_FILTER: estimated severe-cost return does not exceed the configured threshold"
    if not record[settings.policy + "_alert"]:
        return "MODEL_ABSTAINED: evaluated policy did not signal"
    return None


def alert_payload(pair, record, session, settings, as_of):
    # Stop accepting the signal before its planned paper entry and safety boundary.
    windows = [c.day(record["planned_entry"], as_of).windows for c in pair.calendars]
    entry_open = min(max(a.opens_at, b.opens_at) for a in windows[0] for b in windows[1]
                     if max(a.opens_at, b.opens_at) < min(a.closes_at, b.closes_at))
    expires = min([iso(timestamp(as_of) + timedelta(hours=settings.expires_hours)), entry_open,
                   record["safety_deadline"] + "T00:00:00Z"] +
                  [iso(timestamp(r["observed_at"]) + timedelta(hours=settings.max_age_hours))
                   for r in record["features"]["current"]])
    observations = []
    for day in [r["trading_date"] for r in record["features"]["prior_provenance"]] + [record["trading_date"]]:
        for i, mapping in enumerate(pair.maps):
            row = mapping[day]
            observations.append({**row, "contract_id": [record["contract_a"], record["contract_b"]][i]})
    return {"dataset": session["dataset"], "signal_at": as_of, "expires_at": expires,
            "policy": settings.policy, "model_version": session["model_version"],
            "protocol_hash": session["protocol_hash"], "evaluation_report_id": session["report_id"],
            "settings": settings.model_dump(mode="json"), "record": record,
            "contracts": [contract_view(s, c) for s, c in zip(pair.specs, pair.listings)],
            "observations": observations, "horizon": {"holding_sessions": 5, "entry": record["planned_entry"],
                                                       "exit": record["planned_exit"], "entry_opens_at": entry_open},
            "probability": None, "calibration_evaluated": False,
            "liquidity_uncertainty": "Volume and open interest are daily proxies. Bid/ask, order-book depth and executable fills are unknown; package participation must be at most 1% of both proxies.",
            "settlement_uncertainty": "Exact versioned delivery and settlement terms are shown for each leg. Equal gold weight does not ensure fungible delivery. Funding, margin, taxes, delivery premia and settlement performance are unverified.",
            "cost_uncertainty": "BASE/STRESS/SEVERE are assumed brokerage, other-charge and slippage budgets for both legs on entry and exit. Reversion to the prior mean is an uncalibrated hypothesis.",
            "disclaimer": DISCLAIMER}


def paper_outcome(pair, alert, as_of):
    if pair is None:
        return {"status": "UNAVAILABLE", "label": None, "as_of": as_of,
                "reason": "Required source or evaluation is unavailable; no outcome inferred"}
    result = pair.outcome(alert["record"])
    # An unobserved future endpoint is pending, never a loss or a completed label.
    if result["status"] != "COMPLETE":
        stage = "ENTRY" if result["status"] == "CENSORED_ENTRY" else "EXIT"
        endpoint = alert["horizon"][stage.lower()]
        if as_of[:10] <= endpoint:
            result["status"] = "PENDING_" + stage
    return result


def scan(path, root, request):
    with database(root, request.dataset) as db, localcontext() as context:
        context.prec = 34
        session = get_session(db, request.session_id)
        if session["last_as_of"] and request.as_of < session["last_as_of"]:
            raise ReferenceFailure("CHRONOLOGY", "Advance the cutoff for this paper session, or start a new session to replay an earlier period")
        prior_scan = db.execute("SELECT payload FROM scans WHERE session_id=? AND as_of=?",
                                (request.session_id, request.as_of)).fetchone()
        if prior_scan:
            return {**json.loads(prior_scan[0]), "new_alert_ids": [], "repeated_scan": True}
        settings = AlertSettings.model_validate(session["settings"])
        pair, record, reason = None, None, None
        try:
            report = evidence(request.dataset)
            if report["report_id"] != session["report_id"]:
                raise ReferenceFailure("EVALUATION_MISMATCH", "Start a session for the newly evaluated version")
            registry, raw = snapshot(path, request.dataset, request.as_of)
            req = OpportunityRequest(dataset=request.dataset, as_of=request.as_of, pairs=[session["pair"]])
            pair = PairResearch(registry, raw, req, req.pairs[0])
            dates = sorted(set(pair.maps[0]) | set(pair.maps[1]))
            if not dates:
                reason = "MISSING_INPUTS: no known observations at this cutoff"
            else:
                record = pair.record(dates[-1], at=request.as_of, outcomes=False)
                reason = threshold_reason(record, settings, request.as_of)
        except (ReferenceFailure, ValueError, KeyError, OSError, sqlite3.DatabaseError) as error:
            reason = f"{getattr(error, 'code', 'INVALID_INPUT')}: {error}"
            pair = None
        new_ids = []
        if reason is None:
            dedup = canonical_hash({"dataset": request.dataset, "pair": session["pair"],
                                    "policy": settings.policy, "protocol": session["protocol_hash"],
                                    "trading_date": record["trading_date"], "sides": record["sides"]})
            duplicate = db.execute("SELECT id FROM alerts WHERE session_id=? AND dedup_key=?",
                                   (request.session_id, dedup)).fetchone()
            last = db.execute("SELECT signal_at FROM alerts WHERE session_id=? ORDER BY signal_at DESC LIMIT 1",
                              (request.session_id,)).fetchone()
            if duplicate:
                reason = "DEDUPLICATED: this exact pair, version, trading date and direction already notified in this session"
            elif last and timestamp(request.as_of) < timestamp(last[0]) + timedelta(hours=settings.cooldown_hours):
                reason = "COOLDOWN: the pair is still within this session's notification cooldown"
            else:
                alert = alert_payload(pair, record, session, settings, request.as_of)
                if alert["expires_at"] <= request.as_of:
                    reason = "EXPIRED: signal acceptance window has closed"
                else:
                    identifier = canonical_hash({"session": request.session_id, "dedup": dedup})
                    alert["id"] = identifier
                    db.execute("INSERT INTO alerts VALUES(?,?,?,?,?)", (identifier, request.session_id, dedup,
                               request.as_of, json.dumps(alert)))
                    new_ids.append(identifier)
        for row in db.execute("SELECT id,payload FROM alerts WHERE session_id=?", (request.session_id,)).fetchall():
            alert = json.loads(row["payload"])
            outcome = paper_outcome(pair, alert, request.as_of)
            db.execute("INSERT INTO outcomes VALUES(?,?,?)", (row["id"], request.as_of, json.dumps(outcome)))
        result = {"dataset": request.dataset, "session_id": request.session_id, "as_of": request.as_of,
                  "status": "NOTIFIED" if new_ids else "SUPPRESSED", "reason": reason,
                  "input_status": "READY" if record and record["eligibility"] == "ELIGIBLE" and pair
                  and not (reason or "").startswith(("STALE", "MISSING_COSTS")) else "BLOCKED",
                  "signal_eligible": record is not None and pair is not None and threshold_reason(record, settings, request.as_of) is None,
                  "prediction": record, "new_alert_ids": new_ids, "repeated_scan": False}
        db.execute("INSERT INTO scans VALUES(?,?,?)", (request.session_id, request.as_of, json.dumps(result)))
        db.execute("UPDATE sessions SET last_as_of=? WHERE id=?", (request.as_of, request.session_id))
        return result


def history(root, dataset, session_id, as_of):
    utc(as_of)
    with database(root, dataset) as db:
        session = get_session(db, session_id)
        scan_row = db.execute("SELECT payload FROM scans WHERE session_id=? AND as_of<=? ORDER BY as_of DESC LIMIT 1",
                              (session_id, as_of)).fetchone()
        last_scan = json.loads(scan_row[0]) if scan_row else None
        alerts = []
        for row in db.execute("SELECT * FROM alerts WHERE session_id=? AND signal_at<=? ORDER BY signal_at DESC", (session_id, as_of)):
            alert = json.loads(row["payload"])
            journal = [json.loads(r[0]) for r in db.execute("SELECT payload FROM outcomes WHERE alert_id=? AND as_of<=? ORDER BY as_of", (row["id"], as_of))]
            expired = as_of >= alert["expires_at"]
            status = "EXPIRED" if expired else "ACTIVE" if last_scan and last_scan["signal_eligible"] else "SUPPRESSED"
            read = db.execute("SELECT read_at FROM receipts WHERE alert_id=?", (row["id"],)).fetchone()
            alerts.append({**alert, "status": status, "read": bool(read), "outcome": journal[-1] if journal else None,
                           "outcome_history": journal})
        return {"dataset": dataset, "as_of": as_of, "session": session, "last_scan": last_scan,
                "alerts": alerts, "unread_count": sum(not a["read"] for a in alerts),
                "active_count": sum(a["status"] == "ACTIVE" for a in alerts), "disclaimer": DISCLAIMER}


def mark_read(root, dataset, session_id, alert_id):
    with database(root, dataset) as db:
        get_session(db, session_id)
        if not db.execute("SELECT id FROM alerts WHERE id=? AND session_id=?", (alert_id, session_id)).fetchone():
            raise ReferenceFailure("UNKNOWN_ALERT", "Alert is not in this paper session")
        db.execute("INSERT OR IGNORE INTO receipts VALUES(?,?)", (alert_id, iso(datetime.now(timezone.utc))))
    return {"read": True}
