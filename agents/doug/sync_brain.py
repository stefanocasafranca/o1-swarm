"""Sync Doug's brain files from the vault to the runtime repo.

Copies brain markdown files and YAML contracts from s-vault into
agents/doug/brain/ and generates a manifest.json with version and
integrity hashes.

Staleness check: call is_stale() to compare manifest hashes against
vault source files without copying. Returns True if any file changed.
"""

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

VAULT_BRAIN_DIR = Path.home() / "code" / "s-vault" / "03_projects" / "o1-agents" / "agents" / "doug"
RUNTIME_BRAIN_DIR = Path(__file__).parent / "brain"

BRAIN_FILES = [
    # Narrative (human-facing)
    "SOUL.md",
    "AGENTS.md",
    "HEARTBEAT.md",
    "Mission.md",
    "USER.md",
    "IDENTITY.md",
    "MEMORY.md",
    # Contracts (machine-facing)
    "agent.contract.yaml",
    "tool_policy.yaml",
    "memory_policy.yaml",
    "heartbeat.yaml",
]


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_stale() -> bool:
    """Check if synced brain copies are stale vs. vault source files.

    Returns True if any vault file has changed since last sync,
    or if manifest.json does not exist.
    """
    manifest_path = RUNTIME_BRAIN_DIR / "manifest.json"
    if not manifest_path.exists():
        return True

    manifest = json.loads(manifest_path.read_text())
    stored_hashes = manifest.get("files", {})

    for fname in BRAIN_FILES:
        src = VAULT_BRAIN_DIR / fname
        if not src.exists():
            continue
        current_hash = hash_file(src)
        if stored_hashes.get(fname) != current_hash:
            return True

    return False


def sync():
    RUNTIME_BRAIN_DIR.mkdir(parents=True, exist_ok=True)

    file_hashes = {}
    for fname in BRAIN_FILES:
        src = VAULT_BRAIN_DIR / fname
        dst = RUNTIME_BRAIN_DIR / fname
        if not src.exists():
            print(f"WARNING: {src} not found, skipping")
            continue
        shutil.copy2(src, dst)
        file_hashes[fname] = hash_file(dst)
        print(f"  synced {fname}")

    combined = "".join(file_hashes.get(f, "") for f in BRAIN_FILES)
    brain_hash = hashlib.sha256(combined.encode()).hexdigest()

    manifest = {
        "brain_version": datetime.now(timezone.utc).isoformat(),
        "brain_hash": f"sha256:{brain_hash}",
        "source_root": str(VAULT_BRAIN_DIR),
        "files": {f: file_hashes[f] for f in BRAIN_FILES if f in file_hashes},
    }

    manifest_path = RUNTIME_BRAIN_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"  manifest written: {brain_hash[:12]}...")
    return manifest


def ensure_fresh():
    """Auto-sync if stale. Call this at the start of every run."""
    if is_stale():
        print("Brain is stale, re-syncing...")
        return sync()
    else:
        print("Brain is fresh.")
        manifest_path = RUNTIME_BRAIN_DIR / "manifest.json"
        return json.loads(manifest_path.read_text())


if __name__ == "__main__":
    print("Syncing brain from vault...")
    sync()
    print("Done.")
