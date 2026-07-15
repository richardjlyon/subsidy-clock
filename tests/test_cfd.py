from datetime import date

from subsidy_engine_uk.schemes import cfd

GENERATION_RECORDS = [
    {
        "_id": 1,
        "Settlement_Date": "2024-08-20 00:00:00.0000000",
        "CfD_ID": "AR2-TKN-203",
        "Name_of_CfD_Unit": "Triton Knoll Offshore Wind Farm Phase 2",
        "Technology": "Offshore Wind",
        "Allocation_round": "Allocation Round 2",
        "Reference_Type": "IMRP",
        "CFD_Generation_MWh": "2333.9490",
        "Avoided_GHG_tonnes_CO2e": "163.3298",
        "Strike_Price_GBP_Per_MWh": "102.0300",
        "CFD_Payments_GBP": "116500.3900",
        "Avoided_GHG_Cost_GBP": "12930.7920",
        "Market_Reference_Price_GBP_Per_MWh": "56.1563",
        "Weighted_IMRP_GBP_Per_MWh": "52.1144",
    },
    {
        "_id": 2,
        "Settlement_Date": "2025-11-05 00:00:00.0000000",
        "CfD_ID": "AR4-CLH-710",
        "Name_of_CfD_Unit": "Cleve Hill Solar Project",
        "Technology": "Solar PV",
        "Allocation_round": "Allocation Round 4",
        "Reference_Type": "IMRP",
        "CFD_Generation_MWh": "233.6670",
        "Avoided_GHG_tonnes_CO2e": "10.3561",
        "Strike_Price_GBP_Per_MWh": "61.1600",
        "CFD_Payments_GBP": "-4250.5200",
        "Avoided_GHG_Cost_GBP": "923.6041",
        "Market_Reference_Price_GBP_Per_MWh": "78.1729",
        "Weighted_IMRP_GBP_Per_MWh": "79.3505",
    },
    {
        "_id": 3,
        "Settlement_Date": "2025-11-05 00:00:00.0000000",
        "CfD_ID": "INV-HPC-001",
        "Name_of_CfD_Unit": "Hinkley Point C",
        "Technology": "Nuclear",
        "Allocation_round": "Investment Contract",
        "Reference_Type": "BMRP",
        "CFD_Generation_MWh": "1000.0",
        "Avoided_GHG_tonnes_CO2e": "0",
        "Strike_Price_GBP_Per_MWh": "130.0",
        "CFD_Payments_GBP": "50000.0",
        "Avoided_GHG_Cost_GBP": "0",
        "Market_Reference_Price_GBP_Per_MWh": "80.0",
        "Weighted_IMRP_GBP_Per_MWh": "",
    },
]

TRACKING_RECORDS = [
    {
        "_id": 14581,
        "Settlement_Date": "2024-10-01 00:00:00.0000000",
        "Actual_CFD_Payments_GBP": "8880757.1900",
        "Forecast_CFD_Payments_GBP": "",
    },
    {
        "_id": 99999,
        "Settlement_Date": "2026-06-08 00:00:00.0000000",
        "Actual_CFD_Payments_GBP": "",  # future rows have no actuals yet
        "Forecast_CFD_Payments_GBP": "5000000.0",
    },
]


def test_parse_generation_types_and_values():
    df = cfd.parse_generation(GENERATION_RECORDS)
    # is_renewable is NOT stored — it is a derived classification applied at
    # build time (see test_classify_* below), so the parsed/stored frame holds
    # only the source columns LCCC publishes.
    assert df.columns == [
        "date", "cfd_id", "unit_name", "technology",
        "generation_mwh", "payment_gbp", "strike_price_gbp_mwh",
    ]
    row = df.filter(df["cfd_id"] == "AR2-TKN-203").to_dicts()[0]
    assert row["date"] == date(2024, 8, 20)
    assert row["payment_gbp"] == 116500.39


def test_negative_payments_preserved():
    df = cfd.parse_generation(GENERATION_RECORDS)
    row = df.filter(df["cfd_id"] == "AR4-CLH-710").to_dicts()[0]
    assert row["payment_gbp"] == -4250.52


def test_classify_nuclear_is_not_renewable():
    df = cfd.classify(cfd.parse_generation(GENERATION_RECORDS))
    row = df.filter(df["cfd_id"] == "INV-HPC-001").to_dicts()[0]
    assert row["is_renewable"] is False


def test_classify_biomass_is_renewable():
    """Biomass holds renewable CfDs and counts toward renewable targets, so it
    belongs in the renewables headline (REF and every external aggregate count
    it there)."""
    for tech in ("Biomass Conversion", "Dedicated Biomass",
                 "Advanced Conversion Technology", "Energy from Waste"):
        df = cfd.classify(cfd.parse_generation(
            [dict(GENERATION_RECORDS[0], Technology=tech)]))
        assert df.to_dicts()[0]["is_renewable"] is True, tech


def test_classify_wind_is_renewable():
    df = cfd.classify(cfd.parse_generation(GENERATION_RECORDS))
    row = df.filter(df["cfd_id"] == "AR2-TKN-203").to_dicts()[0]
    assert row["is_renewable"] is True


def test_unknown_technology_raises():
    """An unrecognised label must fail the build, not silently drop into a
    bucket — the failure mode that previously left biomass out of the headline.
    Guarded at both fetch (parse_generation) and build (classify)."""
    import pytest
    record = dict(GENERATION_RECORDS[0], Technology="Future Mystery Tech")
    with pytest.raises(ValueError, match="Unclassified CfD technology"):
        cfd.parse_generation([record])


def test_parse_tracking_drops_rows_without_actuals():
    df = cfd.parse_tracking(TRACKING_RECORDS)
    assert df.height == 1
    assert df.to_dicts()[0] == {"date": date(2024, 10, 1), "payment_gbp": 8880757.19}


def test_classify_null_technology_is_not_renewable():
    record = dict(GENERATION_RECORDS[0], Technology=None)
    df = cfd.classify(cfd.parse_generation([record]))
    assert df.to_dicts()[0]["is_renewable"] is False


def test_blank_payment_rows_dropped():
    record = dict(GENERATION_RECORDS[0], CFD_Payments_GBP="")
    df = cfd.parse_generation([record])
    assert df.height == 0
