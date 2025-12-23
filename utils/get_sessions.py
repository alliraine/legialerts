import logging
import os.path

import pandas as pd
import requests
from dotenv import load_dotenv

from utils.config import CACHE_DIR, REQUEST_TIMEOUT

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
legi_key = os.environ.get('legiscan_key')
Session_List_URL = f"https://api.legiscan.com/?key={legi_key}&op=getSessionList"
logger = logging.getLogger(__name__)

def get_sessions_dataframe(session=None, request_fn=None):
    session = session or requests.Session()
    if request_fn is None:
        request_fn = lambda url: session.get(url, timeout=REQUEST_TIMEOUT)
    r = request_fn(Session_List_URL)
    try:
        data = r.json()
    except Exception:
        logger.exception("Failed to parse LegiScan session list JSON")
        logger.error("Session list response text: %s", getattr(r, "text", ""))
        return pd.DataFrame()
    status = data.get("status")
    if status and status != "OK":
        logger.error("LegiScan error for getSessionList: %s", data.get("alert", {}).get("message", data))
        return pd.DataFrame()
    sessions = data.get("sessions")
    if sessions is None:
        logger.error("LegiScan session list missing 'sessions' key. Response: %s", data)
        return pd.DataFrame()
    df = pd.DataFrame(sessions)
    os.makedirs(CACHE_DIR, exist_ok=True)
    df.to_csv(os.path.join(CACHE_DIR, "sessions.csv"))
    return df
