def bad_bills(year):
    global world_report, team_report
    print("starting bad bills..")
    all_lists = get_main_lists(year)
    twitter = tweepy.Client(
        consumer_key=os.environ.get('twitter_consumer_key'),
        consumer_secret=os.environ.get('twitter_consumer_secret'),
        access_token=os.environ.get('twitter_access_token'),
        access_token_secret=os.environ.get('twitter_access_token_secret')
    )

    #open google sheets api account
    gc = gspread.service_account_from_dict(os.environ.get('gsuite_service_account'))

    #open worksheet
    wks = gc.open_by_key(os.environ.get('gsheet_key_' + str(year))).sheet1
    expected_headers = wks.row_values(1)

    #loads worksheet into dataframe
    gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))

    #gets previous sheet from file
    if os.path.exists(f"{curr_path}/cache/gsheet-{year}.csv"):
        prev_gsheet = pd.read_csv(f"{curr_path}/cache/gsheet-{year}.csv")
    else:
        prev_gsheet = gsheet

    for index, row in gsheet.iterrows():
        try:
            r_state = row["State"].strip()
            r_bnum = row["Number"]
            r_btype = row["Bill Type"]
            if not all_lists[r_state].empty:
                lscan = all_lists[r_state].loc[all_lists[r_state]["number"] == r_bnum.strip()]
                if not lscan.empty:
                    r_la = lscan.iloc[0]["last_action"]
                    r_title = lscan.iloc[0]["title"]
                    r_link = lscan.iloc[0]["url"]
                    bill_id = lscan.iloc[0]["bill_id"]
                    prev = prev_gsheet.loc[(prev_gsheet["State"] == row["State"]) & (prev_gsheet["Number"] == row["Number"])]

                    #checks if the bill is recently added. If not then alert new bill
                    if prev.empty or gsheet.at[index, 'Change Hash'] == "":
                        print("New Bill Found")
                        t = f"🚨ALERT NEW BILL 🚨\n------------------------\n📜Bill: {r_state} {r_bnum.strip()} \n📑Title: {r_title}\n🏷️Bill Type: {r_btype}\n🚦Adult State Risk: {ADULT_RISK[r_state]} \n🚦Youth State Risk: {YOUTH_RISK[r_state]}\n🏛Status: {r_la} \n🔗Bill Text:{r_link} "
                        send_tweet(t, twitter)
                        team_report = team_report + "\n" + t
                        world_report = world_report + "\n" + t

                        r = requests.get(Bill_URL + str(bill_id))
                        content = r.json()["bill"]

                        gsheet.at[index, 'Sponsors'] = get_sponsors(content["sponsors"])
                        gsheet.at[index, 'Calendar'] = get_calendar(content["calendar"])
                        gsheet.at[index, 'History'] = get_history(content["history"])
                        gsheet.at[index, 'Bill ID'] = str(bill_id)
                        gsheet.at[index, "PDF"] = get_texts(content["texts"])


                    #if not new check change hash to see if the bill has changed. If it has trigger an alert
                    elif lscan.iloc[0]["change_hash"] != row["Change Hash"] and (lscan.iloc[0]["last_action"] != row["Status"] or lscan.iloc[0]["last_action_date"] != row["Date"]):
                        print("Bill Change Found")
                        t = f"🏛 Status Change 🏛\n📜Bill: {r_state} {r_bnum.strip()} \n📑Title: {r_title}\n🏷️Bill Type: {r_btype}\n🚦Adult State Risk: {ADULT_RISK[r_state]} \n🚦Youth State Risk: {YOUTH_RISK[r_state]}\n🏛Status: {r_la} \n🔗Bill Text:{r_link}"
                        send_tweet(t, twitter)
                        team_report = team_report + "\n" + t
                        world_report = world_report + "\n" + t
                        r = requests.get(Bill_URL + str(bill_id))
                        content = r.json()["bill"]

                        gsheet.at[index, 'Sponsors'] = get_sponsors(content["sponsors"])
                        gsheet.at[index, 'Calendar'] = get_calendar(content["calendar"])
                        gsheet.at[index, 'History'] = get_history(content["history"])
                        gsheet.at[index, 'Bill ID'] = str(bill_id)
                        gsheet.at[index, "PDF"] = get_texts(content["texts"])

                    hyperlink = f"=HYPERLINK(\"{r_link}\",\"{r_bnum}\")"
                    gsheet.at[index, 'Number'] = hyperlink
                    gsheet.at[index, 'Status'] = lscan.iloc[0]["last_action"]
                    if lscan.iloc[0]["last_action_date"] != None and lscan.iloc[0]["last_action_date"] != '':
                        gsheet.at[index, 'Date'] = lscan.iloc[0]["last_action_date"]
                    else:
                        gsheet.at[index, 'Date'] = "Unknown"
                    gsheet.at[index, 'Summary'] = lscan.iloc[0]["title"]
                    gsheet.at[index, 'Change Hash'] = lscan.iloc[0]["change_hash"]
                    gsheet.at[index, 'URL'] = f"=HYPERLINK(\"{r_link}\",\"{r_link}\")"


                else:
                    gsheet.at[index, 'Date'] = "Unknown"
                gsheet.at[index, 'Youth State Risk'] = YOUTH_RISK[r_state]
                gsheet.at[index, 'Adult State Risk'] = ADULT_RISK[r_state]
            else:
                gsheet.at[index, 'Date'] = "Unknown"
                gsheet.at[index, 'Youth State Risk'] = YOUTH_RISK[r_state]
                gsheet.at[index, 'Adult State Risk'] = ADULT_RISK[r_state]
        except Exception as e:
            print("Ran into error")
            dev_report = dev_report + "\n" + str(e)
    gsheet = gsheet.fillna('Unknown')

    #updates the entire google sheet from data frame
    wks.update([gsheet.columns.values.tolist()] + gsheet.values.tolist(), value_input_option='USER_ENTERED')

    #formats google sheet
    wks.format("A2:K400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend"}})
    wks.format("G2:G400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "horizontalAlignment": "CENTER"})
    wks.format("E2:E400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "numberFormat": {"type": "DATE"}, "horizontalAlignment": "CENTER"})

    #does one more pull of the updated sheet then saves it as the previous sheet for next run
    expected_headers = wks.row_values(1)
    gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))
    gsheet.to_csv(f"{curr_path}/cache/gsheet-{year}.csv")

