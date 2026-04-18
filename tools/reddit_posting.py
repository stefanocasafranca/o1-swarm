"""Reddit posting tool: post comments to threads.

Only called during live mode after policy approval.
Appends every post to posted-comments.jsonl for audit.
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
def post_reddit_comment(thread_url: str, comment_body: str) -> dict:
    """Post a comment to a Reddit thread.

    Args:
        thread_url: Full URL of the Reddit thread.
        comment_body: The comment text to post.

    Returns:
        Dict with permalink and status, or error details.
    """
    try:
        reddit = _get_reddit()

        submission = reddit.submission(url=thread_url)
        comment = submission.reply(comment_body)

        result = {
            "status": "posted",
            "permalink": f"https://reddit.com{comment.permalink}",
            "thread_url": thread_url,
            "subreddit": str(submission.subreddit),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "body_preview": comment_body[:100],
        }

        # Append to audit log
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        log_path = MEMORY_DIR / "posted-comments.jsonl"
        with open(log_path, "a") as f:
            f.write(json.dumps(result) + "\n")

        logger.info(f"Posted comment to {thread_url}")
        return result

    except Exception as e:
        logger.error(f"Failed to post comment: {e}")
        return {"status": "error", "error": str(e), "thread_url": thread_url}
