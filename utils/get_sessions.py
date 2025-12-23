import json
import os.path
import logging

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
curr_path = os.path.dirname(__file__)
legi_key = os.environ.get('legiscan_key')
Session_List_URL = f"https://api.legiscan.com/?key={legi_key}&op=getSessionList"
logger = logging.getLogger(__name__)

def get_sessions_dataframe(session=None, request_fn=None):
    session = session or requests
    if request_fn is None:
        request_fn = session.get
    r = request_fn(Session_List_URL)
    try:
        data = r.json()
    except Exception:
        logger.exception("Failed to parse LegiScan session list JSON")
        logger.error("Session list response text: %s", r.text)
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
    df.to_csv(f"./cache/sessions.csv")
    return df
