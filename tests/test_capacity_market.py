from datetime import date

from subsidy_engine_uk.schemes import capacity_market as cm

RECORDS = [
    {
        "_id": 1, "Delivery_Year": "2016/2017", "Calendar_Year": "2016",
        "Calendar_Quarter": "Qtr 4", "Calendar_Month": "December",
        "Auction_Identifier": "TR-2016",
        "Auction_Acquired_Capacity_Obligation_MW": "640.966",
        "Capacity_Payment_GBP": "1612301.64",
        "Capacity_Payment_Suspension_Flag": "Not Suspended",
    },
    {
        "_id": 2, "Delivery_Year": "2016/2017", "Calendar_Year": "2016",
        "Calendar_Quarter": "Qtr 4", "Calendar_Month": "November",
        "Auction_Identifier": "TR-2016",
        "Auction_Acquired_Capacity_Obligation_MW": "727.689",
        "Capacity_Payment_GBP": "1742875.87",
        "Capacity_Payment_Suspension_Flag": "Not Suspended",
    },
]


def test_parse_monthly_payments():
    df = cm.parse_payments(RECORDS)
    assert df.columns == ["date", "auction", "payment_gbp"]
    rows = df.sort("date").to_dicts()
    assert rows[0] == {"date": date(2016, 11, 1), "auction": "TR-2016",
                       "payment_gbp": 1742875.87}
    assert rows[1]["date"] == date(2016, 12, 1)


def test_parse_skips_blank_payments():
    record = dict(RECORDS[0], Capacity_Payment_GBP="")
    assert cm.parse_payments([record]).height == 0


def test_parse_skips_unknown_month_names():
    record = dict(RECORDS[0], Calendar_Month="Mystery")
    assert cm.parse_payments([record]).height == 0
