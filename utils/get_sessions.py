import json
import os.path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()
curr_path = os.path.dirname(__file__)
legi_key = os.environ.get('legiscan_key')
Session_List_URL = f"https://api.legiscan.com/?key={legi_key}&op=getSessionList"

def get_sessions_dataframe():
    r = requests.get(Session_List_URL)
    df = pd.DataFrame(r.json()["sessions"])
    df.to_csv(f"./cache/sessions.csv")
    return df
