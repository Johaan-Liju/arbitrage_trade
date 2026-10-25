"""One fail-closed validation path for CSV ingestion and API research reads."""
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from .domain import utc
from .reference import ReferenceFailure, ReferenceRegistry, exact_date, normalize_999, official_url

FORMULA = "quoted_INR / quotation_grams * 999 / quote_purity_per_mille"


def normalize_observation(row: dict, registry: ReferenceRegistry, calendar_id: str, as_of: str) -> dict:
    utc(as_of)
    required = ("dataset", "instrument", "expiry", "trading_date", "spec_id", "price", "currency",
                "price_unit", "quotation_grams", "quote_purity_per_mille", "source_url", "observed_at", "available_at", "session")
    if any(key not in row or not str(row[key]).strip() for key in required):
        raise ReferenceFailure("MISSING_FIELDS", "Price identity, quote terms, session and provenance are required")
    expiry, day = exact_date(row["expiry"]), exact_date(row["trading_date"])
    observed, available = utc(row["observed_at"]), utc(row["available_at"])
    if available < observed or observed > as_of or available > as_of:
        raise ReferenceFailure("INVALID_CHRONOLOGY", "Require observed <= available <= explicit as-of")
    if day > expiry or datetime.fromisoformat(observed.replace("Z", "+00:00")).astimezone(ZoneInfo("Asia/Kolkata")).date() != day:
        raise ReferenceFailure("INVALID_TRADING_DATE", "Require exact expiry and the observation's Asia/Kolkata trading date")
    source = urlparse(row["source_url"])
    if source.scheme not in ("http", "https") or not source.hostname:
        raise ReferenceFailure("MISSING_PROVENANCE", "Price source must be an explicit HTTP(S) URL")
    spec = registry.spec(row["spec_id"])
    if spec.dataset != row["dataset"] or spec.instrument != row["instrument"] or row.get("spec_version", spec.version) != spec.version:
        raise ReferenceFailure("SPEC_IDENTITY_MISMATCH", "Price belongs to another dataset, symbol or specification version")
    spec.require_usable(row["trading_date"], as_of)
    if row["currency"] != spec.currency or row["price_unit"] != spec.price_unit:
        raise ReferenceFailure("UNIT_MISMATCH", "Currency/price unit differs from the referenced quote basis")
    if Decimal(str(row["quotation_grams"])) != spec.quotation_grams:
        raise ReferenceFailure("UNIT_MISMATCH", "Quotation grams must match the spec, not the lot weight")
    if Decimal(str(row["quote_purity_per_mille"])) != spec.quote_purity_per_mille:
        raise ReferenceFailure("PURITY_MISMATCH", "Quoted purity must match the exact specification version")
    listing = registry.contract(row["instrument"], row["expiry"], row["spec_id"])
    expected = "SYNTHETIC" if spec.dataset == "synthetic" else "VERIFIED"
    if listing.verification_status != expected or not listing.first_trade_date or not listing.source_url.strip():
        raise ReferenceFailure("UNCONFIRMED_EXPIRY", "An explicit, verified exact-expiry listing is required")
    if spec.dataset == "real" and not official_url(listing.source_url):
        raise ReferenceFailure("UNCONFIRMED_EXPIRY", "Real listings require an official source")
    if listing.available_at > as_of:
        raise ReferenceFailure("FUTURE_LISTING", "Listing was not available at the cutoff")
    if not listing.first_trade_date <= row["trading_date"] <= listing.last_trade_date:
        raise ReferenceFailure("OUTSIDE_LISTING", "Price is outside the exact listing's trading interval")
    calendar = registry.calendar(calendar_id)
    if calendar.dataset != spec.dataset:
        raise ReferenceFailure("DATASET_MISMATCH", "Calendar belongs to another dataset")
    market_day = calendar.day(row["trading_date"], as_of)
    if market_day.state == "CLOSED":
        raise ReferenceFailure("TRADING_HOLIDAY", "Observation falls on an explicitly closed session")
    window = next((w for w in market_day.windows if w.name == row["session"]), None)
    if not window or not window.opens_at <= observed <= window.closes_at:
        raise ReferenceFailure("CLOSED_SESSION", "Observation is outside its named trading session")
    for field in ("volume", "open_interest"):
        value = row.get(field)
        if value is None or value == "":
            continue  # Source did not supply this optional liquidity proxy.
        if isinstance(value, bool) or not str(value).isdigit():
            raise ReferenceFailure("INVALID_NUMBER", f"{field} must be a nonnegative integer")
    value = normalize_999(Decimal(str(row["price"])), spec, row["trading_date"], as_of)
    return {**row, "spec_version": spec.version, "price": str(row["price"]),
            "volume": int(row["volume"]) if row.get("volume") not in (None, "") else None,
            "open_interest": int(row["open_interest"]) if row.get("open_interest") not in (None, "") else None,
            "lot_size_grams": str(spec.lot_size_grams), "quotation_grams": str(spec.quotation_grams),
            "quote_purity_per_mille": str(spec.quote_purity_per_mille), "calendar_id": calendar_id,
            "normalized_available_at": max(available, spec.available_at, listing.available_at, calendar.available_at),
            "normalized_999_inr_per_gram": str(value), "normalization_formula": FORMULA,
            "normalization_version": "999-equivalent-v1", "delivery_locations": list(spec.delivery_locations),
            "delivery_restrictions": spec.delivery_restrictions, "expiry_restrictions": spec.expiry_restrictions,
            "settlement_method": spec.settlement_method, "settlement_terms": spec.settlement_terms,
            "reference_availability": {"specification": spec.available_at, "listing": listing.available_at, "calendar": calendar.available_at}}
