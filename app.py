import logging
import threading

from flask import Flask, jsonify

import main as legi_main

app = Flask(__name__)
logger = logging.getLogger(__name__)
_run_lock = threading.Lock()


@app.get("/run")
def run_once():
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
    return jsonify({"status": "ok"}), 200
