"""Dev runner for Phase 1: fetch a week of transcripts, cache them, then filter.

Usage:
    python fetch_and_filter.py           # fetch from the API (uses an API request)
    python fetch_and_filter.py --cached  # re-use the cached file, no API call
"""

import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from fireflies_client import fetch_transcripts, meeting_datetime, week_window
from filters import filter_transcripts, summary_text

CACHE_DIR = "data"
CACHE_FILE = os.path.join(CACHE_DIR, "raw_transcripts.json")


def load_cached():
    with open(CACHE_FILE, encoding="utf-8") as fh:
        return json.load(fh)


def save_cached(transcripts):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as fh:
        json.dump(transcripts, fh, indent=2, ensure_ascii=False)
    print(f"Cached {len(transcripts)} transcripts to {CACHE_FILE}")


def main():
    load_dotenv()
    use_cache = "--cached" in sys.argv

    if use_cache:
        transcripts = load_cached()
        print(f"Loaded {len(transcripts)} transcripts from cache")
    else:
        start, end = week_window()
        print(f"Window: {start} -> {end}")
        transcripts = fetch_transcripts(start, end)
        print(f"Fetched {len(transcripts)} transcripts")
        save_cached(transcripts)

    kept, dropped = filter_transcripts(transcripts)

    print("\n--- DROPPED " + "-" * 50)
    for t, reason in sorted(dropped, key=lambda x: x[1]):
        print(f"  [{reason}] {t.get('title')}")

    print("\n--- KEPT " + "-" * 53)
    for t in sorted(kept, key=lambda t: meeting_datetime(t) or datetime.min.replace(tzinfo=timezone.utc)):
        dt = meeting_datetime(t)
        stamp = dt.strftime("%a %d %b %H:%M") if dt else "?"
        print(f"  {stamp}  {t.get('title')}")

    print("\n--- COUNTS " + "-" * 51)
    print(f"  fetched: {len(transcripts)}")
    print(f"  dropped: {len(dropped)}")
    print(f"  kept:    {len(kept)}")

    chars = sum(len(summary_text(t)) for t in kept)
    print(f"  summary characters kept: {chars:,} (~{chars // 4:,} tokens)")


if __name__ == "__main__":
    main()