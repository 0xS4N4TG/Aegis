"""
Report generator — Markdown/HTML/CSV/JSON export of attack results.
"""

from __future__ import annotations

import csv
import json
import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import settings
from src.db.store import ResultStore


class ReportGenerator:
    """Generate reports from stored attack results."""

    def __init__(self, store: ResultStore | None = None) -> None:
        self._store = store or ResultStore()
        self._reports_dir = settings.reports_dir

    async def generate_markdown(
        self,
        *,
        title: str = "LLM Red Team Report",
        limit: int = 200,
    ) -> str:
        """Generate a full Markdown report."""
        stats = await self._store.get_stats()
        attacks = await self._store.get_attacks(limit=limit)
        successes = await self._store.get_attacks(limit=limit, success_only=True)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        lines = [
            f"# {title}",
            f"*Generated: {now}*\n",
            "---\n",
            "## Summary\n",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Attacks | {stats['total_attacks']} |",
            f"| Successful Jailbreaks | {stats['successful_jailbreaks']} |",
            f"| Success Rate | {self._rate(stats)}% |",
            f"| Avg Jailbreak Score | {stats['avg_jailbreak_score']}/100 |",
            "",
            "## Results by Category\n",
            "| Category | Total | Successes | Rate |",
            "|----------|-------|-----------|------|",
        ]

        for cat in stats.get("categories", []):
            total = cat["total"]
            succ = cat["successes"]
            rate = round(succ / total * 100, 1) if total else 0
            lines.append(f"| {cat['category']} | {total} | {succ} | {rate}% |")

        lines.append("\n## Top Successful Techniques\n")
        if successes:
            for i, atk in enumerate(successes[:10], 1):
                lines.append(
                    f"{i}. **{atk['technique']}** — Score: {atk['jailbreak_score']}/100"
                )
        else:
            lines.append("*No successful jailbreaks recorded.*")

        lines.append("\n## Detailed Results\n")
        for atk in attacks[:30]:
            status = "SUCCESS" if not atk["refused"] and atk["jailbreak_score"] >= 50 else "FAILED"
            lines.extend([
                f"### {status} {atk['technique']}",
                f"- **Category:** {atk['category']}",
                f"- **Score:** {atk['jailbreak_score']}/100",
                f"- **Refused:** {'Yes' if atk['refused'] else 'No'}",
                f"- **Model:** {atk['model']}",
                f"- **Duration:** {atk['duration_ms']}ms",
                "",
                "<details><summary>Prompt</summary>\n",
                f"```\n{atk['prompt'][:500]}{'...' if len(atk['prompt']) > 500 else ''}\n```\n</details>\n",
                "<details><summary>Response</summary>\n",
                f"```\n{atk['response'][:500]}{'...' if len(atk['response']) > 500 else ''}\n```\n</details>\n",
                "---\n",
            ])

        return "\n".join(lines)

    async def generate_csv(self, *, limit: int = 500) -> str:
        """Generate CSV export."""
        attacks = await self._store.get_attacks(limit=limit)
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "id", "timestamp", "technique", "category", "model",
                "refused", "jailbreak_score", "harmful_score",
                "policy_bypass", "info_leaked", "api_blocked", "duration_ms",
            ],
        )
        writer.writeheader()
        for atk in attacks:
            writer.writerow({k: atk.get(k, "") for k in writer.fieldnames})
        return output.getvalue()

    async def generate_json(self, *, limit: int = 500) -> str:
        """Generate JSON export."""
        stats = await self._store.get_stats()
        attacks = await self._store.get_attacks(limit=limit)
        return json.dumps({"stats": stats, "attacks": attacks}, indent=2, default=str)

    async def save_report(
        self, fmt: str = "markdown", filename: str | None = None
    ) -> Path:
        """Generate and save a report to disk."""
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        if fmt == "csv":
            content = await self.generate_csv()
            path = self._reports_dir / (filename or f"report_{ts}.csv")
        elif fmt == "json":
            content = await self.generate_json()
            path = self._reports_dir / (filename or f"report_{ts}.json")
        else:
            content = await self.generate_markdown()
            path = self._reports_dir / (filename or f"report_{ts}.md")

        path.write_text(content, encoding="utf-8")
        return path

    @staticmethod
    def _rate(stats: dict) -> float:
        total = stats.get("total_attacks", 0)
        if not total:
            return 0.0
        return round(stats.get("successful_jailbreaks", 0) / total * 100, 1)
