# CLAUDE.md

## Vault Sync

vault_project: ~/code/s-vault/03_projects/o1-agents/
tier: 2

### How Sync Works (Tier 2: Autonomous)
This repo runs autonomously via GitHub Actions. Brain files are synced from the vault via `sync_brain.py`.
- `ensure_fresh()` checks sha256 hashes on every cron cycle
- If vault brain files changed, runtime auto-re-syncs before executing
- Brain files live in `agents/doug/brain/` (synced copies, do not edit directly)

### Interactive Session Rules
When working in this repo interactively (not via cron):
1. Read the vault dashboard frontmatter at the vault_project path above
2. Run `git log --oneline --since=[last_vault_update from frontmatter]` in this repo
3. If vault is stale relative to code changes, update the vault dashboard
4. Brain file edits go in the VAULT (`~/code/s-vault/03_projects/o1-agents/agents/doug/`), not in this repo's `brain/` folder

### Session End
Before ending this session:
1. Update the vault dashboard with any changes: architecture decisions, bugs fixed, features added
2. Update `last_vault_update` in dashboard frontmatter to today's date
3. Run `python -m agents.doug.sync_brain` if vault brain files were modified

### Conflict Detection
If vault says one thing and the code shows another, present both and ask to resolve.

## Project Context
o1-swarm is the runtime for Stefano's personal agent swarm. Doug (PR agent for BUILD_SCRIPT, targeting 200 GitHub stars) is the first agent. Architecture: LangGraph deterministic pipelines, GitHub Actions cron, Gmail reporting.
