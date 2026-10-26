from datetime import date, datetime, timezone
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_AS_OF = "2026-10-23T18:00:00Z"
DISCLAIMER = "SYNTHETIC research only. Invented contracts, prices and liquidity. Purity normalization is a comparison convention. Hypothetical fees and slippage do not establish executable fills; taxes, premia, margins, funding, delivery and settlement remain uncertain. No trade execution or guaranteed arbitrage."


def utc(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ValueError("Use an exact UTC timestamp: YYYY-MM-DDTHH:MM:SSZ")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Spec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    contract_id: str = Field(min_length=1)
    dataset: Literal["synthetic", "real"] = "synthetic"
    symbol: Literal["GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL"]
    expiry: date
    spec_version: str = Field(min_length=1)
    currency: Literal["INR"] = "INR"
    unit: Literal["quote"] = "quote"
    quote_grams: float = Field(ge=.001, le=1_000_000, allow_inf_nan=False)
    lot_grams: int = Field(gt=0, le=1_000_000)
    purity: float = Field(gt=0, le=1, allow_inf_nan=False)
    valid_from: date
    valid_to: date
    delivery_basis: str = Field(min_length=1)
    delivery_location: str = Field(min_length=1)
    expiry_rule: str = Field(min_length=1)
    delivery_restrictions: str = Field(min_length=1)
    evidence_url: str = Field(min_length=1)
    verification: Literal["SYNTHETIC", "UNVERIFIED", "VERIFIED"]
    tender_start: date
    safe_exit_date: date
    available_at: str
    source: str = "GoldLens deterministic generator v1"
    description: str = "Invented demo specification; not verified exchange terms"

    @model_validator(mode="after")
    def validate_time(self):
        utc(self.available_at)
        if not self.valid_from <= self.valid_to:
            raise ValueError("Invalid specification validity interval")
        if not self.safe_exit_date < self.tender_start <= self.expiry:
            raise ValueError("Safe exit must precede tender and expiry")
        if (self.dataset == "synthetic") != (self.verification == "SYNTHETIC"):
            raise ValueError("Dataset and verification disagree")
        return self


class Price(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_id: str
    dataset: Literal["synthetic", "real"]
    symbol: str = Field(min_length=1)
    expiry: date
    spec_version: str = Field(min_length=1)
    trading_date: date
    price: float = Field(gt=0, le=1e12, allow_inf_nan=False)
    open: float = Field(gt=0, le=1e12, allow_inf_nan=False)
    high: float = Field(gt=0, le=1e12, allow_inf_nan=False)
    low: float = Field(gt=0, le=1e12, allow_inf_nan=False)
    close: float = Field(gt=0, le=1e12, allow_inf_nan=False)
    volume: int = Field(ge=0, strict=True)
    open_interest: int = Field(ge=0, strict=True)
    currency: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    source: str = Field(min_length=1)
    observed_at: str
    available_at: str
    ingested_at: str

    @model_validator(mode="after")
    def chronology(self):
        if utc(self.available_at) < utc(self.observed_at):
            raise ValueError("Availability precedes observation")
        if self.trading_date > self.expiry:
            raise ValueError("Trading date exceeds expiry")
        if self.trading_date.isoformat() > self.observed_at[:10]:
            raise ValueError("Trading date is after observation")
        if utc(self.ingested_at) < utc(self.available_at):
            raise ValueError("Ingestion precedes availability")
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise ValueError("Impossible OHLC range")
        return self


def validate_price(row: dict, spec: dict) -> dict:
    result = Price(**row).model_dump(mode="json")
    for key in ("contract_id", "dataset", "symbol", "expiry", "spec_version", "currency", "unit"):
        if result[key] != spec[key]:
            raise ValueError(f"Price does not match specification: {key}")
    if spec["available_at"] > result["available_at"]:
        raise ValueError("Specification was unavailable")
    if not spec["valid_from"] <= result["trading_date"] <= spec["valid_to"]:
        raise ValueError("Stale specification outside validity interval")
    return result


def normalize(price: float, spec: dict) -> float:
    """999-equivalent INR/g comparison convention; never a fill price."""
    if spec["dataset"] == "real" and spec["verification"] != "VERIFIED":
        raise ValueError("UNVERIFIED specification blocks real analytics")
    return price / spec["quote_grams"] * (0.999 / spec["purity"])
