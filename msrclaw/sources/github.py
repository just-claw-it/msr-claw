"""GitHub: REST API collection script (minimal reproducible sample)."""

from __future__ import annotations

import os
import textwrap

from msrclaw.pipeline.state import ResearchQuestion, Script, SourceConfig
from msrclaw.sources.base import AvailabilityReport, BaseSource


class GitHubSource(BaseSource):
    name = "github"
    description = "GitHub REST API (search repositories, issues) using a token"
    required_credentials = ("GITHUB_TOKEN",)

    def validate_credentials(self, config: SourceConfig) -> bool:
        token = (config.extra or {}).get("api_key") or os.environ.get("GITHUB_TOKEN", "")
        return bool(token and token.strip())

    def llm_prompt_hints(self, config: SourceConfig) -> str:
        return """GitHub REST API (https://api.github.com). Authenticate with header:
Authorization: Bearer <token> from os.environ.get("GITHUB_TOKEN","").
Accept: application/vnd.github+json. User-Agent required.
Common endpoints: GET /search/repositories, /search/issues, /repos/{owner}/{repo}/...
Choose search queries, qualifiers (language:, stars:, etc.), and pagination appropriate
to the stated research problem — not a generic demo query."""

    def estimate_availability(self, rqs: list[ResearchQuestion], config: SourceConfig) -> AvailabilityReport:
        ok = self.validate_credentials(config)
        if not ok:
            return AvailabilityReport(
                summary="No GitHub token configured. Set GITHUB_TOKEN or sources.github.api_key in msrclaw.yaml.",
                complexity="high",
            )
        return AvailabilityReport(
            summary="GitHub API is suitable for repository/issue-level MSR queries; rate limits apply.",
            estimated_rows="depends on query volume",
            complexity="medium",
            notes={"api": "https://api.github.com"},
        )

    def generate_collection_script(
        self,
        rqs: list[ResearchQuestion],
        config: SourceConfig,
        *,
        raw_out_dir: str,
    ) -> Script:
        token_expr = (config.extra or {}).get("api_key") or "${GITHUB_TOKEN}"
        if isinstance(token_expr, str) and token_expr.startswith("${") and token_expr.endswith("}"):
            env_name = token_expr[2:-1]
            token_py = f"os.environ.get({env_name!r}, '')"
        else:
            token_py = repr(str(token_expr))

        # Minimal script: search repos for a keyword derived from the first RQ, write JSONL.
        rq_text = (rqs[0].text if rqs else "msr").replace('"', '\\"')
        body = f"""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

RAW_OUT = {raw_out_dir!r}
TOKEN = {token_py}
KEYWORD = re.sub(r"\\\\s+", " ", "{rq_text}")[:80]

def main() -> None:
    os.makedirs(RAW_OUT, exist_ok=True)
    out_path = os.path.join(RAW_OUT, "github_repos.jsonl")
    if not TOKEN:
        raise SystemExit("Missing GitHub token (GITHUB_TOKEN).")
    q = urllib.parse.quote(KEYWORD + " in:name,description")
    url = f"https://api.github.com/search/repositories?q={{q}}&per_page=10"
    req = urllib.request.Request(
        url,
        headers={{
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {{TOKEN}}",
            "User-Agent": "msr-claw-collector",
        }},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    items = data.get("items") or []
    with open(out_path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\\n")
    print(f"Wrote {{len(items)}} items to {{out_path}}")

if __name__ == "__main__":
    main()
"""
        body = textwrap.dedent(body).lstrip()
        return Script(name="collect_github.py", path="", language="python", content=body)
