"""Dev runner for Phase 3: post an already-generated summary to Slack.

Usage:
    python post_summary.py                      # newest file in out/
    python post_summary.py out/summary_x.md     # a specific file
    python post_summary.py --preview            # print the converted text only
    python post_summary.py --alert "test"       # send a test warning message
"""

import glob
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

from slack_client import chunk_text, post_alert, post_summary, to_mrkdwn
from summarise import split_output

OUT_DIR = "out"


def newest_summary():
    files = sorted(glob.glob(os.path.join(OUT_DIR, "summary_*.md")))
    if not files:
        raise SystemExit("No summary files in out/. Run run_summary.py first.")
    return files[-1]


def main():
    load_dotenv()
    args = [a for a in sys.argv[1:]]

    if "--alert" in args:
        post_alert(args[args.index("--alert") + 1])
        print("Alert sent.")
        return

    preview = "--preview" in args
    paths = [a for a in args if a.endswith(".md")]
    path = paths[0] if paths else newest_summary()

    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    tldr, sections = split_output(raw)
    print(f"Using {path}")

    if preview:
        print("\n--- TL;DR (as Slack will see it) " + "-" * 27)
        print(to_mrkdwn(tldr))
        print("\n--- THREAD CHUNKS " + "-" * 42)
        for i, chunk in enumerate(chunk_text(to_mrkdwn(sections)), start=1):
            print(f"\n[chunk {i}: {len(chunk)} chars]")
            print(chunk)
        return

    header = datetime.now(timezone.utc).strftime("Weekly Product Summary — %d %b %Y")
    post_summary(tldr, sections, header=header)
    print("Done.")


if __name__ == "__main__":
    main()