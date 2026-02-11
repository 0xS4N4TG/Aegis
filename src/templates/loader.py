"""
YAML template loader — reads jailbreak prompt templates from disk
and renders them with Jinja2.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jinja2 import Template

from src.config import settings


class TemplateLoader:
    """Load and render YAML-based jailbreak prompt templates."""

    def __init__(self, templates_dir: Path | None = None) -> None:
        self._dir = templates_dir or settings.templates_dir

    def list_templates(self) -> list[dict[str, Any]]:
        """List all available templates (metadata only, no full prompt)."""
        templates: list[dict[str, Any]] = []
        if not self._dir.exists():
            return templates

        for path in sorted(self._dir.glob("*.yaml")):
            try:
                data = self._load_file(path)
                templates.append(
                    {
                        "file": path.stem,
                        "name": data.get("name", path.stem),
                        "category": data.get("category", "unknown"),
                        "severity": data.get("severity", "medium"),
                        "description": data.get("description", ""),
                        "tags": data.get("tags", []),
                    }
                )
            except Exception:
                continue
        return templates

    def load_template(self, name: str) -> dict[str, Any]:
        """Load a single template by filename (without .yaml extension)."""
        path = self._dir / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Template not found: {path}")
        return self._load_file(path)

    def render(
        self,
        name: str,
        *,
        target_request: str = "",
        model_name: str = "Gemini",
        **extra_vars: Any,
    ) -> str:
        """
        Load a template and render it with Jinja2 variables.

        Args:
            name: Template filename (without .yaml).
            target_request: The harmful request to embed.
            model_name: The model name to reference in persona prompts.
            **extra_vars: Any additional template variables.
        """
        data = self.load_template(name)
        prompt_raw = data.get("prompt", "")

        variables = data.get("variables", {})
        variables.update(
            {
                "target_request": target_request,
                "model_name": model_name,
                **extra_vars,
            }
        )

        template = Template(prompt_raw)
        return template.render(**variables)

    @staticmethod
    def _load_file(path: Path) -> dict[str, Any]:
        """Parse a YAML template file."""
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
