"""GitHub stars tracking: fetch count, log metrics, compute pace.

Single tool that handles fetch + log + pace calculation + milestone detection.
No separate metrics tool needed.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

MEMORY_DIR = Path(__file__).parent.parent / "memory" / "doug"
TARGET_REPO = "stefanocasafranca/build-script"
TARGET_STARS = 200
MILESTONES = [10, 25, 50, 100, 200]


@tool
def check_github_stars() -> dict:
    """Check GitHub star count for BUILD_SCRIPT, log metrics, and compute pace.

    Returns:
        Dict with current stars, daily pace, milestone alerts, and days estimate.
    """
    import urllib.request

    token = os.environ.get("GITHUB_TOKEN", "")
    url = f"https://api.github.com/repos/{TARGET_REPO}"

    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "o1-swarm-doug/1.0")
    if token:
        req.add_header("Authorization", f"token {token}")

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            stars = data.get("stargazers_count", 0)
    except Exception as e:
        logger.error(f"GitHub API failed: {e}")
        return {"error": str(e)}

    now = datetime.now(timezone.utc)

    # Append to metrics log
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = MEMORY_DIR / "metrics.jsonl"
    entry = {
        "timestamp": now.isoformat(),
        "stars": stars,
        "repo": TARGET_REPO,
    }
    with open(metrics_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Compute pace from history
    pace_info = _compute_pace(metrics_path, stars)

    # Check milestones
    milestone_hit = None
    prev_stars = _get_previous_stars(metrics_path)
    for m in MILESTONES:
        if prev_stars < m <= stars:
            milestone_hit = m
            break

    result = {
        "stars": stars,
        "target": TARGET_STARS,
        "remaining": max(0, TARGET_STARS - stars),
        "milestone_hit": milestone_hit,
        **pace_info,
    }

    if milestone_hit:
        logger.info(f"MILESTONE: {milestone_hit} stars reached!")

    return result


def _compute_pace(metrics_path: Path, current: int) -> dict:
    """Compute daily star acquisition rate from history."""
    if not metrics_path.exists():
        return {"daily_rate": 0, "days_to_target": None}

    lines = metrics_path.read_text().strip().split("\n")
    if len(lines) < 2:
        return {"daily_rate": 0, "days_to_target": None}

    first = json.loads(lines[0])
    first_stars = first.get("stars", 0)
    first_time = datetime.fromisoformat(first["timestamp"])
    now = datetime.now(timezone.utc)

    days_elapsed = max((now - first_time).total_seconds() / 86400, 0.1)
    gained = current - first_stars
    daily_rate = round(gained / days_elapsed, 2)

    remaining = max(0, TARGET_STARS - current)
    days_to_target = round(remaining / daily_rate, 1) if daily_rate > 0 else None

    return {"daily_rate": daily_rate, "days_to_target": days_to_target}


def _get_previous_stars(metrics_path: Path) -> int:
    """Get the star count from the second-to-last entry."""
    if not metrics_path.exists():
        return 0
    lines = metrics_path.read_text().strip().split("\n")
    if len(lines) < 2:
        return 0
    return json.loads(lines[-2]).get("stars", 0)
