import json
import logging
import os
import time
import uuid
import hashlib
from typing import Any, Dict, List, Optional

from utils.config import CACHE_DIR

logger = logging.getLogger(__name__)

QUEUE_FILE = os.path.join(CACHE_DIR, "change_queue.json")
RSS_FILE = os.path.join(CACHE_DIR, "changes.rss")


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def load_queue() -> List[Dict[str, Any]]:
    try:
        with open(QUEUE_FILE, "r") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return []
    except Exception:
        logger.exception("Unable to read change queue from %s", QUEUE_FILE)
        return []


def save_queue(queue: List[Dict[str, Any]]) -> None:
    _ensure_dir(QUEUE_FILE)
    try:
        with open(QUEUE_FILE, "w") as handle:
            json.dump(queue, handle, indent=2)
    except Exception:
        logger.exception("Unable to write change queue to %s", QUEUE_FILE)


def append_changes(changes: List[Dict[str, Any]]) -> int:
    if not changes:
        return 0
    queue = load_queue()
    fingerprints = {c.get("fingerprint") for c in queue}
    added = 0
    for change in changes:
        fp = change.get("fingerprint")
        if fp in fingerprints:
            continue
        queue.append(change)
        fingerprints.add(fp)
        added += 1
    save_queue(queue)
    return added


def get_pending_changes() -> List[Dict[str, Any]]:
    return [c for c in load_queue() if not c.get("processed_at")]


def mark_changes_processed(change_ids: List[str]) -> None:
    if not change_ids:
        return
    queue = load_queue()
    now = time.time()
    updated = False
    for change in queue:
        if change.get("id") in change_ids and not change.get("processed_at"):
            change["processed_at"] = now
            updated = True
    if updated:
        save_queue(queue)


def _format_rss_date(ts: float) -> str:
    return time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(ts))


def build_rss_feed(changes: List[Dict[str, Any]], base_url: Optional[str] = None, limit: int = 100) -> str:
    items = []
    sorted_changes = sorted(changes, key=lambda c: c.get("created_at", 0), reverse=True)[:limit]
    for change in sorted_changes:
        title = f"{change.get('change_type', 'update').title()}: {change.get('state')} {change.get('bill_number')}"
        link = change.get("url") or (base_url or "").rstrip("/") or "#"
        description_lines = []
        if change.get("title"):
            description_lines.append(change["title"])
        if change.get("status"):
            description_lines.append(f"Status: {change['status']}")
        for f in change.get("changed_fields", []):
            description_lines.append(f"{f.get('field')}: {f.get('old', '')} -> {f.get('new', '')}")
        description = "\n".join(description_lines)
        pub_date = _format_rss_date(change.get("created_at", time.time()))
        guid = change.get("id") or hashlib.sha256(json.dumps(change, sort_keys=True).encode("utf-8")).hexdigest()
        items.append(
            f"<item><title>{_escape_xml(title)}</title>"
            f"<link>{_escape_xml(link)}</link>"
            f"<guid isPermaLink=\"false\">{guid}</guid>"
            f"<pubDate>{pub_date}</pubDate>"
            f"<description>{_escape_xml(description)}</description></item>"
        )
    channel_title = "LegiAlerts Changes"
    channel_link = (base_url or "").rstrip("/") or "#"
    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        f"<title>{_escape_xml(channel_title)}</title>"
        f"<link>{_escape_xml(channel_link)}</link>"
        f"<description>{_escape_xml('Recent tracked bill changes')}</description>"
        + "".join(items) +
        "</channel></rss>"
    )
    return rss


def write_rss_feed(changes: List[Dict[str, Any]], base_url: Optional[str] = None) -> None:
    content = build_rss_feed(changes, base_url=base_url)
    _ensure_dir(RSS_FILE)
    try:
        with open(RSS_FILE, "w") as handle:
            handle.write(content)
    except Exception:
        logger.exception("Unable to write RSS feed to %s", RSS_FILE)


def _escape_xml(text: Any) -> str:
    value = "" if text is None else str(text)
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
        .replace("'", "&apos;")
    )

