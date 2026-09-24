"""Rules for dropping meetings that are not product-relevant.

Tune the two lists below. Everything else is mechanical.
"""

import re

# --- tuning knobs -----------------------------------------------------------

MIN_DURATION_MINUTES = 5

# Dropped if any of these appear in the title (case-insensitive substring match).
EXCLUDE_TITLE_TERMS = [
    "interview",
    "intro call",
    "candidate",
    "screening",
    "hiring",
    "recruit",
    "recruitment",
    "yoga",
    "wellness",
    "coffee",
    "lunch",
    "birthday",
    "english lesson",
    "english class",
    "spanish",
    "language",
    "onboarding",
    "training",
    "webinar",
    "demo for",
    "daily",
    "weekly",
    "monthly",
    "standup",
    "sync",
    "engineering",
    "chardonnay",
    "stand-up",
    "discussion",
    "office hours",
    "workshop",
    "check-in",
    "121",
    "onboarding",
    "okrs",
    "kickoff",
    "planning",
    "review",
    "retrospective",
    "retro",
    "kick-off",
    "discuss",
    "case study",
    "scoping",
    "huddle",
    "wig",
    "1-1",
    "gaming",
    "l10",
    "1-2-1",
    "interview",
    "catch up",
    "club",
    "demo",
    "standup",
    "intro",
    "hold",
    "scrum",
    "check in",
    "coaching",
    "initiative",
    "qbr prep",
    "1x1",
    "project",
    "feedback",
    "block buster weekly",
    "artur / anna",
    "Marketing",
    "outstanding",
    "commitments",
    "meeting",
    "anton / mitali",
    "brainstorm",
    "sergey / joel",
    "brainstorm",
    "ai",
    "stas - lera",
    "francesco / joel",
    "roles",
    "follow-up",
    "appodeal",
    "okra",
    "dmytrii / roman",
    "block buster / mainx"
    "accelerator",
    "embeddings",
    "ml",
    "sales",
    "1 on 1",
    "discussion",
    "intro",
    "1 on 1",
    "rendering",
    "natalia / nikita",
    "peter / katarzyna",
    "game",
    "development",
    "norayr / anastasia",
    "hanna / sebastian",
    "hold",
    "casey wuestefeld and joel chang",
    "creative",
    "Danila / Joel",
    "refactoring",
    "rachel / camille",
    "nueva",
    "all hands social",
]

# Kept even if a term above matches (rescue list, checked first).
ALWAYS_KEEP_TERMS = [
    "bidmachine+",
    "bm plus",
    "bm+",
    "first look",
    "mediation",
    "roadmap",
    "sdk",
    "product",
]

# --- mechanics --------------------------------------------------------------


def _normalise_duration_minutes(raw):
    """Fireflies usually returns minutes; fall back to seconds if implausible."""
    if raw is None:
        return None
    value = float(raw)
    if value > 600:  # no meeting runs 10+ hours: this must be seconds
        return value / 60
    return value


def summary_text(transcript):
    summary = transcript.get("summary") or {}
    parts = [summary.get("short_summary"), summary.get("overview")]
    return "\n".join(p for p in parts if p).strip()


def exclusion_reason(transcript):
    """Return a reason string if the meeting should be dropped, else None."""
    title = (transcript.get("title") or "").strip()
    lowered = title.lower()

    if not summary_text(transcript):
        return "no summary"

    minutes = _normalise_duration_minutes(transcript.get("duration"))
    if minutes is not None and minutes < MIN_DURATION_MINUTES:
        return f"too short ({minutes:.0f} min)"

    if any(term in lowered for term in ALWAYS_KEEP_TERMS):
        return None

    for term in EXCLUDE_TITLE_TERMS:
        if term in lowered:
            return f"title term '{term}'"

    # One-to-one patterns like "Paul <> Jane" or "1:1", kept only if a keep term hit.
    if re.search(r"\b1[:\-]?1\b|<>", lowered) and "paul" not in lowered:
        return "1:1 without product keyword"

    return None


def filter_transcripts(transcripts):
    """Split transcripts into (kept, dropped) where dropped is (transcript, reason)."""
    kept, dropped = [], []
    for t in transcripts:
        reason = exclusion_reason(t)
        if reason:
            dropped.append((t, reason))
        else:
            kept.append(t)
    return kept, dropped