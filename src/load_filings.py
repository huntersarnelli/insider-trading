# Downloads, caches and parses the SEC Insider Transactions Data Sets (one zip
# per quarter), then applies filters 1-5 of project.md Section 5.2. Filters 6-7
# need prices, so they live in load_prices.py. Column names come from the SEC readme.

import csv
import zipfile

import pandas as pd
import requests

from utils import SEC_RAW_DIR, download_sec_file, record_row_count

SEC_DATA_SET_URL = (
    "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/"
    "{quarter}_form345.zip"
)
# From 2026q2 the SEC page links to a different folder; tried when the usual one returns 404.
SEC_DATA_SET_URL_NEW_FOLDER = (
    "https://www.sec.gov/files/datastandardsinnovation/data/insider-transactions-data-sets/"
    "{quarter}_form345.zip"
)
FIRST_YEAR = 2006  # first quarter on the SEC page is 2006q1
LAST_QUARTER = "2026q2"  # latest quarter on the SEC page as of 26 Sep 2026

MINIMUM_PURCHASE_USD = 10_000  # filter 5


# ---------------------------------------------------------------------------
# Step A: list, download and read quarters
# ---------------------------------------------------------------------------
def list_quarters():
    """Return every quarter label from 2006q1 to LAST_QUARTER, e.g. '2006q1'."""
    quarters = []
    for year in range(FIRST_YEAR, int(LAST_QUARTER[:4]) + 1):
        for quarter_number in range(1, 5):
            label = f"{year}q{quarter_number}"
            quarters.append(label)
            if label == LAST_QUARTER:
                return quarters
    return quarters


def download_quarter(quarter):
    """Download one quarterly zip into data/raw/sec/ (skipped if already cached)."""
    destination_path = SEC_RAW_DIR / f"{quarter}_form345.zip"
    try:
        return download_sec_file(SEC_DATA_SET_URL.format(quarter=quarter), destination_path)
    except requests.HTTPError as error:
        if error.response is None or error.response.status_code != 404:
            raise
        return download_sec_file(SEC_DATA_SET_URL_NEW_FOLDER.format(quarter=quarter), destination_path)


def read_table(zip_file, table_name, columns=None):
    """Read one tab-delimited table from an open quarterly zip, all columns as text."""
    with zip_file.open(f"{table_name}.tsv") as table_file:
        return pd.read_csv(
            table_file,
            sep="\t",
            dtype=str,
            usecols=columns,
            quoting=csv.QUOTE_NONE,  # free-text fields contain stray quote marks
            keep_default_na=False,
            na_values=[""],
            encoding_errors="replace",
        )


def parse_sec_date(text_dates):
    """Convert SEC dates like '31-JAN-2024' to pandas Timestamps."""
    return pd.to_datetime(text_dates, format="%d-%b-%Y", errors="coerce")


def read_10b5_1_flag(submissions):
    """Return 'yes', 'no' or 'unknown' per filing from the AFF10B5ONE column.

    The column only exists in files from 2023 onward. Values seen: 1/true, 0/false, blank.
    """
    if "AFF10B5ONE" not in submissions.columns:
        return pd.Series("unknown", index=submissions.index)
    raw_flag = submissions["AFF10B5ONE"].str.strip().str.lower()
    flag = pd.Series("unknown", index=submissions.index)
    flag[raw_flag.isin(["1", "true"])] = "yes"
    flag[raw_flag.isin(["0", "false"])] = "no"
    return flag


