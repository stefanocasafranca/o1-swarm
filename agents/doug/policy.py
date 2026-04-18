"""Deterministic policy enforcement for Doug.

All filtering, cap checking, and posting decisions are pure code.
No LLM calls. No ambiguity.
"""

from datetime import datetime, timezone

# Subreddits Doug is allowed to post in
SUBREDDIT_ALLOWLIST = {
    "ClaudeAI",
    "LocalLLaMA",
    "programming",
    "Python",
    "OpenAI",
    "Anthropic",
    "MachineLearning",
    "artificial",
    "learnprogramming",
    "coding",
    "webdev",
}

# Limits
MAX_DAILY_COMMENTS = 5
MAX_THREAD_AGE_DAYS = 14
MIN_THREAD_SCORE = 2


def filter_candidates(candidates: list[dict], state, posted_urls: set[str]) -> list[dict]:
    """Filter raw candidates through deterministic policy rules."""
    filtered = []
    for c in candidates:
        subreddit = c.get("subreddit", "").replace("r/", "")
        if subreddit not in SUBREDDIT_ALLOWLIST:
            continue

        age_hours = c.get("age_hours", 0)
        if age_hours > MAX_THREAD_AGE_DAYS * 24:
            continue

        score = c.get("score", 0)
        if score < MIN_THREAD_SCORE and c.get("source") != "serpapi":
            continue

        url = c.get("url", "")
        if url in posted_urls:
            continue

        filtered.append(c)

    return filtered


def check_post_policy(state, num_drafts: int) -> dict:
    """Check whether posting is allowed right now."""
    if state.mode == "shadow":
        return {"allowed": False, "reason": "shadow mode, drafts only"}

    if state.mode == "human_review":
        return {"allowed": False, "reason": "human review, posting disabled"}

    remaining = MAX_DAILY_COMMENTS - state.daily_comment_count
    if remaining <= 0:
        return {"allowed": False, "reason": f"daily cap reached ({MAX_DAILY_COMMENTS})"}

    allowed_count = min(num_drafts, remaining)
    return {"allowed": True, "count": allowed_count}


def check_shadow_promotion(state) -> bool:
    """Check if Doug should be promoted from shadow to live."""
    return (
        state.mode == "shadow"
        and state.healthy_shadow_days >= 3
        and state.health_status == "healthy"
    )


def check_mission_deadline(state) -> bool:
    """Check if the 60-day deadline has passed without reaching 200 stars."""
    if state.mission_day is not None and state.mission_day >= 60:
        if state.star_count is not None and state.star_count < 200:
            return True
    return False


def load_posted_urls() -> set[str]:
    """Load all previously posted thread URLs from posted-comments.jsonl."""
    import json
    from pathlib import Path

    path = Path(__file__).parent.parent.parent / "memory" / "doug" / "posted-comments.jsonl"
    urls = set()
    if path.exists():
        for line in path.read_text().strip().split("\n"):
            if line:
                entry = json.loads(line)
                urls.add(entry.get("thread_url", ""))
    return urls
