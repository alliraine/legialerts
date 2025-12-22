import json
import os.path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
curr_path = os.path.dirname(__file__)
legi_key = os.environ.get('legiscan_key')
Session_List_URL = f"https://api.legiscan.com/?key={legi_key}&op=getSessionList"

def get_sessions_dataframe(session=None, request_fn=None):
    session = session or requests
    if request_fn is None:
        request_fn = session.get
    r = request_fn(Session_List_URL)
    df = pd.DataFrame(r.json()["sessions"])
    df.to_csv(f"./cache/sessions.csv")
    return df
