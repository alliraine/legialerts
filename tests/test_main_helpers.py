import pandas as pd

import main


def test_row_missing_details_detects_blanks():
    row = {"Sponsors": None, "Calendar": "", "History": "Unknown", "PDF": "Unknown", "Bill ID": ""}
    assert main.row_missing_details(row) is True


def test_row_missing_details_detects_complete_row():
    row = {"Sponsors": "A", "Calendar": "B", "History": "C", "PDF": "D", "Bill ID": "123"}
    assert main.row_missing_details(row) is False


def test_build_master_index_handles_multiple_states():
    df = pd.DataFrame(
        [
            {"number": "HB1", "change_hash": "a", "last_action": "X", "last_action_date": "2024-01-01", "title": "t1", "url": "u1", "bill_id": 1},
            {"number": "HB2", "change_hash": "b", "last_action": "Y", "last_action_date": "2024-01-02", "title": "t2", "url": "u2", "bill_id": 2},
        ]
    )
    index = main.build_master_index({"Example": df})
    assert index["Example"]["HB1"]["bill_id"] == 1
    assert index["Example"]["HB2"]["change_hash"] == "b"


def test_worksheet_legiscan_digest_changes_on_change_hash():
    gsheet = pd.DataFrame([{"State": "X", "Number": "HB1", "Change Hash": "hash1"}])
    master_index = {"X": {"HB1": {"change_hash": "hash1"}}}
    digest1 = main.worksheet_legiscan_digest(gsheet, master_index)
    master_index["X"]["HB1"]["change_hash"] = "hash2"
    digest2 = main.worksheet_legiscan_digest(gsheet, master_index)
    assert digest1 != digest2
