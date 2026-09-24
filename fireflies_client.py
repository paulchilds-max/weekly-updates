"""Fireflies GraphQL client: fetch transcripts for a date window."""

import os
import time
from datetime import datetime, timedelta, timezone

import requests

API_URL = "https://api.fireflies.ai/graphql"
PAGE_SIZE = 50          # Fireflies caps `transcripts` at 50 results per query
MAX_PAGES = 20          # safety stop: 20 pages = 1000 meetings
REQUEST_TIMEOUT = 60    # seconds

TRANSCRIPTS_QUERY = """
query Transcripts($fromDate: DateTime, $toDate: DateTime, $limit: Int, $skip: Int) {
  transcripts(fromDate: $fromDate, toDate: $toDate, limit: $limit, skip: $skip) {
    id
    title
    date
    duration
    organizer_email
    summary {
      short_summary
      overview
      keywords
      action_items
    }
  }
}
"""


class FirefliesError(RuntimeError):
    pass


def _api_key():
    key = os.environ.get("FIREFLIES_API_KEY")
    if not key:
        raise FirefliesError("FIREFLIES_API_KEY is not set. Check your .env file.")
    return key


def _post(query, variables, max_retries=5):
    """POST a GraphQL query, retrying on 429 and 5xx with exponential backoff."""
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    delay = 2
    for attempt in range(1, max_retries + 1):
        response = requests.post(
            API_URL,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 429:
            if attempt == max_retries:
                raise FirefliesError(
                    "Rate limited by Fireflies after several retries. "
                    "Free/Pro plans allow only 50 requests per day."
                )
            print(f"  rate limited, waiting {delay}s (attempt {attempt}/{max_retries})")
            time.sleep(delay)
            delay *= 2
            continue

        if response.status_code >= 500:
            if attempt == max_retries:
                raise FirefliesError(f"Fireflies server error {response.status_code}")
            time.sleep(delay)
            delay *= 2
            continue

        if response.status_code != 200:
            raise FirefliesError(f"HTTP {response.status_code}: {response.text[:400]}")

        payload = response.json()
        if "errors" in payload:
            raise FirefliesError(f"GraphQL error: {payload['errors']}")
        return payload["data"]

    raise FirefliesError("Request failed after retries")


def week_window(days=7, now=None):
    """Return (from_date, to_date) as ISO 8601 UTC strings for the last N days."""
    end = now or datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    fmt = "%Y-%m-%dT%H:%M:%S.000Z"
    return start.strftime(fmt), end.strftime(fmt)


def fetch_transcripts(from_date, to_date):
    """Fetch every transcript in the window, following pagination."""
    all_transcripts = []
    for page in range(MAX_PAGES):
        skip = page * PAGE_SIZE
        print(f"  fetching page {page + 1} (skip={skip})...")
        data = _post(
            TRANSCRIPTS_QUERY,
            {
                "fromDate": from_date,
                "toDate": to_date,
                "limit": PAGE_SIZE,
                "skip": skip,
            },
        )
        batch = data.get("transcripts") or []
        all_transcripts.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        time.sleep(1)  # be polite between pages
    else:
        print(f"  WARNING: hit MAX_PAGES ({MAX_PAGES}); results may be truncated")

    return all_transcripts


def meeting_datetime(transcript):
    """Fireflies returns `date` as epoch milliseconds (sometimes an ISO string)."""
    raw = transcript.get("date")
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw / 1000, tz=timezone.utc)
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def meeting_url(transcript):
    return f"https://app.fireflies.ai/view/{transcript['id']}"


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    start, end = week_window()
    print(f"Window: {start} -> {end}")
    items = fetch_transcripts(start, end)
    print(f"Fetched {len(items)} transcripts")
    for t in items[:5]:
        dt = meeting_datetime(t)
        stamp = dt.strftime("%Y-%m-%d %H:%M") if dt else "?"
        print(f"  {stamp}  {t.get('title')}")