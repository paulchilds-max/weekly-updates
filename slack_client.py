"""Post the summary to Slack: TL;DR as the message, sections as thread replies."""

import os
import re
import time

import requests

POST_URL = "https://slack.com/api/chat.postMessage"
CHUNK_LIMIT = 2800  # Slack truncates long messages; stay well under the limit
TIMEOUT = 30


class SlackError(RuntimeError):
    pass


def to_mrkdwn(text):
    """Convert the Markdown Claude writes into Slack's mrkdwn dialect."""
    # Links: [label](url) -> <url|label>   (do this before bold, which eats *)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"<\2|\1>", text)
    # Bold: **text** -> *text*
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"*\1*", text)
    # Headings: ## Heading or ### Heading -> *Heading*
    text = re.sub(r"^#{1,6}\s*(.+)$", r"*\1*", text, flags=re.MULTILINE)
    # Bullets: leading - or * -> bullet character
    text = re.sub(r"^(\s*)[-*]\s+", r"\1• ", text, flags=re.MULTILINE)
    # Italics: _text_ is already valid mrkdwn, leave alone.
    return text.strip()


def chunk_text(text, limit=CHUNK_LIMIT):
    """Split on blank lines so headings stay with their bullets."""
    blocks = text.split("\n\n")
    chunks, current = [], ""
    for block in blocks:
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # A single block over the limit: hard split it.
            while len(block) > limit:
                cut = block.rfind("\n", 0, limit) or limit
                chunks.append(block[:cut])
                block = block[cut:].lstrip("\n")
            current = block
    if current:
        chunks.append(current)
    return chunks


def _post(payload):
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise SlackError("SLACK_BOT_TOKEN is not set. Check your .env file.")
    response = requests.post(
        POST_URL,
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        timeout=TIMEOUT,
    )
    data = response.json()
    if not data.get("ok"):
        raise SlackError(f"Slack rejected the message: {data.get('error')}")
    return data


def post_summary(tldr, sections, channel=None, header=None):
    """Post the TL;DR, then each section chunk as a threaded reply."""
    channel = channel or os.environ.get("SLACK_CHANNEL_ID")
    if not channel:
        raise SlackError("SLACK_CHANNEL_ID is not set.")

    body = to_mrkdwn(tldr)
    if header:
        body = f"*{header}*\n\n{body}"

    parent = _post({"channel": channel, "text": body, "unfurl_links": False})
    thread_ts = parent["ts"]
    print(f"Posted TL;DR (ts={thread_ts})")

    if sections:
        for i, chunk in enumerate(chunk_text(to_mrkdwn(sections)), start=1):
            _post(
                {
                    "channel": channel,
                    "thread_ts": thread_ts,
                    "text": chunk,
                    "unfurl_links": False,
                }
            )
            print(f"  posted thread reply {i} ({len(chunk)} chars)")
            time.sleep(1)  # stay under Slack's 1 message/second guidance

    return thread_ts


def post_alert(message, channel=None):
    """Post a short failure or empty-week notice."""
    channel = channel or os.environ.get("SLACK_CHANNEL_ID")
    return _post({"channel": channel, "text": f":warning: {message}"})