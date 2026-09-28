"""Production entry point: fetch -> filter -> summarise -> post.

Run locally:
    python main.py
    python main.py --no-post     # everything except the Slack post
"""

import logging
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from fireflies_client import fetch_transcripts, week_window
from filters import filter_transcripts
from slack_client import post_alert, post_summary
from summarise import build_meeting_block, estimate_tokens, split_output, summarise

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("weekly-summary")

REQUIRED_VARS = [
    "FIREFLIES_API_KEY",
    "ANTHROPIC_API_KEY",
    "SLACK_BOT_TOKEN",
    "SLACK_CHANNEL_ID",
]


def check_environment():
    missing = [name for name in REQUIRED_VARS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")


def window_label(start_iso, end_iso):
    start = datetime.strptime(start_iso, "%Y-%m-%dT%H:%M:%S.000Z")
    end = datetime.strptime(end_iso, "%Y-%m-%dT%H:%M:%S.000Z")
    return f"{start:%d %b} to {end:%d %b %Y}"


def run(post_to_slack=True):
    check_environment()

    start, end = week_window()
    label = window_label(start, end)
    log.info("Window: %s", label)

    log.info("Fetching transcripts...")
    transcripts = fetch_transcripts(start, end)
    log.info("Fetched %d transcripts", len(transcripts))

    kept, dropped = filter_transcripts(transcripts)
    log.info("Kept %d, dropped %d", len(kept), len(dropped))

    if not kept:
        msg = f"Weekly summary: no qualifying meetings found for {label}."
        log.warning(msg)
        if post_to_slack:
            post_alert(msg)
        return 0

    block = build_meeting_block(kept)
    log.info("Meeting block: ~%d tokens", estimate_tokens(block))

    log.info("Calling Claude...")
    raw = summarise(block, label)
    tldr, sections = split_output(raw)
    log.info("Summary: %d words, sections present: %s", len(raw.split()), bool(sections))

    if not post_to_slack:
        print("\n" + raw)
        return 0

    header = f"Weekly Product Summary — {label}"
    post_summary(tldr, sections, header=header)
    log.info("Posted to Slack")
    return 0


def main():
    load_dotenv()
    post_to_slack = "--no-post" not in sys.argv
    try:
        return run(post_to_slack=post_to_slack)
    except Exception as exc:  # noqa: BLE001 - we want every failure reported
        log.error("Run failed: %s", exc)
        traceback.print_exc()
        try:
            post_alert(
                f"Weekly summary run FAILED: {type(exc).__name__}: {exc}. "
                "Check the GitHub Actions log."
            )
        except Exception:  # noqa: BLE001 - Slack itself may be the failure
            log.error("Could not post the failure alert to Slack")
        return 1


if __name__ == "__main__":
    sys.exit(main())