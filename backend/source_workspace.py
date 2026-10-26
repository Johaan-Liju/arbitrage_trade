"""Source quote browsing without granting unverified records model eligibility."""
from .public_sources import catalog


def snapshot(as_of, root):
    contracts, histories = [], {}
    for source in catalog(as_of, root)["sources"]:
        version = source["spec_id"].split(":", 1)[1]
        for expiry in sorted({r["expiry"] for r in source["rows"]}):
            identifier = f"{source['symbol']}:{expiry}:{version}"
            spec = dict(contract_id=identifier, dataset="real", symbol=source["symbol"], expiry=expiry,
                spec_id=source["spec_id"], spec_version=version, currency="INR", unit="SOURCE_QUOTE",
                quote_grams=None, lot_grams=None, purity=None, quotation_grams=None,
                lot_size_grams=None, quote_purity_per_mille=None, valid_from=None, valid_to=None,
                delivery_locations=[], delivery_location="Unverified", delivery_basis=None,
                delivery_restrictions=None, settlement_method=None, settlement_terms=None,
                expiry_restrictions=None, verification="UNVERIFIED", safe_exit_date=None,
                tender_start=None, delivery_end=None, available_at=source["retrieved_at"],
                source=source["source_url"], listing_source=source["source_url"],
                description="Collected broker quotes; source terms are not verified for model use",
                normalization_status="BLOCKED", normalization_reason="Source quotes are available. Normalization and model signals require verified contract terms.")
            contracts.append(spec)
            rows = []
            for raw in source["rows"]:
                if raw["expiry"] != expiry or max(raw["observed_at"], raw["available_at"]) > as_of or raw["trading_date"] > as_of[:10]:
                    continue
                rows.append({**raw, "instrument": raw["symbol"], "contract_id": identifier,
                    "spec_version": version, "source": raw["source_url"], "unit": "SOURCE_QUOTE",
                    "price": float(raw["price"]), "quoted_price_decimal": raw["price"],
                    "normalized_999_inr_per_gram": None, "normalized_999_per_g": None,
                    "normalized_available_at": None, "volume": None, "open_interest": None})
            histories[identifier] = sorted(rows, key=lambda r: r["trading_date"])
    return {"dataset": "real", "as_of": as_of, "contracts": contracts,
            "histories": histories, "issues": [], "data_mode": "source_quotes", "model_ready": False}