# ---------------------------------------------------------------------------
# Step B: apply filters 1-5 to one quarter
# ---------------------------------------------------------------------------
def filter_one_quarter(quarter):
    """Apply filters 1-5 to one quarter. Returns (purchases, row_count_log).

    Rows are transaction rows until the "sum lots" step, after which each row
    is one filing (one insider's purchase report).
    """
    row_count_log = []
    zip_path = download_quarter(quarter)

    with zipfile.ZipFile(zip_path) as zip_file:
        submissions = read_table(zip_file, "SUBMISSION")
        owners = read_table(zip_file, "REPORTINGOWNER")
        transactions = read_table(zip_file, "NONDERIV_TRANS")
        derivative_accessions = read_table(zip_file, "DERIV_TRANS", ["ACCESSION_NUMBER"])

    document_type_by_accession = submissions.set_index("ACCESSION_NUMBER")["DOCUMENT_TYPE"]
    transactions["DOCUMENT_TYPE"] = transactions["ACCESSION_NUMBER"].map(document_type_by_accession)
    derivative_document_types = derivative_accessions["ACCESSION_NUMBER"].map(document_type_by_accession)

    # Starting point: every transaction row in the quarter, all forms.
    record_row_count(
        row_count_log,
        "0. all transaction rows (non-derivative + derivative), all forms",
        len(transactions) + len(derivative_accessions),
    )

    # Filter 1: Form 4 only. The readme gives no rule for de-duplicating 4/A
    # amendments, so per project.md they are dropped.
    transactions = transactions[transactions["DOCUMENT_TYPE"] == "4"]
    derivative_form4_rows = (derivative_document_types == "4").sum()
    record_row_count(
        row_count_log,
        "1. form type 4 (4/A amendments dropped)",
        len(transactions) + derivative_form4_rows,
    )

    # Filter 2a: non-derivative table only.
    record_row_count(row_count_log, "2a. non-derivative transactions only", len(transactions))

    # Filter 2b: common stock only (security title contains 'common' or 'ordinary').
    title_lower = transactions["SECURITY_TITLE"].str.lower().fillna("")
    is_common = title_lower.str.contains("common") | title_lower.str.contains("ordinary")
    transactions = transactions[is_common]
    record_row_count(row_count_log, "2b. security title contains 'common' or 'ordinary'", len(transactions))

    # Filter 3a: transaction code P (open-market purchase).
    transactions = transactions[transactions["TRANS_CODE"] == "P"]
    record_row_count(row_count_log, "3a. transaction code P", len(transactions))

    # Filter 3b: drop code-P rows marked as Disposed (contradictory; likely filing errors).
    transactions = transactions[transactions["TRANS_ACQUIRED_DISP_CD"] == "A"]
    record_row_count(row_count_log, "3b. acquired (A), not disposed (D)", len(transactions))

    # Sum the individual lots of each filing into one purchase row.
    purchases = sum_lots_per_filing(transactions)
    record_row_count(
        row_count_log,
        "sum lots into one row per filing",
        len(purchases),
        note="unit changes here: rows below are filings, not transaction lots",
    )

    # Attach filing details and the first-listed reporting owner.
    purchases = attach_filing_details(purchases, submissions)
    purchases, multi_owner_filings = attach_first_owner(purchases, owners)
    record_row_count(
        row_count_log,
        "attach first-listed reporting owner",
        len(purchases),
        note="note_count = filings with more than one owner; kept the first",
        note_count=multi_owner_filings,
    )

    # Filter 4: drop filings flagged as made under a Rule 10b5-1 plan.
    purchases = purchases[purchases["plan_10b5_1"] != "yes"]
    record_row_count(
        row_count_log,
        "4. not flagged as a Rule 10b5-1 plan",
        len(purchases),
        note="flag only exists from 2023; earlier rows are 'unknown' and kept",
    )

    # Filter 5: total purchase value at least $10,000 (missing price counts as failing).
    missing_value_count = int(purchases["purchase_value_usd"].isna().sum())
    purchases = purchases[purchases["purchase_value_usd"] >= MINIMUM_PURCHASE_USD]
    record_row_count(
        row_count_log,
        "5. purchase value >= $10,000",
        len(purchases),
        note="note_count = filings dropped because a lot had no price or share count",
        note_count=missing_value_count,
    )

    purchases = purchases.copy()
    purchases["quarter"] = quarter
    return purchases, row_count_log


