"""
LLM Red Team Platform — Entry point.
"""

from __future__ import annotations

import sys
from src.tui.app import RedTeamApp


def main() -> None:
    """Launch the TUI application."""
    app = RedTeamApp()
    app.run()


if __name__ == "__main__":
    main()
