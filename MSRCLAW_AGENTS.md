# MSR-Claw — instructions for OpenClaw / coding agents

Use this file when driving **MSR-Claw** from an [OpenClaw](https://github.com/openclaw/openclaw)-compatible assistant, Claude Code, Cursor, or any tool that can run shell commands and read repo docs.

## If you are using OpenClaw (Gateway + agent)

[OpenClaw](https://github.com/openclaw/openclaw) is a **Node.js** assistant: a **Gateway** exposes a **WebSocket** control plane; the agent uses **tools** (often `bash` / `process` on the host) and reads **`AGENTS.md` / skills** under `~/.openclaw/workspace`. It does **not** embed Python projects by default.

**Practical integration:**

1. Install MSR-Claw on the **same host** where OpenClaw’s agent can run shell commands (`pip install -e .`; add `".[mcp]"` if you use MCP).
2. Copy or symlink this file into OpenClaw’s workspace or add a **skill** whose `SKILL.md` summarizes the commands below.
3. Run pipelines via **`msr-claw …`** in the project directory, **or** run **`msr-claw mcp`** and configure your IDE’s MCP client, **or** call **`msrclaw.run_service`** from Python for the same checkpoint logic as the CLI.

Full architecture notes: **`docs/OPENCLAW.md`**. Optional **OpenClaw skill template:** `skills/msr-claw/SKILL.md` (copy into `~/.openclaw/workspace/skills/msr-claw/`).

## What MSR-Claw is

- **Human-in-the-loop** MSR pipeline: LangGraph agents propose RQs, sources, scripts, and drafts; **humans** approve or edit at **gates** (not a single “auto-approve” switch for the whole pipeline).
- **Checkpointed** runs: same `run_id` can be resumed from CLI or MCP.
- **Outputs** live under `workspace_dir` / `runs/<run_id>/` (scripts, data, paper sections, `provenance.db` at workspace root).

## Quick bootstrap (agent checklist)

1. **Clone** this repository and `cd` into it.
2. Create a venv: `python3.11 -m venv .venv` and activate it.
3. **Install:** `pip install -e .` — add `pip install -e ".[mcp]"` for MCP.
4. **Config:** `cp msrclaw.yaml.example msrclaw.yaml` and set `LLM_*` (and `GITHUB_TOKEN` if using GitHub collection).  
   - Or export `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`.
5. **Start a run (CLI):**  
   `msr-claw init "Your MSR problem statement"`  
   At each pause, reply with **one line of JSON** (see below).

## Gate resume JSON (CLI stdin)

The CLI pauses at human gates. Respond with a single JSON object per line, for example:

```json
{"choice":"approve","rationale":"ok"}
```

Common `choice` values:

- Milestone gates: `approve`, `approve_all`, `a`, `abort`, `x`
- Collection recovery (if collection failed): `retry`, `r`, `skip`, `s`

Optional keys when the human edits content (see pipeline code / `resume_apply.py`):

- `rqs` — list of `{ "id", "text" }`
- `candidate_sources` — list of `{ "name", "extra" }` or names
- `approved_source_names` / `sources` — filter sources after the source agent

## MCP (Claude Desktop, Cursor, …)

Install the extra: `pip install -e ".[mcp]"`, then run the **stdio** server:

```bash
msr-claw mcp
```

Configure your MCP client to launch that command (and set `MSRCLAW_CONFIG` if needed). Tools:

- `msrclaw_start_run` — `problem` (string)
- `msrclaw_resume_run` — `run_id`, `resume` (object, e.g. `{"choice":"approve","rationale":"ok"}`)
- `msrclaw_get_snapshot` — `run_id`
- `msrclaw_list_runs` — no arguments  

Responses are **JSON strings** (including error payloads on failure).

## Programmatic Python (same as CLI / MCP)

Use **`msrclaw.run_service`** for `start_run`, `resume_run`, `get_snapshot`, and `list_runs` with the same behavior as the Typer CLI and MCP tools (SQLite checkpoints, provenance). Set `MSRCLAW_CONFIG` or pass `config_path=` to locate `msrclaw.yaml`.

## Testing without an LLM

```bash
export MSRCLAW_MOCK_LLM=1
```

Agents return stub RQs/sources; useful for CI or dry runs.

## Relationship to AutoResearchClaw

[AutoResearchClaw](https://github.com/aiming-lab/AutoResearchClaw) targets **fully autonomous** end-to-end paper generation with many stages. MSR-Claw is **methodology-first**: smaller graph, explicit gates, audit trail. Use ARC for “idea → paper” autonomy; use MSR-Claw when researchers must sign off on RQs, sources, samples, and validity. See `docs/OPENCLAW.md` for a detailed comparison and OpenClaw terminology.

## Safety

- Collection scripts run as **subprocesses** with timeouts; review generated code before trusting production data.
