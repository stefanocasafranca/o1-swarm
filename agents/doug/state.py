"""Runtime state management for Doug.

Handles loading, saving, and validating execution state.
State persists in memory/doug/state.json between runs.
"""

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

MEMORY_DIR = Path(__file__).parent.parent.parent / "memory" / "doug"


@dataclass
class RuntimeState:
    # Execution identity
    mode: Literal["shadow", "live", "human_review"] = "shadow"
    cycle_type: str = ""
    cycle_slot_key: str = ""
    run_id: str = ""

    # Brain audit
    brain_hash: str = ""
    brain_version: str = ""
    model_name: str = "claude-sonnet-4-6"

    # Mission tracking
    mission_started_at: str | None = None
    mission_day: int | None = None
    star_count: int | None = None

    # Shadow -> live promotion
    healthy_shadow_days: int = 0

    # Posting caps
    daily_comment_count: int = 0
    daily_comment_date: str = ""

    # Gmail threading
    gmail_thread_message_id: str = ""

    # Health
    last_successful_run_at: str | None = None
    health_status: str = "healthy"
    summary_email_sent: bool = False

    # Run artifacts (populated during execution)
    selected_threads: list = field(default_factory=list)
    drafted_comments: list = field(default_factory=list)
    posted_comments: list = field(default_factory=list)
    observed_replies: list = field(default_factory=list)


def load_state() -> RuntimeState:
    path = MEMORY_DIR / "state.json"
    if not path.exists():
        return RuntimeState()
    data = json.loads(path.read_text())
    return RuntimeState(**{k: v for k, v in data.items() if k in RuntimeState.__dataclass_fields__})


def save_state(state: RuntimeState) -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    path = MEMORY_DIR / "state.json"
    path.write_text(json.dumps(asdict(state), indent=2, default=str) + "\n")


def new_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]


def slot_key(cycle_type: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"{today}:{cycle_type}"


def is_duplicate_slot(state: RuntimeState, cycle_type: str) -> bool:
    return state.cycle_slot_key == slot_key(cycle_type)


def reset_daily_caps(state: RuntimeState) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.daily_comment_date != today:
        state.daily_comment_count = 0
        state.daily_comment_date = today
