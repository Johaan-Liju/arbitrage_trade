"""Loopback-only test API with an isolated notification store: serve-alert-test-api.py PORT NOTIFICATION_ROOT."""
from pathlib import Path
import sys

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.main import create_app  # noqa: E402

port, root = int(sys.argv[1]), Path(sys.argv[2]).resolve()
uvicorn.run(create_app(alert_root=root), host="127.0.0.1", port=port, log_level="warning")
