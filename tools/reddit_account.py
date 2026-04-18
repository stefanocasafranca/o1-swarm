"""Reddit account monitoring: check replies to Doug's comments.

Tracks sentiment and engagement on previously posted comments
to detect risk signals (downvotes, negative replies, mod actions).
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

MEMORY_DIR = Path(__file__).parent.parent / "memory" / "doug"


def _get_reddit():
    import praw
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        username=os.environ["REDDIT_USERNAME"],
        password=os.environ["REDDIT_PASSWORD"],
        user_agent="o1-swarm-doug/1.0",
    )


@tool
def check_reddit_replies() -> dict:
    """Check replies to Doug's recent Reddit comments.

    Returns:
        Summary of reply activity including counts, sentiment signals, and risk flags.
    """
    try:
        reddit = _get_reddit()
        user = reddit.user.me()
    except Exception as e:
        logger.error(f"Reddit account check failed: {e}")
        return {"error": str(e), "replies": [], "risk_signals": []}

    replies = []
    risk_signals = []

    try:
        for comment in user.comments.new(limit=25):
            comment.refresh()
            for reply in comment.replies[:5]:
                reply_data = {
                    "parent_url": f"https://reddit.com{comment.permalink}",
                    "reply_author": str(reply.author) if reply.author else "[deleted]",
                    "reply_body": reply.body[:300],
                    "reply_score": reply.score,
                    "parent_score": comment.score,
                    "subreddit": str(comment.subreddit),
                    "timestamp": datetime.fromtimestamp(
                        reply.created_utc, tz=timezone.utc
                    ).isoformat(),
                }
                replies.append(reply_data)

                if comment.score < -2:
                    risk_signals.append(f"Comment at {comment.permalink} has score {comment.score}")
                if "spam" in reply.body.lower() or "bot" in reply.body.lower():
                    risk_signals.append(f"Reply mentions spam/bot at {comment.permalink}")

    except Exception as e:
        logger.warning(f"Error fetching replies: {e}")

    # Persist monitor state
    monitor_path = MEMORY_DIR / "reply-monitor.json"
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    monitor_data = {
        "last_checked": datetime.now(timezone.utc).isoformat(),
        "total_replies": len(replies),
        "risk_signals": risk_signals,
    }
    monitor_path.write_text(json.dumps(monitor_data, indent=2) + "\n")

    return {
        "replies": replies,
        "risk_signals": risk_signals,
        "total": len(replies),
    }
