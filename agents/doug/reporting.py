"""Email summary generation for Doug's operational reports.

Builds the Gmail body for cycle summaries. Subject is always constant
to maintain email threading.
"""

from datetime import datetime, timezone

SUBJECT = "Re: [DOUG] Operations Log"
FIRST_SUBJECT = "[DOUG] Operations Log"


def build_summary_email(state, results: dict) -> dict:
    """Build the email summary for a completed cycle."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    is_first = not state.gmail_thread_message_id

    lines = [
        f"Cycle: {state.cycle_type}",
        f"Run ID: {state.run_id}",
        f"Mode: {state.mode}",
        f"Model: {state.model_name}",
        f"Brain: {state.brain_hash[:20]}...",
        f"Time: {now}",
        "",
    ]

    if state.star_count is not None:
        lines.append(f"Stars: {state.star_count}")

    threads_found = results.get("threads_found", 0)
    threads_ranked = results.get("threads_ranked", 0)
    drafts_created = results.get("drafts_created", 0)
    comments_posted = results.get("comments_posted", 0)

    lines.extend([
        f"Threads discovered: {threads_found}",
        f"Threads ranked: {threads_ranked}",
        f"Drafts created: {drafts_created}",
        f"Comments posted: {comments_posted}",
        "",
        f"Health: {state.health_status}",
        f"Daily comments used: {state.daily_comment_count}",
    ])

    if state.mode == "shadow":
        lines.append(f"Shadow days (healthy): {state.healthy_shadow_days}/3")

    if results.get("errors"):
        lines.append("")
        lines.append("Errors:")
        for err in results["errors"]:
            lines.append(f"  - {err}")

    body = "\n".join(lines)

    return {
        "subject": FIRST_SUBJECT if is_first else SUBJECT,
        "body": body,
    }
