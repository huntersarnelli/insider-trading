# Shared helpers used by every other module: project paths, a polite cached
# downloader for SEC files (User-Agent header, rate limit, never re-download),
# and a small logger that records row counts after each filter step.

import time
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
SEC_RAW_DIR = RAW_DIR / "sec"
PRICE_RAW_DIR = RAW_DIR / "prices"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
RESULTS_DIR = PROJECT_ROOT / "results"

# ---------------------------------------------------------------------------
# SEC fair-access settings (project.md Section 5.1)
# ---------------------------------------------------------------------------
SEC_USER_AGENT = "Hunter Sarnelli huntersarnelli1@gmail.com"
SEC_SECONDS_BETWEEN_REQUESTS = 0.2  # at most 5 requests per second; SEC limit is 10

_time_of_last_sec_request = 0.0


def wait_for_sec_rate_limit():
    """Sleep just long enough to stay under the SEC request rate limit."""
    global _time_of_last_sec_request
    seconds_since_last_request = time.time() - _time_of_last_sec_request
    if seconds_since_last_request < SEC_SECONDS_BETWEEN_REQUESTS:
        time.sleep(SEC_SECONDS_BETWEEN_REQUESTS - seconds_since_last_request)
    _time_of_last_sec_request = time.time()


def fetch_sec_json(url):
    """GET a JSON document from the SEC (User-Agent + rate limit). Returns None on 404."""
    response = get_from_sec(url)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


RETRYABLE_SEC_STATUS_CODES = {429, 500, 502, 503, 504}


def get_from_sec(url, attempts=5):
    """GET with the SEC User-Agent and rate limit. Retries after network timeouts and
    temporary server errors (429/5xx), waiting 30s, 60s, 90s... between attempts."""
    for attempt in range(1, attempts + 1):
        wait_for_sec_rate_limit()
        try:
            response = requests.get(url, headers={"User-Agent": SEC_USER_AGENT}, timeout=60)
            if response.status_code not in RETRYABLE_SEC_STATUS_CODES or attempt == attempts:
                return response
        except (requests.Timeout, requests.ConnectionError):
            if attempt == attempts:
                raise
        print(f"  SEC temporarily unavailable; retrying in {30 * attempt}s")
        time.sleep(30 * attempt)


def fetch_sec_text(url):
    """GET a web page from the SEC (User-Agent + rate limit). Returns None on 404."""
    response = get_from_sec(url)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.text


def download_sec_file(url, destination_path):
    """Download url to destination_path unless the file already exists.

    Sends the required User-Agent header and waits between requests so we
    stay well under the SEC limit of 10 requests per second.
    Returns the destination path.
    """
    destination_path = Path(destination_path)
    if destination_path.exists():
        return destination_path

    wait_for_sec_rate_limit()
    response = requests.get(url, headers={"User-Agent": SEC_USER_AGENT}, timeout=120)
    response.raise_for_status()

    # Write to a temporary name first so a failed download never leaves a
    # half-written file that would later be mistaken for a cached one.
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination_path.with_suffix(destination_path.suffix + ".part")
    temporary_path.write_bytes(response.content)
    temporary_path.rename(destination_path)
    return destination_path


# ---------------------------------------------------------------------------
# Row-count logging (project.md Section 5.2: "log the row count after each step")
# ---------------------------------------------------------------------------
def record_row_count(row_count_log, step_name, row_count, note="", note_count=0):
    """Append one filter step to row_count_log (a plain list of dicts).

    note_count is an optional number that the note refers to (e.g. how many
    filings had several owners); it is summed when quarters are combined.
    """
    if len(row_count_log) == 0:
        rows_dropped = 0
    else:
        rows_dropped = row_count_log[-1]["rows_remaining"] - row_count
    row_count_log.append(
        {
            "step": step_name,
            "rows_remaining": row_count,
            "rows_dropped": rows_dropped,
            "note": note,
            "note_count": note_count,
        }
    )


def save_results_csv(table, phase_and_name, file_name):
    """Save a DataFrame to results/<phase>_<name>/<file_name> and return the path."""
    output_folder = RESULTS_DIR / phase_and_name
    output_folder.mkdir(parents=True, exist_ok=True)
    output_path = output_folder / file_name
    table.to_csv(output_path, index=False)
    return output_path
