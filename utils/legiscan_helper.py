def get_sponsors(list):
    sponsors = ""
    for s in list:
        if sponsors != "":
            sponsors = sponsors + ", "
        sponsors = sponsors + s["name"]
    return sponsors

def get_texts(list):
    texts = ""
    for t in list:
        if texts != "":
            texts = texts + ", "
        texts = texts + t["state_link"]
    return texts

def get_calendar(list):
    calendar = ""
    for event in list:
        if calendar != "":
            calendar = calendar + ", "
        calendar = calendar + event["type"] + " " + event["date"] + " " + event["time"] + " " + event["location"]
    return calendar

def get_history(list):
    history = ""
    for event in list:
        if history != "":
            history = history + ", "
        history = history + event["chamber"] + " " + event["date"] + " " + event["action"]
    return history
