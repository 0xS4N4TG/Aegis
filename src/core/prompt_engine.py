"""
Prompt engine — templating utilities for building and mutating attack prompts.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any
from jinja2 import Template
from src.templates.loader import TemplateLoader
from src.config import settings


class PromptEngine:
    """High-level prompt building and mutation utilities."""

    def __init__(self) -> None:
        self.loader = TemplateLoader()

    def list_templates(self) -> list[dict[str, Any]]:
        return self.loader.list_templates()

    def render_template(
        self, name: str, target: str, **kwargs: Any
    ) -> str:
        return self.loader.render(name, target_request=target, **kwargs)

    @staticmethod
    def wrap_with_prefix(prompt: str, prefix: str) -> str:
        """Prepend a prefix instruction to any prompt."""
        return f"{prefix}\n\n{prompt}"

    @staticmethod
    def wrap_with_suffix(prompt: str, suffix: str) -> str:
        """Append a suffix to any prompt."""
        return f"{prompt}\n\n{suffix}"

    @staticmethod
    def combine_techniques(prompts: list[str], separator: str = "\n---\n") -> str:
        """Combine multiple prompt techniques into one."""
        return separator.join(prompts)