def good_bills(year):
    global team_report, world_report
    print("starting good bills...")
    all_lists = get_main_lists(year)
    twitter = tweepy.Client(
        consumer_key=os.environ.get('twitter_consumer_key'),
        consumer_secret=os.environ.get('twitter_consumer_secret'),
        access_token=os.environ.get('twitter_access_token'),
        access_token_secret=os.environ.get('twitter_access_token_secret')
    )

    #open google sheets api account
    gc = gspread.service_account_from_dict(os.environ.get('gsuite_service_account'))

    #open worksheet
    wks = gc.open_by_key(os.environ.get('gsheet_key_' + str(year))).worksheet("Pro-LGBTQ Bills")
    expected_headers = wks.row_values(1)

    #loads worksheet into dataframe
    gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))

    #gets previous sheet from file
    if os.path.exists(f"{curr_path}/cache/gsheet_good-{year}.csv"):
        prev_gsheet = pd.read_csv(f"{curr_path}/cache/gsheet_good-{year}.csv")
    else:
        prev_gsheet = gsheet

    for index, row in gsheet.iterrows():
        try:
            r_state = row["State"].strip()
            r_bnum = row["Number"]
            r_btype = row["Bill Type"]
            if not all_lists[r_state].empty and r_state in all_lists.keys():
                lscan = all_lists[r_state].loc[all_lists[r_state]["number"] == r_bnum.strip()]
                if not lscan.empty:
                    r_la = lscan.iloc[0]["last_action"]
                    r_title = lscan.iloc[0]["title"]
                    r_link = lscan.iloc[0]["url"]
                    bill_id = lscan.iloc[0]["bill_id"]
                    prev = prev_gsheet.loc[(prev_gsheet["State"] == row["State"]) & (prev_gsheet["Number"] == row["Number"])]

                    #checks if the bill is recently added. If not then alert new bill
                    if prev.empty or gsheet.at[index, 'Change Hash'] == "":
                        print("New Bill Found")
                        t = f"🌈NEW GOOD BILL 🏳️‍⚧️\n------------------------\n📜Bill: {r_state} {r_bnum.strip()} \n📑Title: {r_title}\n🏷️Bill Type: {r_btype}\n🚦Adult State Risk: {ADULT_RISK[r_state]} \n🚦Youth State Risk: {YOUTH_RISK[r_state]}\n🏛Status: {r_la} \n🔗Bill Text:{r_link} "
                        send_tweet(t, twitter)
                        team_report = team_report + "\n" + t
                        world_report = world_report + "\n" + t
                        r = requests.get(Bill_URL + str(bill_id))
                        content = r.json()["bill"]

                        gsheet.at[index, 'Sponsors'] = get_sponsors(content["sponsors"])
                        gsheet.at[index, 'Calendar'] = get_calendar(content["calendar"])
                        gsheet.at[index, 'Bill ID'] = str(bill_id)
                        gsheet.at[index, "PDF"] = get_texts(content["texts"])

                    #if not new check change hash to see if the bill has changed. If it has trigger an alert
                    elif lscan.iloc[0]["change_hash"] != row["Change Hash"] and (lscan.iloc[0]["last_action"] != row["Status"] or lscan.iloc[0]["last_action_date"] != row["Date"]):
                        print("Bill Change Found")
                        t = f"🌈Status Change 🏛\n📜Bill: {r_state} {r_bnum.strip()} \n📑Title: {r_title}\n🏷️Bill Type: {r_btype}\n🚦Adult State Risk: {ADULT_RISK[r_state]} \n🚦Youth State Risk: {YOUTH_RISK[r_state]}\n🏛Status: {r_la} \n🔗Bill Text:{r_link}"
                        send_tweet(t, twitter)
                        team_report = team_report + "\n" + t
                        world_report = world_report + "\n" + t
                        r = requests.get(Bill_URL + str(bill_id))
                        content = r.json()["bill"]

                        gsheet.at[index, 'Sponsors'] = get_sponsors(content["sponsors"])
                        gsheet.at[index, 'Calendar'] = get_calendar(content["calendar"])
                        gsheet.at[index, 'Bill ID'] = str(bill_id)
                        gsheet.at[index, "PDF"] = get_texts(content["texts"])

                    hyperlink = f"=HYPERLINK(\"{r_link}\",\"{r_bnum}\")"
                    gsheet.at[index, 'Number'] = hyperlink
                    gsheet.at[index, 'Status'] = lscan.iloc[0]["last_action"]
                    if lscan.iloc[0]["last_action_date"] != None and lscan.iloc[0]["last_action_date"] != '':
                        gsheet.at[index, 'Date'] = lscan.iloc[0]["last_action_date"]
                    else:
                        gsheet.at[index, 'Date'] = "Unknown"
                    gsheet.at[index, 'Summary'] = lscan.iloc[0]["title"]
                    gsheet.at[index, 'Change Hash'] = lscan.iloc[0]["change_hash"]
                    gsheet.at[index, 'URL'] = f"=HYPERLINK(\"{r_link}\",\"{r_link}\")"


                else:
                    gsheet.at[index, 'Date'] = "Unknown"
                gsheet.at[index, 'Youth State Risk'] = YOUTH_RISK[r_state]
                gsheet.at[index, 'Adult State Risk'] = ADULT_RISK[r_state]
            else:
                gsheet.at[index, 'Date'] = "Unknown"
                gsheet.at[index, 'Youth State Risk'] = YOUTH_RISK[r_state]
                gsheet.at[index, 'Adult State Risk'] = ADULT_RISK[r_state]
        except Exception as e:
            print("Ran into error")
            dev_report = dev_report + "\n" + str(e)
    gsheet = gsheet.fillna('Unknown')

    #updates the entire google sheet from data frame
    wks.update([gsheet.columns.values.tolist()] + gsheet.values.tolist(), value_input_option='USER_ENTERED')

    #formats google sheet
    wks.format("A2:K400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend"}})
    wks.format("G2:G400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "horizontalAlignment": "CENTER"})
    wks.format("E2:E400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "numberFormat": {"type": "DATE"}, "horizontalAlignment": "CENTER"})

    #does one more pull of the updated sheet then saves it as the previous sheet for next run
    expected_headers = wks.row_values(1)
    gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))
    gsheet.to_csv(f"{curr_path}/cache/gsheet_good-{year}.csv")

