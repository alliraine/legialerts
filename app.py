import csv
import logging
import os
import threading

from flask import Flask, jsonify, request

import main as legi_main
from utils.config import ALLOW_ANONYMOUS_API

app = Flask(__name__)
logger = logging.getLogger(__name__)
_run_lock = threading.Lock()
AUTH_TOKEN = os.environ.get("API_AUTH_TOKEN")
WORKSHEETS = [
    "Anti-LGBTQ Bills",
    "Pro-LGBTQ Bills",
    "Rollover Anti-LGBTQ Bills",
    "Rollover Pro-LGBTQ Bills",
]


def _is_authorized():
    provided = request.headers.get("Authorization", "")
    if not AUTH_TOKEN:
        return ALLOW_ANONYMOUS_API
    return provided == f"Bearer {AUTH_TOKEN}"


def _auth_required(allow_health=False):
    if allow_health:
        return None
    if _is_authorized():
        return None
    return jsonify({"status": "unauthorized"}), 401


def _sheet_stats(path):
    stats = {
        "total_rows": 0,
        "by_state": {},
        "by_status": {},
        "unknown_status": 0,
        "missing_url": 0,
    }
    if not os.path.exists(path):
        return stats
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            state = (row.get("State") or "").strip()
            if not state:
                continue
            stats["total_rows"] += 1
            stats["by_state"][state] = stats["by_state"].get(state, 0) + 1
            status = (row.get("Status") or "").strip()
            if not status or status.lower() == "unknown":
                stats["unknown_status"] += 1
            else:
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            url = (row.get("URL") or "").strip()
            if not url or url.lower() == "unknown":
                stats["missing_url"] += 1
    return stats


@app.get("/run")
def run_once():
    auth = _auth_required()
    if auth:
        return auth
    if not _run_lock.acquire(blocking=False):
        return jsonify({"status": "busy"}), 409
    try:
        logger.info("Triggered /run")
        legi_main.main()
        return jsonify({"status": "ok"}), 200
    finally:
        _run_lock.release()


@app.get("/health")
def health():
    auth = _auth_required(allow_health=True)
    if auth:
        return auth
    return jsonify({"status": "ok"}), 200


@app.get("/stats")
def stats():
    auth = _auth_required()
    if auth:
        return auth
    results = {
        "run": legi_main.get_stats(),
        "worksheets": {},
    }
    years = getattr(legi_main, "years", [])
    for year in years:
        year_stats = {}
        for worksheet in WORKSHEETS:
            cache_dir = getattr(legi_main, "CACHE_DIR", os.path.join(legi_main.curr_path, "cache"))
            cache_path = os.path.join(cache_dir, f"gsheet-{worksheet}-{year}.csv")
            year_stats[worksheet] = _sheet_stats(cache_path)
        results["worksheets"][str(year)] = year_stats
    return jsonify(results), 200
