from datetime import date, datetime, timezone
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_AS_OF = "2026-10-23T18:00:00Z"
DISCLAIMER = "SYNTHETIC research only. Invented specifications, prices and liquidity. Fees, taxes, slippage, execution and settlement uncertainty are not modeled. No trade execution or guaranteed arbitrage."


def utc(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise ValueError("Use an exact UTC timestamp: YYYY-MM-DDTHH:MM:SSZ")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Spec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    contract_id: str = Field(min_length=1)
    dataset: Literal["synthetic"] = "synthetic"
    symbol: Literal["GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL"]
    expiry: date
    spec_version: str = Field(min_length=1)
    currency: Literal["INR"] = "INR"
    unit: Literal["quote"] = "quote"
    quote_grams: float = Field(gt=0, allow_inf_nan=False)
    available_at: str
    source: str = "GoldLens deterministic generator v1"
    description: str = "Invented demo specification; not verified exchange terms"

    @model_validator(mode="after")
    def validate_time(self):
        utc(self.available_at)
        return self


class Price(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_id: str
    dataset: Literal["synthetic"]
    symbol: str = Field(min_length=1)
    expiry: date
    spec_version: str = Field(min_length=1)
    trading_date: date
    price: float = Field(gt=0, allow_inf_nan=False)
    volume: int = Field(ge=0, strict=True)
    open_interest: int = Field(ge=0, strict=True)
    currency: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    source: str = Field(min_length=1)
    observed_at: str
    available_at: str

    @model_validator(mode="after")
    def chronology(self):
        if utc(self.available_at) < utc(self.observed_at):
            raise ValueError("Availability precedes observation")
        if self.trading_date > self.expiry:
            raise ValueError("Trading date exceeds expiry")
        if self.trading_date.isoformat() > self.observed_at[:10]:
            raise ValueError("Trading date is after observation")
        return self


def validate_price(row: dict, spec: dict) -> dict:
    result = Price(**row).model_dump(mode="json")
    for key in ("contract_id", "dataset", "symbol", "expiry", "spec_version", "currency", "unit"):
        if result[key] != spec[key]:
            raise ValueError(f"Price does not match specification: {key}")
    if spec["available_at"] > result["available_at"]:
        raise ValueError("Specification was unavailable")
    return result
