# OpenClaw, “bridge”, and AutoResearchClaw — how MSR-Claw fits

This document clarifies **how [OpenClaw](https://github.com/openclaw/openclaw) is structured**, **terminology**, compares [AutoResearchClaw](https://github.com/aiming-lab/AutoResearchClaw) (ARC), and explains how MSR-Claw fits in.

## How OpenClaw integration actually works (official project)

[OpenClaw](https://github.com/openclaw/openclaw) is a **Node.js** personal assistant (install via `npm install -g openclaw`, `openclaw onboard`, etc.). The architecture described in its README is roughly:

| Piece | Role |
|--------|------|
| **Gateway** | **WebSocket control plane** on loopback (docs/diagrams often use a port such as **18789**). Sessions, channels, tools, and events are coordinated here — not a Python import inside your repo. |
| **Channels** | WhatsApp, Telegram, Slack, Discord, WebChat, and many others feed **inbound** messages into the Gateway. |
| **Agent + tools** | The assistant runs with **first-class tools** (`bash` / `process`, `read`, `write`, browser, canvas, nodes, cron, … — see their [Security](https://github.com/openclaw/openclaw) / sandbox docs). For **main** sessions, tools often run on the **host** where the Gateway runs. |
| **Workspace** | Default workspace under `~/.openclaw/workspace` with injected prompts such as **`AGENTS.md`**, **`SOUL.md`**, **`TOOLS.md`**, plus **skills** under `skills/<skill>/SKILL.md`. |
| **CLI** | `openclaw gateway`, `openclaw agent --message "…"`, `openclaw message send`, etc. |

**Implication for MSR-Claw:** OpenClaw does not ship a built-in “MSR-Claw” binary. Integration is **normal tool use**:

1. **Shell** — The OpenClaw agent runs **`msr-claw`** in a directory where Python, venv, and `msrclaw.yaml` are set up.
2. **Context** — Copy or symlink **`MSRCLAW_AGENTS.md`** into the OpenClaw workspace (or a skill) so the model knows exact commands and gate JSON.
3. **Optional** — Run **`msr-claw mcp`** (stdio) so an MCP-capable client can call **`msrclaw_start_run`** / **`msrclaw_resume_run`**, or import **`msrclaw.run_service`** from Python for the same checkpoint logic.

There is **no requirement** that MSR-Claw speak the Gateway WebSocket protocol natively. A future **thin Node skill** or **MCP server** could wrap the same CLI/API if you want a dedicated tool name inside OpenClaw.

**Docs / site:** [openclaw.ai](https://openclaw.ai) and the repo [README](https://github.com/openclaw/openclaw) (Getting started, Security, Gateway runbook).

## Terminology (easy to confuse)

| Term | What it usually means |
|------|------------------------|
| **OpenClaw** | The assistant / gateway ecosystem ([openclaw/openclaw](https://github.com/openclaw/openclaw)). |
| **Bridge protocol (TCP JSONL)** | **Legacy** node transport in OpenClaw docs. Current builds focus on the **Gateway WebSocket** protocol instead. See [Bridge protocol (legacy)](https://docs.clawd.bot/gateway/bridge-protocol). |
| **ARC `openclaw_bridge` in YAML** | **Optional adapter flags** in AutoResearchClaw (cron, messaging, memory, web fetch, browser, …) — **not** the same as embedding the deprecated TCP bridge server. |
| **“Use OpenClaw with ARC”** | Typically: share the repo + `RESEARCHCLAW_AGENTS.md` so an OpenClaw-driven session can **clone, install, configure, and run** the pipeline — **orchestration via agent**, not necessarily a custom wire protocol in your app. |

MSR-Claw does **not** embed OpenClaw’s legacy TCP bridge. It **does** support **OpenClaw-style workflows** the same way ARC recommends: **documented agent instructions** (`MSRCLAW_AGENTS.md`) plus **MCP** or **Python** (`msrclaw.run_service`) for automation alongside the CLI.

## What AutoResearchClaw does well (and complexity)

ARC aims at **fully autonomous** runs (23 stages): literature from real APIs, sandbox experiments, LaTeX, citation verification layers, peer review, MetaClaw cross-run learning, optional **ACP** backends (Claude Code, Codex CLI, …), and optional **messaging** via OpenClaw-related integrations.

That breadth implies:

- Heavy **dependencies** (Docker/LaTeX optional paths, many adapters).
- **Operational risk**: long runs, many failure modes; ARC adds repair loops, anti-fabrication, verified registries — because autonomy requires it.
- **Different default contract**: “chat an idea → paper” vs “researcher signs off at gates”.

## Limitations / risks in autonomous pipelines (ARC class) — MSR-Claw mitigations

| Risk | Typical symptom | ARC-style response (examples) | MSR-Claw response |
|------|-----------------|--------------------------------|-------------------|
| **Hallucinated or ungrounded claims** | Numbers in paper not tied to runs | VerifiedRegistry, 4-layer citation checks, repair loops | **Mandatory gates** before analysis-heavy writing; **ValidityAgent** + human review; provenance log |
| **Runaway autonomy** | Wrong direction without human catch | PIVOT/REFINE, quality gates | **Human approves** RQs, sources, sample profile, RQ refinement, validity |
| **Opaque methodology** | Hard to reproduce | Deliverables bundle, configs | **Workspace + `provenance.db`**, exported scripts, replication zip |
| **Fragile LLM JSON / code** | Broken collection scripts | Retries, Beast Mode routing | Documented **GPT-4o-class** expectation; collection **timeout + recovery gate**; mock mode for tests |
| **Sandbox escape / data exfil** | Untrusted code in sandbox | Docker policies, AST checks | **Subprocess** collection/analysis (tighten with Docker in roadmap) |

MSR-Claw trades **full autonomy** for **auditability and researcher control** — complementary to ARC, not a drop-in replacement.

## MCP server (optional)

MSR-Claw ships a **stdio** [Model Context Protocol](https://modelcontextprotocol.io) server so Claude Desktop, Cursor, and other MCP clients can call **`msrclaw_start_run`**, **`msrclaw_resume_run`**, etc., without shell scripting:

```bash
pip install -e ".[mcp]"
msr-claw mcp
```

This uses the same Python module as the CLI (`msrclaw.run_service`). Set **`MSRCLAW_CONFIG`** when `msrclaw.yaml` is not discoverable from the cwd.

## What MSR-Claw should add to be “comprehensive” (roadmap)

Inspired by ARC’s surface area, these are **reasonable next steps** (not all are implemented yet):

1. **Citation / claim grounding** — Link paper sentences to `Result` objects and raw artifacts (ARC-style verification is deeper; we can start with structured “evidence IDs”).
2. **Stronger sandboxes** — Docker (or gVisor) for collection/analysis subprocesses; network policies.
3. **LLM fallback chain** — `primary_model` + `fallback_models` in YAML (ARC pattern).
4. **Notifications** — Webhook or messaging when a **gate** fires (ARC’s `use_message` idea), opt-in.
5. **ACP / CLI-agent backends** — Optional routing of some agent steps to ACP (like ARC’s `llm.provider: acp`) for teams without API keys.
6. **Optional cross-run learning** — Pluggable “skills” (MetaClaw-style) **off by default**, like ARC’s MetaClaw bridge.
7. **MCP server** — Shipped: `msr-claw mcp` + `pip install -e ".[mcp]"`. Optional future: SSE transport, OAuth.

## Using MSR-Claw with OpenClaw today

1. On the **same machine** as the Gateway (or any host where the agent’s `bash`/`process` tool runs), install MSR-Claw in a venv and create **`msrclaw.yaml`** (see repo README).
2. Add **`MSRCLAW_AGENTS.md`** to OpenClaw’s **workspace** or a **skill** so the assistant has stable instructions (clone path, venv activate, gate JSON, API table).
3. Prefer one of:
   - **Interactive:** user answers gates in the terminal while chatting with OpenClaw on a channel; or  
   - **Agent-driven:** assistant runs **`msr-claw init "…"`** and supplies JSON lines, **or** uses **MCP** / **`msrclaw.run_service`** for non-interactive steps.

**Tight coupling** (a custom WebSocket client that implements the full Gateway client protocol inside MSR-Claw) is **optional** and large; MSR-Claw stays **transport-agnostic**: OpenAI-compatible LLM HTTP + local files + SQLite checkpoints + MCP or Python for automation.

## References

- **OpenClaw (canonical):** https://github.com/openclaw/openclaw  
- AutoResearchClaw: https://github.com/aiming-lab/AutoResearchClaw  
- Legacy bridge protocol note: https://docs.clawd.bot/gateway/bridge-protocol  