def sum_lots_per_filing(transactions):
    """Collapse the code-P lots of each filing into one row.

    purchase_value_usd = sum of shares x price over lots; average_price is the
    share-weighted price. shares_owned_after comes from the last lot in the
    filing (highest NONDERIV_TRANS_SK). A filing with any lot missing a price
    or share count gets purchase_value_usd = NaN.
    """
    lots = transactions.copy()
    lots["shares"] = pd.to_numeric(lots["TRANS_SHARES"], errors="coerce")
    lots["price"] = pd.to_numeric(lots["TRANS_PRICEPERSHARE"], errors="coerce")
    lots["lot_value"] = lots["shares"] * lots["price"]
    lots["shares_owned_after"] = pd.to_numeric(lots["SHRS_OWND_FOLWNG_TRANS"], errors="coerce")
    lots["transaction_date"] = parse_sec_date(lots["TRANS_DATE"])
    lots["lot_order"] = pd.to_numeric(lots["NONDERIV_TRANS_SK"], errors="coerce")
    lots = lots.sort_values(["ACCESSION_NUMBER", "lot_order"])

    grouped = lots.groupby("ACCESSION_NUMBER")
    purchases = pd.DataFrame(
        {
            "number_of_lots": grouped.size(),
            "first_transaction_date": grouped["transaction_date"].min(),
            "security_title": grouped["SECURITY_TITLE"].first(),
            "shares_purchased": grouped["shares"].sum(min_count=1),
            "purchase_value_usd": grouped["lot_value"].sum(min_count=1),
            "any_lot_missing_value": grouped["lot_value"].apply(lambda values: values.isna().any()),
            "shares_owned_after": grouped["shares_owned_after"].last(),
        }
    )
    purchases.loc[purchases["any_lot_missing_value"], "purchase_value_usd"] = float("nan")
    purchases["average_price"] = purchases["purchase_value_usd"] / purchases["shares_purchased"]
    purchases = purchases.drop(columns="any_lot_missing_value")
    return purchases.reset_index().rename(columns={"ACCESSION_NUMBER": "accession_number"})


def attach_filing_details(purchases, submissions):
    """Add filing date, issuer, ticker and the 10b5-1 flag from SUBMISSION."""
    filing_details = pd.DataFrame(
        {
            "accession_number": submissions["ACCESSION_NUMBER"],
            "filing_date": parse_sec_date(submissions["FILING_DATE"]),
            "issuer_cik": submissions["ISSUERCIK"],
            "issuer_name": submissions["ISSUERNAME"],
            "ticker_as_filed": submissions["ISSUERTRADINGSYMBOL"],
            "plan_10b5_1": read_10b5_1_flag(submissions),
        }
    )
    return purchases.merge(filing_details, on="accession_number", how="left")


def attach_first_owner(purchases, owners):
    """Add the first-listed reporting owner of each filing (file order).

    Returns (purchases, number of filings that listed more than one owner).
    """
    owners_in_our_filings = owners[owners["ACCESSION_NUMBER"].isin(purchases["accession_number"])]
    owner_count = owners_in_our_filings.groupby("ACCESSION_NUMBER").size()
    multi_owner_filings = int((owner_count > 1).sum())

    first_owner = owners_in_our_filings.drop_duplicates("ACCESSION_NUMBER", keep="first")
    first_owner = pd.DataFrame(
        {
            "accession_number": first_owner["ACCESSION_NUMBER"],
            "owner_cik": first_owner["RPTOWNERCIK"],
            "owner_name": first_owner["RPTOWNERNAME"],
            "owner_relationship": first_owner["RPTOWNER_RELATIONSHIP"],
            "owner_title": first_owner["RPTOWNER_TITLE"],
        }
    )
    return purchases.merge(first_owner, on="accession_number", how="left"), multi_owner_filings


# ---------------------------------------------------------------------------
# Step C: run every quarter and combine
# ---------------------------------------------------------------------------
def load_all_purchases(quarters):
    """Filter every quarter and combine. Returns (purchases, row_count_table).

    row_count_table sums each step across all quarters.
    """
    all_purchases = []
    all_logs = []
    for quarter in quarters:
        purchases, row_count_log = filter_one_quarter(quarter)
        all_purchases.append(purchases)
        all_logs.append(pd.DataFrame(row_count_log))
        print(f"{quarter}: {len(purchases):,} purchases kept")

    combined_logs = pd.concat(all_logs)
    row_count_table = combined_logs.groupby("step", sort=False).agg(
        rows_remaining=("rows_remaining", "sum"),
        rows_dropped=("rows_dropped", "sum"),
        note=("note", "first"),
        note_count=("note_count", "sum"),
    )
    row_count_table = row_count_table.reset_index()

    purchases = pd.concat(all_purchases, ignore_index=True)
    return purchases, row_count_table
