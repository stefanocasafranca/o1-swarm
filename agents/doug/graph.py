"""Deterministic LangGraph orchestration for Doug.

Two pipelines: reddit_hunt and ops_maintenance.
LLM is bounded to exactly 2 decision points (rank and draft).
No ReAct loop. No open-ended tool-use at the top level.
Control flow is pure code.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from agents.doug.policy import (
    check_post_policy,
    check_shadow_promotion,
    filter_candidates,
    load_posted_urls,
)
from agents.doug.prompts import build_system_prompt
from agents.doug.reporting import build_summary_email
from tools.github_stars import check_github_stars
from tools.gmail_tool import send_gmail
from tools.reddit_posting import post_reddit_comment
from tools.reddit_search import search_reddit
from tools.serpapi_discovery import search_serpapi

logger = logging.getLogger(__name__)

MEMORY_DIR = Path(__file__).parent.parent.parent / "memory" / "doug"


class DougState(TypedDict, total=False):
    """Typed state for the Doug graph. All keys optional for partial updates."""
    runtime_state: Any
    system_prompt: str
    posted_urls: set
    recent_metrics: list
    errors: list
    # reddit_hunt keys
    serpapi_candidates: list
    praw_candidates: list
    threads_found: int
    merged_candidates: list
    filtered_candidates: list
    ranked_candidates: list
    threads_ranked: int
    drafted_comments: list
    drafts_created: int
    post_policy: dict
    comments_posted: int
    # ops_maintenance keys
    star_result: dict
    pace: dict
    conversion_updates: list
    campaign_summary: str


def _get_llm(model: str = "claude-sonnet-4-6"):
    return ChatAnthropic(model=model, temperature=0, max_tokens=4096)


def _extract_json_array(text: str) -> list:
    """Robustly extract a JSON array from LLM output."""
    import re

    # Find the outermost [...] block (greedy)
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if not match:
        return []

    raw = match.group()

    # Try parsing as-is first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Fix common LLM JSON issues: unescaped newlines inside strings
    # Replace literal newlines inside strings with \n
    fixed = re.sub(r'(?<=": ")(.*?)(?="[,\}\]])', lambda m: m.group().replace('\n', '\\n'), raw, flags=re.DOTALL)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Last resort: try to find individual JSON objects
    objects = []
    for obj_match in re.finditer(r'\{[^{}]*\}', raw, re.DOTALL):
        try:
            objects.append(json.loads(obj_match.group()))
        except json.JSONDecodeError:
            continue
    return objects


# --- SHARED NODES ---

def load_context(state: DougState) -> dict:
    """Deterministic: load brain, memory, and recent context. No LLM call."""
    system_prompt = build_system_prompt()

    # Load recent posted comments for dedup
    posted_urls = load_posted_urls()

    # Load recent metrics for context
    metrics_path = MEMORY_DIR / "metrics.jsonl"
    recent_metrics = []
    if metrics_path.exists():
        lines = metrics_path.read_text().strip().split("\n")
        for line in lines[-5:]:
            if line:
                recent_metrics.append(json.loads(line))

    return {
        "system_prompt": system_prompt,
        "posted_urls": posted_urls,
        "recent_metrics": recent_metrics,
        "errors": [],
    }


def finalize_run(state: DougState) -> dict:
    """Deterministic: write run artifact, send summary email."""
    runtime_state = state.get("runtime_state")
    if not runtime_state:
        logger.error("finalize_run: no runtime_state in graph state")
        return {}

    now = datetime.now(timezone.utc)

    # Write run artifact
    run_dir = MEMORY_DIR / "runs" / now.strftime("%Y-%m-%d")
    run_dir.mkdir(parents=True, exist_ok=True)
    artifact = {
        "run_id": runtime_state.run_id,
        "cycle_type": runtime_state.cycle_type,
        "mode": runtime_state.mode,
        "model": runtime_state.model_name,
        "brain_hash": runtime_state.brain_hash,
        "timestamp": now.isoformat(),
        "threads_found": state.get("threads_found", 0),
        "threads_ranked": state.get("threads_ranked", 0),
        "drafts_created": state.get("drafts_created", 0),
        "comments_posted": state.get("comments_posted", 0),
        "star_count": runtime_state.star_count,
        "errors": state.get("errors", []),
    }
    artifact_path = run_dir / f"{runtime_state.run_id}.json"
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n")
    logger.info(f"Run artifact written: {artifact_path}")

    # Check shadow promotion
    if check_shadow_promotion(runtime_state):
        runtime_state.mode = "live"
        logger.info("PROMOTED: shadow -> live")

    # Update health
    runtime_state.last_successful_run_at = now.isoformat()
    runtime_state.health_status = "healthy"

    # Send summary email
    email_data = build_summary_email(runtime_state, {
        "threads_found": state.get("threads_found", 0),
        "threads_ranked": state.get("threads_ranked", 0),
        "drafts_created": state.get("drafts_created", 0),
        "comments_posted": state.get("comments_posted", 0),
        "errors": state.get("errors", []),
    })

    try:
        send_gmail.invoke({
            "subject": email_data["subject"],
            "body": email_data["body"],
        })
        runtime_state.summary_email_sent = True
        logger.info("Summary email sent")
    except Exception as e:
        logger.error(f"Summary email failed: {e}")
        runtime_state.summary_email_sent = False

    return {"runtime_state": runtime_state}


# --- REDDIT HUNT PIPELINE ---

def collect_candidates(state: DougState) -> dict:
    """Run SerpApi (primary) and PRAW (fallback) discovery in sequence."""
    keywords = "CLI tool developer workflow automation build script"

    serpapi_results = []
    praw_results = []
    errors = list(state.get("errors", []))

    try:
        serpapi_results = search_serpapi.invoke({"keywords": keywords})
    except Exception as e:
        logger.warning(f"SerpApi failed: {e}")
        errors.append(f"SerpApi: {e}")

    try:
        praw_results = search_reddit.invoke({"keywords": keywords})
    except Exception as e:
        logger.warning(f"PRAW failed: {e}")
        errors.append(f"PRAW: {e}")

    return {
        "serpapi_candidates": serpapi_results,
        "praw_candidates": praw_results,
        "threads_found": len(serpapi_results) + len(praw_results),
        "errors": errors,
    }


def merge_and_dedup(state: DougState) -> dict:
    """Deterministic: merge SerpApi + PRAW results, dedup by URL."""
    serpapi = state.get("serpapi_candidates", [])
    praw = state.get("praw_candidates", [])

    seen_urls = set()
    merged = []

    # SerpApi first (primary, higher quality ranking)
    for c in serpapi:
        url = c.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            merged.append(c)

    # PRAW second (fallback, catches fresh threads)
    for c in praw:
        url = c.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            merged.append(c)

    return {"merged_candidates": merged}


def policy_filter(state: DougState) -> dict:
    """Deterministic: apply allowlist, caps, age, dedup filters."""
    candidates = state.get("merged_candidates", [])
    posted_urls = state.get("posted_urls", set())
    runtime_state = state.get("runtime_state")

    filtered = filter_candidates(candidates, runtime_state, posted_urls)
    return {"filtered_candidates": filtered}


def rank_candidates_llm(state: DougState) -> dict:
    """LLM node (bounded, single call): rank filtered candidates."""
    candidates = state.get("filtered_candidates", [])
    if not candidates:
        return {"ranked_candidates": [], "threads_ranked": 0}

    system_prompt = state.get("system_prompt", "")
    llm = _get_llm()

    candidates_text = json.dumps(candidates[:15], indent=2)
    prompt = (
        "Rank these Reddit threads by how well BUILD_SCRIPT answers the poster's question. "
        "Return a JSON array of the top 5 thread URLs, ordered best to worst. "
        "Only include threads where BUILD_SCRIPT is a genuine, helpful answer.\n\n"
        f"Candidates:\n{candidates_text}"
    )

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ])

        # Parse ranked URLs from response
        ranked_urls = _extract_json_array(response.content)

        # Map back to full candidate objects
        url_to_candidate = {c["url"]: c for c in candidates}
        ranked = [url_to_candidate[u] for u in ranked_urls if u in url_to_candidate]

        return {"ranked_candidates": ranked, "threads_ranked": len(ranked)}

    except Exception as e:
        logger.error(f"Ranking failed: {e}")
        errors = list(state.get("errors", []))
        errors.append(f"Ranking LLM: {e}")
        return {"ranked_candidates": candidates[:5], "threads_ranked": len(candidates[:5]), "errors": errors}


def draft_comments_llm(state: DougState) -> dict:
    """LLM node (bounded, single call): draft comments for top threads."""
    ranked = state.get("ranked_candidates", [])
    if not ranked:
        return {"drafted_comments": [], "drafts_created": 0}

    system_prompt = state.get("system_prompt", "")
    llm = _get_llm()

    threads_text = json.dumps(ranked[:5], indent=2)
    prompt = (
        "Draft a genuine, helpful Reddit comment for each of these threads. "
        "The comment should answer the poster's question and naturally mention BUILD_SCRIPT "
        "(https://github.com/stefanocasafranca/build-script) as a solution where relevant. "
        "Write in Stefano's voice: confident, warm, value-first. "
        "No em-dashes. Keep each comment under 200 words. "
        "Return ONLY a valid JSON array of objects with 'thread_url' and 'comment_body'. "
        "Use \\n for newlines inside strings. No markdown code fences.\n\n"
        f"Threads:\n{threads_text}"
    )

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ])

        drafts = _extract_json_array(response.content)

        # Persist drafts
        now = datetime.now(timezone.utc)
        draft_dir = MEMORY_DIR / "drafts" / now.strftime("%Y-%m-%d")
        draft_dir.mkdir(parents=True, exist_ok=True)
        draft_path = draft_dir / f"drafts-{now.strftime('%H%M%S')}.json"
        draft_path.write_text(json.dumps(drafts, indent=2) + "\n")

        return {"drafted_comments": drafts, "drafts_created": len(drafts)}

    except Exception as e:
        logger.error(f"Drafting failed: {e}")
        errors = list(state.get("errors", []))
        errors.append(f"Drafting LLM: {e}")
        return {"drafted_comments": [], "drafts_created": 0, "errors": errors}


def apply_post_policy(state: DougState) -> dict:
    """Deterministic: check mode, caps, and decide whether to post."""
    runtime_state = state.get("runtime_state")
    drafts = state.get("drafted_comments", [])
    policy_result = check_post_policy(runtime_state, len(drafts))
    return {"post_policy": policy_result}


def post_comments(state: DougState) -> dict:
    """Post approved comments to Reddit."""
    policy = state.get("post_policy", {})
    drafts = state.get("drafted_comments", [])
    runtime_state = state.get("runtime_state")

    if not policy.get("allowed"):
        return {"comments_posted": 0}

    max_posts = policy.get("count", 0)
    posted = 0
    errors = list(state.get("errors", []))

    for draft in drafts[:max_posts]:
        try:
            result = post_reddit_comment.invoke({
                "thread_url": draft["thread_url"],
                "comment_body": draft["comment_body"],
            })
            if result.get("status") == "posted":
                posted += 1
                runtime_state.daily_comment_count += 1
        except Exception as e:
            logger.error(f"Post failed: {e}")
            errors.append(f"Posting: {e}")

    return {"comments_posted": posted, "runtime_state": runtime_state, "errors": errors}


# --- OPS MAINTENANCE PIPELINE ---

def check_stars(state: DougState) -> dict:
    """Deterministic: fetch star count and log metrics."""
    try:
        result = check_github_stars.invoke({})
        runtime_state = state.get("runtime_state")
        if runtime_state and "stars" in result:
            runtime_state.star_count = result["stars"]
            logger.info(f"Star count: {result['stars']}")
        return {"star_result": result, "runtime_state": runtime_state}
    except Exception as e:
        logger.error(f"Star check failed: {e}")
        errors = list(state.get("errors", []))
        errors.append(f"Stars: {e}")
        return {"star_result": {"error": str(e)}, "errors": errors}


def evaluate_pace(state: DougState) -> dict:
    """Deterministic: compare pace to target."""
    star_result = state.get("star_result", {})
    return {
        "pace": {
            "current": star_result.get("stars", 0),
            "target": star_result.get("target", 200),
            "daily_rate": star_result.get("daily_rate", 0),
            "days_to_target": star_result.get("days_to_target"),
        }
    }


def conversion_surfaces(state: DougState) -> dict:
    """Deterministic: check if repo metadata needs updates."""
    # Placeholder for Phase 2 repo optimization
    return {"conversion_updates": []}


def summarize_llm(state: DougState) -> dict:
    """LLM node (optional): generate narrative campaign summary."""
    pace = state.get("pace", {})
    system_prompt = state.get("system_prompt", "")
    llm = _get_llm()

    prompt = (
        f"Current stars: {pace.get('current', 0)}. "
        f"Target: {pace.get('target', 200)}. "
        f"Daily rate: {pace.get('daily_rate', 0)}. "
        f"Estimated days to target: {pace.get('days_to_target', 'unknown')}. "
        "Write a 3-sentence campaign health assessment. No em-dashes."
    )

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ])
        return {"campaign_summary": response.content}
    except Exception as e:
        logger.error(f"Summary failed: {e}")
        return {"campaign_summary": f"Summary generation failed: {e}"}


# --- GRAPH BUILDERS ---

def _route_after_policy(state: DougState) -> str:
    policy = state.get("post_policy", {})
    if policy.get("allowed"):
        return "post_comments"
    return "finalize_run"


def build_reddit_hunt_graph():
    graph = StateGraph(DougState)
    graph.add_node("load_context", load_context)
    graph.add_node("collect_candidates", collect_candidates)
    graph.add_node("merge_and_dedup", merge_and_dedup)
    graph.add_node("policy_filter", policy_filter)
    graph.add_node("rank_candidates_llm", rank_candidates_llm)
    graph.add_node("draft_comments_llm", draft_comments_llm)
    graph.add_node("apply_post_policy", apply_post_policy)
    graph.add_node("post_comments", post_comments)
    graph.add_node("finalize_run", finalize_run)

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "collect_candidates")
    graph.add_edge("collect_candidates", "merge_and_dedup")
    graph.add_edge("merge_and_dedup", "policy_filter")
    graph.add_edge("policy_filter", "rank_candidates_llm")
    graph.add_edge("rank_candidates_llm", "draft_comments_llm")
    graph.add_edge("draft_comments_llm", "apply_post_policy")
    graph.add_conditional_edges("apply_post_policy", _route_after_policy, {
        "post_comments": "post_comments",
        "finalize_run": "finalize_run",
    })
    graph.add_edge("post_comments", "finalize_run")
    graph.add_edge("finalize_run", END)

    return graph.compile()


def build_ops_maintenance_graph():
    graph = StateGraph(DougState)
    graph.add_node("load_context", load_context)
    graph.add_node("check_stars", check_stars)
    graph.add_node("evaluate_pace", evaluate_pace)
    graph.add_node("conversion_surfaces", conversion_surfaces)
    graph.add_node("summarize_llm", summarize_llm)
    graph.add_node("finalize_run", finalize_run)

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "check_stars")
    graph.add_edge("check_stars", "evaluate_pace")
    graph.add_edge("evaluate_pace", "conversion_surfaces")
    graph.add_edge("conversion_surfaces", "summarize_llm")
    graph.add_edge("summarize_llm", "finalize_run")
    graph.add_edge("finalize_run", END)

    return graph.compile()
