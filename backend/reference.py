"""Versioned, fail-closed reference data. Documented fields are not live approval."""
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .domain import utc

REFERENCE_FILE = Path(__file__).resolve().parents[1] / "data/reference/mcx-2026-10-24.json"
Status = Literal["VERIFIED", "UNVERIFIED", "SYNTHETIC"]


class ReferenceFailure(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def exact_date(value: str) -> date:
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("Expected exact YYYY-MM-DD date, not a month label")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Expected exact YYYY-MM-DD date")
    return parsed


def canonical_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class SpecVersion(FrozenModel):
    spec_id: str = Field(min_length=1)
    instrument: Literal["GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL"]
    dataset: Literal["real", "synthetic"]
    version: str = Field(min_length=1)
    verification_status: Status
    source_url: str | None
    retrieved_at: str
    available_at: str  # Earliest proven knowledge of this exact document version, not guessed midnight.
    effective_date: str | None
    effective_until: str | None = None
    verified_through: str | None
    applicability: str
    lot_size_grams: Decimal | None = Field(default=None, gt=0)
    quotation_grams: Decimal | None = Field(default=None, gt=0)
    quote_purity_per_mille: Decimal | None = Field(default=None, gt=0, le=1000)
    currency: Literal["INR"] = "INR"
    price_unit: Literal["INR_PER_QUOTATION"] = "INR_PER_QUOTATION"
    delivery_locations: tuple[str, ...] = ()
    expiry_restrictions: str | None = None
    delivery_restrictions: str | None = None
    evidence: dict[str, str] = Field(default_factory=dict)
    unresolved: tuple[str, ...] = ()

    @model_validator(mode="after")
    def structure(self):
        utc(self.retrieved_at)
        utc(self.available_at)
        for value in (self.effective_date, self.effective_until, self.verified_through):
            if value is not None:
                exact_date(value)
        if self.dataset == "real" and self.verification_status == "SYNTHETIC":
            raise ValueError("Synthetic reference cannot authorize real data")
        if self.effective_date and self.effective_until and self.effective_date > self.effective_until:
            raise ValueError("Invalid effective date interval")
        return self

    def require_usable(self, trading_date: str, as_of: str):
        expected = "VERIFIED" if self.dataset == "real" else "SYNTHETIC"
        if self.verification_status != expected or self.unresolved:
            raise ReferenceFailure("UNVERIFIED_SPEC", f"{self.spec_id} is not approved: {'; '.join(self.unresolved) or self.verification_status}")
        required = (self.source_url, self.effective_date, self.verified_through, self.lot_size_grams,
                    self.quotation_grams, self.quote_purity_per_mille, self.delivery_locations,
                    self.expiry_restrictions, self.delivery_restrictions)
        if any(value is None or value == "" or value == () for value in required):
            raise ReferenceFailure("UNVERIFIED_SPEC", "Specification has missing required terms")
        if self.dataset == "real" and not official_url(self.source_url):
            raise ReferenceFailure("UNVERIFIED_SPEC", "Real specifications require an official MCX source")
        if not self.effective_date <= trading_date <= self.verified_through or (self.effective_until and trading_date > self.effective_until):
            raise ReferenceFailure("STALE_SPEC", "Trading date is outside the verified specification interval")
        if self.available_at > as_of:
            raise ReferenceFailure("FUTURE_SPEC", "Specification was not available at the requested as-of time")


def official_url(url: str | None) -> bool:
    host = urlparse(url or "").hostname or ""
    return urlparse(url or "").scheme == "https" and (host == "mcxindia.com" or host.endswith(".mcxindia.com") or host == "mcxccl.com" or host.endswith(".mcxccl.com"))


class ListedContract(FrozenModel):
    instrument: str
    expiry: str
    spec_id: str
    first_trade_date: str | None
    last_trade_date: str
    verification_status: Status
    source_url: str
    available_at: str
    delivery_start: str | None = None
    delivery_end: str | None = None

    @model_validator(mode="after")
    def structure(self):
        for value in (self.expiry, self.first_trade_date, self.last_trade_date, self.delivery_start, self.delivery_end):
            if value is not None:
                exact_date(value)
        utc(self.available_at)
        if self.last_trade_date > self.expiry:
            raise ValueError("Last trading date exceeds exact expiry")
        if self.first_trade_date and self.first_trade_date > self.last_trade_date:
            raise ValueError("Invalid listing interval")
        return self


class SessionWindow(FrozenModel):
    name: str
    opens_at: str
    closes_at: str

    @model_validator(mode="after")
    def structure(self):
        if utc(self.opens_at) >= utc(self.closes_at):
            raise ValueError("Invalid session window")
        return self


class CalendarDay(FrozenModel):
    state: Literal["OPEN", "PARTIAL", "CLOSED"]
    windows: tuple[SessionWindow, ...] = ()

    @model_validator(mode="after")
    def structure(self):
        if (self.state == "CLOSED") != (len(self.windows) == 0):
            raise ValueError("Open/partial days require explicit windows; closed days require none")
        return self


class SessionCalendar(FrozenModel):
    calendar_id: str
    dataset: Literal["real", "synthetic"]
    verification_status: Status
    source_url: str
    available_at: str
    coverage_start: str
    coverage_end: str
    days: dict[str, CalendarDay]
    unresolved: tuple[str, ...] = ()

    @model_validator(mode="after")
    def structure(self):
        utc(self.available_at)
        if exact_date(self.coverage_start) > exact_date(self.coverage_end):
            raise ValueError("Invalid calendar coverage")
        for day in self.days:
            exact_date(day)
            if not self.coverage_start <= day <= self.coverage_end:
                raise ValueError("Day outside calendar coverage")
        return self

    def day(self, day: str, as_of: str) -> CalendarDay:
        expected = "VERIFIED" if self.dataset == "real" else "SYNTHETIC"
        if self.verification_status != expected or self.unresolved or (self.dataset == "real" and not official_url(self.source_url)):
            raise ReferenceFailure("UNVERIFIED_CALENDAR", "A verified, versioned trading-session calendar is required")
        if self.available_at > as_of:
            raise ReferenceFailure("FUTURE_CALENDAR", "Calendar was not available at the as-of time")
        if not self.coverage_start <= day <= self.coverage_end or day not in self.days:
            raise ReferenceFailure("UNKNOWN_SESSION", f"No explicit calendar coverage for {day}; weekdays are not inferred")
        return self.days[day]


class ReferenceRegistry(FrozenModel):
    schema_version: Literal["goldlens.reference.v1"] = "goldlens.reference.v1"
    specs: tuple[SpecVersion, ...]
    contracts: tuple[ListedContract, ...]
    calendars: tuple[SessionCalendar, ...]

    @model_validator(mode="after")
    def unique(self):
        keys = [s.spec_id for s in self.specs]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate specification version IDs")
        keys = [(c.instrument, c.expiry, c.spec_id) for c in self.contracts]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate exact contract reference")
        if len({c.calendar_id for c in self.calendars}) != len(self.calendars):
            raise ValueError("Duplicate calendar IDs")
        return self

    def spec(self, spec_id: str) -> SpecVersion:
        for item in self.specs:
            if item.spec_id == spec_id:
                return item
        raise ReferenceFailure("UNKNOWN_SPEC", f"Unknown exact specification version: {spec_id}")

    def contract(self, instrument: str, expiry: str, spec_id: str) -> ListedContract:
        for item in self.contracts:
            if (item.instrument, item.expiry, item.spec_id) == (instrument, expiry, spec_id):
                return item
        raise ReferenceFailure("UNCONFIRMED_EXPIRY", f"No exact listing for {instrument} / {expiry} / {spec_id}")

    def calendar(self, calendar_id: str) -> SessionCalendar:
        for item in self.calendars:
            if item.calendar_id == calendar_id:
                return item
        raise ReferenceFailure("UNVERIFIED_CALENDAR", f"Unknown calendar version: {calendar_id}")


def load_registry(path=REFERENCE_FILE) -> ReferenceRegistry:
    return ReferenceRegistry.model_validate_json(Path(path).read_text(encoding="utf-8"))


def normalize_999(price: Decimal, spec: SpecVersion, trading_date: str, as_of: str) -> Decimal:
    """Convert quote-basis metal to a 999-per-mille gram; never divide by lot size."""
    exact_date(trading_date)
    utc(as_of)
    spec.require_usable(trading_date, as_of)
    if not price.is_finite() or price <= 0:
        raise ReferenceFailure("INVALID_PRICE", "Gold prices must be finite and strictly positive")
    return price / spec.quotation_grams * Decimal(999) / spec.quote_purity_per_mille


def match_observations(left: dict, right: dict) -> dict:
    """Describes relationships without joining, averaging, or overwriting either identity."""
    if left["dataset"] != right["dataset"]:
        return {"relationship": "DATASET_MISMATCH", "comparable": False, "expiry_difference_days": None, "basis_differences": ["dataset"], "gap_pct": None}
    expiry_days = (exact_date(right["expiry"]) - exact_date(left["expiry"])).days
    differences = [key for key in ("instrument", "spec_id", "delivery_locations", "delivery_restrictions", "currency") if left.get(key) != right.get(key)]
    same_date = left["trading_date"] == right["trading_date"]
    relationship = "EXACT_EXPIRY" if expiry_days == 0 else "CALENDAR_BASIS_DIFFERENCE"
    if not same_date:
        relationship = "TRADING_DATE_MISMATCH"
    comparable = same_date and expiry_days == 0 and not differences
    gap = None
    if comparable and left.get("normalized_999_inr_per_gram") and right.get("normalized_999_inr_per_gram"):
        gap = str((Decimal(right["normalized_999_inr_per_gram"]) / Decimal(left["normalized_999_inr_per_gram"]) - 1) * 100)
    return {"relationship": relationship, "comparable": comparable, "expiry_difference_days": expiry_days,
            "basis_differences": differences, "gap_pct": gap,
            "note": "Purity adjustment does not remove delivery, expiry, location, fee or execution differences."}