def rollover(prev_year, year):
    global dev_report
    print("starting roll over bills..")
    all_lists = get_main_lists(prev_year)
    twitter = tweepy.Client(
        consumer_key=os.environ.get('twitter_consumer_key'),
        consumer_secret=os.environ.get('twitter_consumer_secret'),
        access_token=os.environ.get('twitter_access_token'),
        access_token_secret=os.environ.get('twitter_access_token_secret')
    )

    #open google sheets api account
    gc = gspread.service_account_from_dict(os.environ.get('gsuite_service_account'))

    #open worksheet
    wks = gc.open_by_key(os.environ.get('gsheet_key_' + str(year))).worksheet("2023 Rollover Anti-LGBTQ Bills")
    expected_headers = wks.row_values(1)

    #loads worksheet into dataframe
    gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))

    #gets previous sheet from file
    if os.path.exists(f"{curr_path}/cache/gsheet-rollover-{year}.csv"):
        prev_gsheet = pd.read_csv(f"{curr_path}/cache/gsheet-rollover-{year}.csv")
    else:
        prev_gsheet = gsheet

    for index, row in gsheet.iterrows():
        try:
            r_state = row["State"].strip()
            r_bnum = row["Number"]
            r_btype = row["Bill Type"]
            if not all_lists[r_state].empty:
                lscan = all_lists[r_state].loc[all_lists[r_state]["number"] == r_bnum.strip()]
                if not lscan.empty:
                    r_la = lscan.iloc[0]["last_action"]
                    r_title = lscan.iloc[0]["title"]
                    r_link = lscan.iloc[0]["url"]
                    bill_id = lscan.iloc[0]["bill_id"]
                    prev = prev_gsheet.loc[(prev_gsheet["State"] == row["State"]) & (prev_gsheet["Number"] == row["Number"])]

                    #checks if the bill is recently added. If not then alert new bill
                    if prev.empty or gsheet.at[index, 'Change Hash'] == "":
                        print("New Bill Found")
                        t = f"🚨ALERT NEW BILL 🚨\n------------------------\n📜Bill: {r_state} {r_bnum.strip()} \n📑Title: {r_title}\n🏷️Bill Type: {r_btype}\n🚦Adult State Risk: {ADULT_RISK[r_state]} \n🚦Youth State Risk: {YOUTH_RISK[r_state]}\n🏛Status: {r_la} \n🔗Bill Text:{r_link} "
                        send_tweet(t, twitter)
                        team_report = team_report + "\n" + t
                        world_report = world_report + "\n" + t
                        r = requests.get(Bill_URL + str(bill_id))
                        content = r.json()["bill"]

                        gsheet.at[index, 'Sponsors'] = get_sponsors(content["sponsors"])
                        gsheet.at[index, 'Calendar'] = get_calendar(content["calendar"])
                        gsheet.at[index, 'History'] = get_history(content["history"])
                        gsheet.at[index, 'Bill ID'] = str(bill_id)
                        gsheet.at[index, "PDF"] = get_texts(content["texts"])


                    #if not new check change hash to see if the bill has changed. If it has trigger an alert
                    elif lscan.iloc[0]["change_hash"] != row["Change Hash"] and (lscan.iloc[0]["last_action"] != row["Status"] or lscan.iloc[0]["last_action_date"] != row["Date"]):
                        print("Bill Change Found")
                        t = f"🏛 Status Change 🏛\n📜Bill: {r_state} {r_bnum.strip()} \n📑Title: {r_title}\n🏷️Bill Type: {r_btype}\n🚦Adult State Risk: {ADULT_RISK[r_state]} \n🚦Youth State Risk: {YOUTH_RISK[r_state]}\n🏛Status: {r_la} \n🔗Bill Text:{r_link}"
                        send_tweet(t, twitter)
                        team_report = team_report + "\n" + t
                        world_report = world_report + "\n" + t
                        r = requests.get(Bill_URL + str(bill_id))
                        content = r.json()["bill"]

                        gsheet.at[index, 'Sponsors'] = get_sponsors(content["sponsors"])
                        gsheet.at[index, 'Calendar'] = get_calendar(content["calendar"])
                        gsheet.at[index, 'History'] = get_history(content["history"])
                        gsheet.at[index, 'Bill ID'] = str(bill_id)
                        gsheet.at[index, "PDF"] = get_texts(content["texts"])

                    hyperlink = f"=HYPERLINK(\"{r_link}\",\"{r_bnum}\")"
                    gsheet.at[index, 'Number'] = hyperlink
                    gsheet.at[index, 'Status'] = lscan.iloc[0]["last_action"]
                    if lscan.iloc[0]["last_action_date"] != None and lscan.iloc[0]["last_action_date"] != '':
                        gsheet.at[index, 'Date'] = lscan.iloc[0]["last_action_date"]
                    else:
                        gsheet.at[index, 'Date'] = "Unknown"
                    gsheet.at[index, 'Summary'] = lscan.iloc[0]["title"]
                    gsheet.at[index, 'Change Hash'] = lscan.iloc[0]["change_hash"]
                    gsheet.at[index, 'URL'] = f"=HYPERLINK(\"{r_link}\",\"{r_link}\")"


                else:
                    gsheet.at[index, 'Date'] = "Unknown"
                gsheet.at[index, 'Youth State Risk'] = YOUTH_RISK[r_state]
                gsheet.at[index, 'Adult State Risk'] = ADULT_RISK[r_state]
            else:
                gsheet.at[index, 'Date'] = "Unknown"
                gsheet.at[index, 'Youth State Risk'] = YOUTH_RISK[r_state]
                gsheet.at[index, 'Adult State Risk'] = ADULT_RISK[r_state]
        except Exception as e:
            print(f"Ran into error: {e}")
            dev_report = dev_report + "\n" + str(e)
    gsheet = gsheet.fillna('Unknown')

    #updates the entire google sheet from data frame
    wks.update([gsheet.columns.values.tolist()] + gsheet.values.tolist(), value_input_option='USER_ENTERED')

    #formats google sheet
    wks.format("A2:K400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend"}})
    wks.format("G2:G400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "horizontalAlignment": "CENTER"})
    wks.format("E2:E400", {'textFormat': {"fontSize": 12, "fontFamily": "Lexend", }, "numberFormat": {"type": "DATE"}, "horizontalAlignment": "CENTER"})

    #does one more pull of the updated sheet then saves it as the previous sheet for next run
    expected_headers = wks.row_values(1)
    gsheet = pd.DataFrame(wks.get_all_records(expected_headers=expected_headers))
    gsheet.to_csv(f"{curr_path}/cache/gsheet-rollover-{year}.csv")