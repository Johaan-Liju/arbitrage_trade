"""Collect public broker snapshots without promoting unverified terms into research."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1] / "data/real/sources"
SYMBOLS = ("GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL")


def timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.active = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False

    def handle_data(self, data):
        prefix = "self.__next_f.push("
        if self.active and data.startswith(prefix) and data.endswith(")"):
            try:
                value = json.loads(data[len(prefix):-1])
                if len(value) == 2 and value[0] == 1 and isinstance(value[1], str):
                    self.chunks.append(value[1])
            except (ValueError, TypeError):
                pass


def extract(html, symbol, retrieved_at):
    parser = Scripts()
    parser.feed(html)
    candidates = []

    def walk(node):
        if isinstance(node, dict):
            if "contractDetails" in node and "historicalData" in node:
                candidates.append(node)
            else:
                for value in node.values():
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for line in "".join(parser.chunks).splitlines():
        _, _, raw = line.partition(":")
        try:
            walk(json.loads(raw))
        except ValueError:
            continue
    candidates = [c for c in candidates if c["contractDetails"].get("symbol") == symbol]
    if len(candidates) != 1:
        raise ValueError("Source schema changed or exact instrument is unavailable; no substitute data")
    data = candidates[0]
    history = data["historicalData"]
    divisor = Decimal(str(history["priceDivisor"]))
    if not divisor.is_finite() or divisor <= 0:
        raise ValueError("Invalid explicit source price divisor")
    digest = hashlib.sha256(json.dumps(data["contractDetails"], sort_keys=True).encode()).hexdigest()
    spec_id = f"{symbol}:upstox-unverified:{digest}"
    url = f"https://upstox.com/commodity-market-trading/mcx-{symbol.lower()}-price/"
    rows = []
    for item in history["priceHistory"]:
        # Dates are explicit in the source; historical daily bars have no proven publication time.
        expiry = datetime.strptime(item["expiryDate"], "%d %b, %y").date().isoformat()
        from datetime import timedelta
        day = datetime.fromtimestamp(item["date"] / 1000, timezone(timedelta(hours=5, minutes=30))).date().isoformat()
        close = Decimal(str(item["close"])) / divisor
        if not close.is_finite() or close <= 0 or day > expiry:
            raise ValueError("Invalid source price/date")
        rows.append({"dataset": "real", "symbol": symbol, "expiry": expiry, "trading_date": day,
            "spec_id": spec_id, "price": str(close), "currency": "INR",
            "unit": data["contractDetails"]["priceQuoteUnit"], "quotation_grams": None,
            "source_url": url, "observed_at": retrieved_at, "available_at": retrieved_at,
            "historical_publication_time": None, "verification_status": "UNVERIFIED"})
    if not rows:
        raise ValueError("No historical observations in source response")
    return {"dataset": "real", "collector": "python-urllib", "symbol": symbol,
        "retrieved_at": retrieved_at, "source_url": url, "spec_id": spec_id,
        "specification": data["contractDetails"], "verification_status": "UNVERIFIED",
        "model_ready": False, "rows": rows,
        "blockers": ["Official versioned specification, exact listing and session calendar are not verified.",
                     "Source GRMS label does not establish quotation weight; normalization is disabled.",
                     "Historical publication times are unknown. Availability begins at collection, never at the historical trading date."]}


def collect(symbol):
    url = f"https://upstox.com/commodity-market-trading/mcx-{symbol.lower()}-price/"
    with urlopen(Request(url, headers={"User-Agent": "GoldLens local research collector"}), timeout=30) as response:
        raw = response.read(10_000_001)
    if len(raw) > 10_000_000:
        raise ValueError("Source response exceeds 10 MB")
    captured = timestamp()
    snapshot = extract(raw.decode("utf-8"), symbol, captured)
    snapshot["html_sha256"] = hashlib.sha256(raw).hexdigest()
    folder = ROOT / symbol
    folder.mkdir(parents=True, exist_ok=True)
    html_path = folder / f"{snapshot['html_sha256']}.html"
    if not html_path.exists():
        html_path.write_bytes(raw)
    encoded = json.dumps(snapshot, indent=2).encode()
    path = folder / f"{hashlib.sha256(encoded).hexdigest()}.json"
    if not path.exists():
        path.write_bytes(encoded)
    return {"symbol": symbol, "rows": len(snapshot["rows"]), "path": str(path), "model_ready": False}


def catalog(as_of, root=ROOT):
    snapshots = []
    for symbol in SYMBOLS:
        versions = []
        for path in (root / symbol).glob("*.json"):
            value = json.loads(path.read_text(encoding="utf-8"))
            if value["retrieved_at"] <= as_of:
                versions.append(value)
        if versions:
            snapshots.append(max(versions, key=lambda v: v["retrieved_at"]))
    return {"dataset": "real", "as_of": as_of, "model_ready": False, "sources": snapshots}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbols", nargs="*", choices=SYMBOLS, default=list(SYMBOLS))
    args = parser.parse_args()
    failures = 0
    for symbol in args.symbols:
        try:
            print(json.dumps(collect(symbol)))
        except Exception as error:
            failures += 1
            print(json.dumps({"symbol": symbol, "status": "collection_failed", "error": str(error)}))
    raise SystemExit(bool(failures))
