"""Invented parser inputs; no generated rows are written into real storage."""
import json
import pytest
from backend.public_sources import extract, catalog


def page(expiry="05 Nov, 26", divisor=100):
    data = {"contractDetails": {"symbol": "GOLDM", "priceQuoteUnit": "GRMS"},
            "historicalData": {"priceDivisor": divisor, "priceHistory": [
                {"date": 1792693800000, "expiryDate": expiry, "close": 14045300}]}}
    chunk = "a:" + json.dumps({"data": data}) + "\n"
    return "<script>self.__next_f.push(" + json.dumps([1, chunk]) + ")</script>"


def test_source_divisor_explicit_expiry_and_conservative_availability():
    result = extract(page(), "GOLDM", "2026-10-26T14:00:00Z")
    row = result["rows"][0]
    assert row["price"] == "140453"
    assert row["expiry"] == "2026-11-05"
    assert row["trading_date"] == "2026-10-23"
    assert row["available_at"] == row["observed_at"] == result["retrieved_at"]
    assert row["quotation_grams"] is None
    assert not result["model_ready"]
    assert result["collector"] == "python-urllib"


def test_no_inferred_expiry_or_divisor():
    with pytest.raises(ValueError):
        extract(page(expiry="November 2026"), "GOLDM", "2026-10-26T14:00:00Z")
    with pytest.raises(ValueError):
        extract(page(divisor=0), "GOLDM", "2026-10-26T14:00:00Z")
    with pytest.raises(ValueError):
        extract(page(), "GOLDTEN", "2026-10-26T14:00:00Z")


def test_archive_does_not_expose_future_collection(tmp_path):
    result = extract(page(), "GOLDM", "2026-10-26T14:00:00Z")
    folder = tmp_path / "GOLDM"
    folder.mkdir()
    (folder / "snapshot.json").write_text(json.dumps(result))
    assert not catalog("2026-10-23T18:00:00Z", tmp_path)["sources"]
    assert len(catalog("2026-10-26T14:00:00Z", tmp_path)["sources"]) == 1
