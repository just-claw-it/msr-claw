---
name: msr-claw
description: Human-in-the-loop MSR (mining software repositories) pipeline — LangGraph gates, collection scripts, analysis, paper drafts.
---

# MSR-Claw skill (OpenClaw / workspace)

MSR-Claw is a **Python** tool (separate from OpenClaw’s Node Gateway). Install it on the **same host** where you run shell commands, then drive it via **CLI**, **MCP**, or **`msrclaw.run_service`** in Python.

## Install

```bash
git clone <your-msr-claw-repository-url>
cd msr-claw
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[mcp]"
cp msrclaw.yaml.example msrclaw.yaml
# Set LLM_BASE_URL, LLM_API_KEY, LLM_MODEL in env or yaml
```

## Paths

- Repo root: **copy this skill’s folder** into `~/.openclaw/workspace/skills/msr-claw/` **or** keep the cloned repo and point the user at `MSRCLAW_AGENTS.md`.
- Config: `export MSRCLAW_CONFIG=/absolute/path/to/msrclaw.yaml` when cwd is not the repo.

## Commands

| Goal | Command |
|------|---------|
| CLI run | `msr-claw init "problem statement"` (JSON lines at gates) |
| Resume | `msr-claw resume <run_id>` |
| MCP (Claude Desktop, Cursor, etc.) | `msr-claw mcp` (stdio) |

## MCP tools (when `msr-claw mcp` is configured in the client)

- `msrclaw_start_run` — `problem`
- `msrclaw_resume_run` — `run_id`, `resume` (object with `choice`, optional `rationale`, …)
- `msrclaw_get_snapshot` — `run_id`
- `msrclaw_list_runs` — no args

## Docs in this repository

- `MSRCLAW_AGENTS.md` — full gate JSON and MCP / Python usage  
- `docs/OPENCLAW.md` — how OpenClaw’s Gateway relates to MSR-Claw  

## Safety

Review generated collection scripts before production use.
