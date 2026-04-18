"""Primary discovery tool: SerpApi Google Search for Reddit threads.

Queries Google's index of Reddit via SerpApi, which surfaces threads
by relevance that Reddit's native search misses entirely.
"""

import logging
import os
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def search_serpapi(keywords: str, max_results: int = 20) -> list[dict]:
    """Search Google for Reddit threads matching keywords via SerpApi.

    Args:
        keywords: Search terms describing the problem BUILD_SCRIPT solves.
        max_results: Maximum results to return (default 20).

    Returns:
        List of candidate threads with title, url, subreddit, snippet, rank.
    """
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        logger.warning("SERPAPI_API_KEY not set, returning empty results")
        return []

    try:
        from serpapi import GoogleSearch

        params = {
            "engine": "google",
            "q": f"site:reddit.com {keywords}",
            "num": max_results,
            "tbs": "qdr:w",  # last week
            "api_key": api_key,
        }

        search = GoogleSearch(params)
        results = search.get_dict()
        organic = results.get("organic_results", [])

        candidates = []
        for i, r in enumerate(organic):
            link = r.get("link", "")
            if "reddit.com" not in link:
                continue

            # Extract subreddit from URL
            subreddit = ""
            parts = link.split("/r/")
            if len(parts) > 1:
                subreddit = parts[1].split("/")[0]

            candidates.append({
                "title": r.get("title", ""),
                "url": link,
                "subreddit": subreddit,
                "snippet": r.get("snippet", ""),
                "rank_position": i + 1,
                "source": "serpapi",
                "score": 0,
                "num_comments": 0,
                "age_hours": 0,
            })

        logger.info(f"SerpApi returned {len(candidates)} Reddit threads")
        return candidates

    except Exception as e:
        logger.error(f"SerpApi search failed: {e}")
        return []
