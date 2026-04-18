"""System prompt builder for Doug.

Reads all brain markdown files and concatenates them into
a single system prompt with clear section headers.
"""

from pathlib import Path

BRAIN_DIR = Path(__file__).parent / "brain"

BRAIN_FILES_ORDER = [
    "SOUL.md",
    "IDENTITY.md",
    "AGENTS.md",
    "Mission.md",
    "HEARTBEAT.md",
    "USER.md",
    "MEMORY.md",
]


def build_system_prompt(brain_dir: Path | None = None) -> str:
    brain_dir = brain_dir or BRAIN_DIR
    sections = []

    for fname in BRAIN_FILES_ORDER:
        path = brain_dir / fname
        if not path.exists():
            continue
        label = fname.replace(".md", "").upper()
        content = path.read_text().strip()
        sections.append(f"=== {label} ===\n\n{content}")

    prompt = "\n\n---\n\n".join(sections)

    prompt += "\n\n---\n\n=== RUNTIME CONTEXT ===\n\n"
    prompt += "You are executing inside the o1-swarm runtime.\n"
    prompt += "Your tools are attached. Use them to complete the cycle.\n"
    prompt += "Do NOT use em-dashes anywhere in your output.\n"

    return prompt
