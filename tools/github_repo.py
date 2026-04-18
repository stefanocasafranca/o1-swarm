"""GitHub repo metadata updates: description, topics.

Low-risk operations only. No destructive actions.
"""

import json
import logging
import os
import urllib.request
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

TARGET_REPO = "stefanocasafranca/build-script"


@tool
def update_github_repo(description: str = "", topics: list[str] | None = None) -> dict:
    """Update BUILD_SCRIPT repo description and/or topics.

    Args:
        description: New repo description (empty string to skip).
        topics: List of topic tags to set (None to skip).

    Returns:
        Dict with updated fields or error.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"error": "GITHUB_TOKEN not set"}

    results = {}

    if description:
        url = f"https://api.github.com/repos/{TARGET_REPO}"
        payload = json.dumps({"description": description}).encode()
        req = urllib.request.Request(url, data=payload, method="PATCH")
        req.add_header("Authorization", f"token {token}")
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "o1-swarm-doug/1.0")
        try:
            with urllib.request.urlopen(req) as resp:
                results["description"] = "updated"
        except Exception as e:
            results["description_error"] = str(e)

    if topics is not None:
        url = f"https://api.github.com/repos/{TARGET_REPO}/topics"
        payload = json.dumps({"names": topics}).encode()
        req = urllib.request.Request(url, data=payload, method="PUT")
        req.add_header("Authorization", f"token {token}")
        req.add_header("Accept", "application/vnd.github.mercy-preview+json")
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "o1-swarm-doug/1.0")
        try:
            with urllib.request.urlopen(req) as resp:
                results["topics"] = "updated"
        except Exception as e:
            results["topics_error"] = str(e)

    return results or {"status": "no changes requested"}
