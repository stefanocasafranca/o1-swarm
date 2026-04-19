"""Entry point for Doug's runtime.

Usage: python -m agents.doug.run

Loads environment, determines cycle type, checks idempotency,
invokes the appropriate LangGraph pipeline, and saves state.
"""

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env before any other imports that need env vars
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from agents.doug.graph import build_ops_maintenance_graph, build_reddit_hunt_graph
from agents.doug.state import (
    RuntimeState,
    is_duplicate_slot,
    load_state,
    new_run_id,
    reset_daily_caps,
    save_state,
    slot_key,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("doug")

VALID_CYCLES = {"reddit_hunt", "ops_maintenance"}


def main():
    cycle_type = os.environ.get("CYCLE_TYPE", "reddit_hunt")
    if cycle_type not in VALID_CYCLES:
        logger.error(f"Invalid CYCLE_TYPE: {cycle_type}. Must be one of {VALID_CYCLES}")
        sys.exit(1)

    logger.info(f"Starting Doug: cycle_type={cycle_type}")

    # Staleness check: auto-sync brain if vault files changed
    from agents.doug.sync_brain import ensure_fresh
    manifest = ensure_fresh()

    # Load persisted state
    state = load_state()

    # Check idempotency
    if is_duplicate_slot(state, cycle_type):
        logger.info(f"Slot already executed: {state.cycle_slot_key}. Skipping.")
        return

    # Reset daily caps if new day
    reset_daily_caps(state)

    # Record brain version for audit trail
    state.brain_hash = manifest.get("brain_hash", "")
    state.brain_version = manifest.get("brain_version", "")

    # Set run identity
    state.cycle_type = cycle_type
    state.cycle_slot_key = slot_key(cycle_type)
    state.run_id = new_run_id()

    # Track mission day
    if state.mission_started_at is None:
        from datetime import datetime, timezone
        state.mission_started_at = datetime.now(timezone.utc).isoformat()
        state.mission_day = 0
    else:
        from datetime import datetime, timezone
        started = datetime.fromisoformat(state.mission_started_at)
        now = datetime.now(timezone.utc)
        state.mission_day = (now - started).days

    logger.info(f"Run: {state.run_id} | Mode: {state.mode} | Day: {state.mission_day}")

    # Build and invoke the appropriate graph
    if cycle_type == "reddit_hunt":
        graph = build_reddit_hunt_graph()
    else:
        graph = build_ops_maintenance_graph()

    initial_state = {"runtime_state": state}

    try:
        result = graph.invoke(initial_state)
        # Update state from graph result
        if "runtime_state" in result:
            state = result["runtime_state"]

        # Shadow mode: increment healthy days
        if state.mode == "shadow":
            state.healthy_shadow_days += 1

        state.health_status = "healthy"
        logger.info(f"Cycle complete: {state.run_id}")

    except Exception as e:
        logger.error(f"Graph execution failed: {e}")
        state.health_status = "failed"
        if state.mode == "shadow":
            state.healthy_shadow_days = 0

    # Save state
    save_state(state)
    logger.info(f"State saved. Mode: {state.mode} | Stars: {state.star_count}")


if __name__ == "__main__":
    main()
