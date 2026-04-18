"""Fallback discovery tool: PRAW Reddit search.

Searches Reddit directly via PRAW. Catches fresh threads (< 1 hour old)
that Google hasn't indexed yet.
"""

import logging
import os
from datetime import datetime, timezone
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

TARGET_SUBREDDITS = [
    "ClaudeAI",
    "LocalLLaMA",
    "programming",
    "Python",
    "OpenAI",
    "Anthropic",
    "MachineLearning",
]


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
def search_reddit(keywords: str, max_results: int = 20) -> list[dict]:
    """Search Reddit subreddits for threads matching keywords via PRAW.

    Args:
        keywords: Search terms for finding relevant threads.
        max_results: Maximum results per subreddit (default 20).

    Returns:
        List of candidate threads with title, url, subreddit, score, comments, age.
    """
    try:
        reddit = _get_reddit()
    except Exception as e:
        logger.error(f"PRAW init failed: {e}")
        return []

    candidates = []
    now = datetime.now(timezone.utc)

    for sub_name in TARGET_SUBREDDITS:
        try:
            subreddit = reddit.subreddit(sub_name)
            for submission in subreddit.search(keywords, sort="new", limit=max_results):
                created = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
                age_hours = (now - created).total_seconds() / 3600

                candidates.append({
                    "title": submission.title,
                    "url": f"https://reddit.com{submission.permalink}",
                    "subreddit": sub_name,
                    "snippet": (submission.selftext or "")[:200],
                    "score": submission.score,
                    "num_comments": submission.num_comments,
                    "age_hours": round(age_hours, 1),
                    "source": "praw",
                    "rank_position": 0,
                })
        except Exception as e:
            logger.warning(f"Failed to search r/{sub_name}: {e}")
            continue

    logger.info(f"PRAW returned {len(candidates)} Reddit threads")
    return candidates
