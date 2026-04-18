"""Sync Doug's brain files from the vault to the runtime repo.

Copies the 7 brain markdown files from s-vault into agents/doug/brain/
and generates a manifest.json with version and integrity hashes.
"""

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

VAULT_BRAIN_DIR = Path.home() / "code" / "s-vault" / "03_projects" / "EOS-Agents" / "swarm" / "Marketing" / "PR"
RUNTIME_BRAIN_DIR = Path(__file__).parent / "brain"

BRAIN_FILES = [
    "SOUL.md",
    "AGENTS.md",
    "HEARTBEAT.md",
    "Mission.md",
    "USER.md",
    "IDENTITY.md",
    "MEMORY.md",
]


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


if __name__ == "__main__":
    print("Syncing brain from vault...")
    sync()
    print("Done.")
