# Looks up each issuer's SEC industry code (SIC) from the SEC submissions API
# and flags the H8 tech universe (project.md Section 3). Results are cached in
# data/raw/sec_sic_codes.csv so each company is requested from the SEC only once.

import pandas as pd

from utils import RAW_DIR, fetch_sec_json

SIC_CACHE_FILE = RAW_DIR / "sec_sic_codes.csv"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

# H8 tech universe (fixed in project.md v3 before any H8 returns were computed)
TECH_SIC_CODES = (
    list(range(3570, 3580))  # computers and office equipment
    + [3661, 3663, 3669]  # communications equipment
    + list(range(3670, 3680))  # electronic components, incl. 3674 semiconductors
    + [3825, 3827]  # electronic test and optical instruments
    + list(range(7370, 7380))  # software, data processing, IT services, internet
)


def read_sic_cache():
    """Cached SIC codes: columns issuer_cik, sic, sic_description (sic is blank if the SEC had none)."""
    if not SIC_CACHE_FILE.exists():
        return pd.DataFrame(columns=["issuer_cik", "sic", "sic_description"])
    return pd.read_csv(SIC_CACHE_FILE, dtype={"issuer_cik": str})


def fetch_sic_codes(issuer_ciks):
    """Fetch the SIC code for every issuer not already cached. Saves progress every 100 companies."""
    cache = read_sic_cache()
    already_cached = set(cache["issuer_cik"])
    to_fetch = sorted(set(issuer_ciks) - already_cached)
    print(f"{len(to_fetch):,} companies to look up")

    new_rows = []
    for count, issuer_cik in enumerate(to_fetch, start=1):
        document = fetch_sec_json(SEC_SUBMISSIONS_URL.format(cik=str(issuer_cik).zfill(10)))
        new_rows.append(
            {
                "issuer_cik": issuer_cik,
                "sic": document.get("sic") if document else None,
                "sic_description": document.get("sicDescription") if document else None,
            }
        )
        if count % 100 == 0 or count == len(to_fetch):
            cache = pd.concat([cache, pd.DataFrame(new_rows)], ignore_index=True)
            SIC_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            cache.to_csv(SIC_CACHE_FILE, index=False)
            new_rows = []
            print(f"  {count:,}/{len(to_fetch):,} done")
    return read_sic_cache()


def add_industry(events):
    """Add sic, sic_description and is_tech_sic (issuer's SIC code is in the H8 tech list)."""
    sic_codes = read_sic_cache()
    events = events.merge(sic_codes, on="issuer_cik", how="left")
    sic_number = pd.to_numeric(events["sic"], errors="coerce")
    events["is_tech_sic"] = sic_number.isin(TECH_SIC_CODES)
    return events
