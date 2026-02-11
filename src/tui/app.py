"""
Main TUI Application — LLM Red Team Platform.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Rule,
    Select,
    Static,
)

from src.config import settings
from src.core.attack_orchestrator import (
    AttackOrchestrator,
    ALL_ATTACK_CLASSES,
    get_attacks_by_category,
)
from src.core.gemini_client import GeminiClient
from src.core.iterative import IterativeOrchestrator
from src.db.store import ResultStore
from src.reporting.generator import ReportGenerator


# ── ASCII Banner ────────────────────────────────────────────────

BANNER = r"""
 ██▀███  ▓█████ ▓█████▄    ▄▄▄█████▓▓█████  ▄▄▄       ███▄ ▄███▓
▓██ ▒ ██▒▓█   ▀ ▒██▀ ██▌   ▓  ██▒ ▓▒▓█   ▀ ▒████▄    ▓██▒▀█▀ ██▒
▓██ ░▄█ ▒▒███   ░██   █▌   ▒ ▓██░ ▒░▒███   ▒██  ▀█▄  ▓██    ▓██░
▒██▀▀█▄  ▒▓█  ▄ ░▓█▄   ▌   ░ ▓██▓ ░ ▒▓█  ▄ ░██▄▄▄▄██ ▒██    ▒██
░██▓ ▒██▒░▒████▒░▒████▓      ▒██▒ ░ ░▒████▒  ▓█   ▓██▒▒██▒   ░██▒
░ ▒▓ ░▒▓░░░ ▒░ ░ ▒▒▓  ▒      ▒ ░░   ░░ ▒░ ░  ▒▒   ▓▒█░░ ▒░   ░  ░
  ░▒ ░ ▒░ ░ ░  ░ ░ ▒  ▒        ░     ░ ░  ░   ▒   ▒▒ ░░  ░      ░
   ▒   ▒    ░    ░              ░       ░      ░   ▒      ░
   ░        ░    ░                      ░          ░         ░
"""


class RedTeamApp(App):
    """LLM Red Team Platform — Textual TUI Application."""

    TITLE = "LLM Red Team Platform"
    CSS_PATH = "styles/app.tcss"

    BINDINGS = [
        Binding("d", "show_dashboard", "Dashboard", show=True),
        Binding("a", "show_attack", "Attack", show=True),
        Binding("u", "show_auto", "Auto-Attack", show=True),
        Binding("r", "show_results", "Results", show=True),
        Binding("c", "show_catalog", "Catalog", show=True),
        Binding("e", "show_reports", "Export", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.store = ResultStore()
        self.report_gen = ReportGenerator(self.store)
        self._current_view = "dashboard"

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            # Sidebar
            with Vertical(id="sidebar"):
                yield Label("RED TEAM", classes="title")
                yield Rule()
                yield Button("Dashboard", id="btn-dashboard", variant="default")
                yield Button("Attack", id="btn-attack", variant="default")
                yield Button("Auto-Attack", id="btn-auto", variant="warning")
                yield Button("Results", id="btn-results", variant="default")
                yield Button("Catalog", id="btn-catalog", variant="default")
                yield Button("Export", id="btn-reports", variant="default")
                yield Rule()
                yield Label("", id="status-label", classes="subtitle")

            # Main content
            with Vertical(id="content"):
                yield Static(BANNER, id="banner", classes="success-text")
                yield Label("LLM Red Teaming Platform", classes="title")
                yield Label(
                    f"Model: {settings.gemini_model} | "
                    f"API: {'Configured' if settings.validate_api_key() else 'Not Set'}",
                    classes="subtitle",
                )
                yield Rule()

                # Dashboard stats
                with Horizontal(id="dash-stats"):
                    yield Static("Loading...", id="stat-total", classes="stat-box")
                    yield Static("Loading...", id="stat-success", classes="stat-box")
                    yield Static("Loading...", id="stat-rate", classes="stat-box")
                    yield Static("Loading...", id="stat-avg", classes="stat-box")

                # Attack panel (hidden initially)
                with Vertical(id="attack-panel"):
                    yield Label("Launch Attack", classes="title")
                    yield Label("Target Topic (harmful request to test):", classes="subtitle")
                    yield Input(
                        placeholder="e.g., how to pick a lock",
                        id="target-input",
                    )
                    yield Label("Target Model:", classes="subtitle")
                    yield Select(
                        [(m, m) for m in settings.available_models],
                        id="model-select",
                        value=settings.gemini_model,
                        allow_blank=False,
                    )
                    yield Label("Attack Technique:", classes="subtitle")
                    yield Select(
                        [(f"{cls().name} [{cls().category.value}]", cls().name) for cls in ALL_ATTACK_CLASSES],
                        id="attack-select",
                        prompt="Select attack technique...",
                    )
                    yield Horizontal(
                        Button("Launch Single", id="btn-launch", variant="success"),
                        Button("Run All Attacks", id="btn-launch-all", variant="warning"),
                        Button("Run Category", id="btn-launch-cat", variant="default"),
                    )
                    yield Rule()
                    yield Label("Attack Log:", classes="subtitle")
                    yield RichLog(id="attack-log", wrap=True, markup=True)

                # Auto-Attack panel (hidden initially)
                with Vertical(id="auto-panel"):
                    yield Label("Auto-Iterative Attack (PAIR-Lite)", classes="title")
                    yield Label("Target Topic:", classes="subtitle")
                    yield Input(
                        placeholder="e.g., how to create a phishing email",
                        id="auto-target-input",
                    )
                    yield Horizontal(
                        Vertical(
                            Label("Target Model:", classes="subtitle"),
                            Select(
                                [(m, m) for m in settings.available_models],
                                id="auto-target-model",
                                value=settings.gemini_model,
                                allow_blank=False,
                            ),
                        ),
                        Vertical(
                            Label("Attacker Model (Optimizer):", classes="subtitle"),
                            Select(
                                [(m, m) for m in settings.available_models],
                                id="auto-attacker-model",
                                value="gemini-2.5-flash", 
                                allow_blank=False,
                            ),
                        ),
                    )
                    yield Button("Start Optimization", id="btn-start-auto", variant="error")
                    yield Rule()
                    yield Label("Optimization Log:", classes="subtitle")
                    yield RichLog(id="auto-log", wrap=True, markup=True)

                # Results panel (hidden initially)
                with Vertical(id="results-panel"):
                    yield Label("Attack Results", classes="title")
                    yield DataTable(id="results-table")

                # Catalog panel (hidden initially)
                with Vertical(id="catalog-panel"):
                    yield Label("Jailbreak Catalog", classes="title")
                    yield DataTable(id="catalog-table")

                # Reports panel (hidden initially)
                with Vertical(id="reports-panel"):
                    yield Label("Export Reports", classes="title")
                    yield Horizontal(
                        Button("Markdown", id="btn-export-md"),
                        Button("CSV", id="btn-export-csv"),
                        Button("JSON", id="btn-export-json"),
                    )
                    yield RichLog(id="report-log", wrap=True, markup=True)

        yield Footer()

    async def on_mount(self) -> None:
        """Initialize on startup."""
        await self.store.init_db()
        self._show_view("dashboard")
        await self._refresh_dashboard()
        self._populate_catalog()

    # ── View switching ──────────────────────────────────────────

    def _show_view(self, view: str) -> None:
        """Show one panel, hide others."""
        self._current_view = view
        panels = {
            "dashboard": ["dash-stats", "banner"],
            "attack": ["attack-panel"],
            "auto": ["auto-panel"],
            "results": ["results-panel"],
            "catalog": ["catalog-panel"],
            "reports": ["reports-panel"],
        }
        all_ids = {pid for pids in panels.values() for pid in pids}

        for pid in all_ids:
            try:
                widget = self.query_one(f"#{pid}")
                widget.display = pid in panels.get(view, [])
            except Exception:
                pass

    def action_show_dashboard(self) -> None:
        self._show_view("dashboard")
        asyncio.create_task(self._refresh_dashboard())

    def action_show_attack(self) -> None:
        self._show_view("attack")

    def action_show_auto(self) -> None:
        self._show_view("auto")

    def action_show_results(self) -> None:
        self._show_view("results")
        asyncio.create_task(self._refresh_results())

    def action_show_catalog(self) -> None:
        self._show_view("catalog")

    def action_show_reports(self) -> None:
        self._show_view("reports")

    # ── Button handlers ─────────────────────────────────────────

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button.id

        if btn == "btn-dashboard":
            self.action_show_dashboard()
        elif btn == "btn-attack":
            self.action_show_attack()
        elif btn == "btn-auto":
            self.action_show_auto()
        elif btn == "btn-results":
            self.action_show_results()
        elif btn == "btn-catalog":
            self.action_show_catalog()
        elif btn == "btn-reports":
            self.action_show_reports()
        elif btn == "btn-launch":
            await self._run_single_attack()
        elif btn == "btn-launch-all":
            await self._run_all_attacks()
        elif btn == "btn-launch-cat":
            await self._run_category_attacks()
        elif btn == "btn-start-auto":
            await self._run_auto_attack()
        elif btn == "btn-export-md":
            await self._export_report("markdown")
        elif btn == "btn-export-csv":
            await self._export_report("csv")
        elif btn == "btn-export-json":
            await self._export_report("json")

    # ── Dashboard ───────────────────────────────────────────────

    async def _refresh_dashboard(self) -> None:
        stats = await self.store.get_stats()
        total = stats["total_attacks"]
        success = stats["successful_jailbreaks"]
        rate = round(success / total * 100, 1) if total else 0
        avg = stats["avg_jailbreak_score"]

        self.query_one("#stat-total", Static).update(
            f"[bold green]TOTAL[/]\n{total}"
        )
        self.query_one("#stat-success", Static).update(
            f"[bold green]SUCCESS[/]\n{success}"
        )
        self.query_one("#stat-rate", Static).update(
            f"[bold green]RATE[/]\n{rate}%"
        )
        self.query_one("#stat-avg", Static).update(
            f"[bold green]AVG SCORE[/]\n{avg}/100"
        )

    # ── Attack execution ────────────────────────────────────────

    async def _run_single_attack(self) -> None:
        target = self.query_one("#target-input", Input).value.strip()
        # Allow empty target for generic attacks or pure template testing
        if not target:
            target = "(No topic provided)"


        if not settings.validate_api_key():
            self._log_attack("[red]Error: Set GEMINI_API_KEY in .env file![/]")
            return

        select = self.query_one("#attack-select", Select)
        if select.value is Select.BLANK:
            self._log_attack("[red]Error: Select an attack technique![/]")
            return

        attack_name = select.value
        attack_cls = None
        for cls in ALL_ATTACK_CLASSES:
            if cls().name == attack_name:
                attack_cls = cls
                break

        if not attack_cls:
            self._log_attack(f"[red]Attack not found: {escape(attack_name)}[/]")
            return

        target_model = self.query_one("#model-select", Select).value

        self._log_attack(f"[yellow]Launching: {escape(attack_name)} against {escape(target_model)}[/]")

        orchestrator = AttackOrchestrator(store=self.store, client=GeminiClient(model_name=target_model))
        await orchestrator.init()

        result = await orchestrator.run_attack(
            attack_cls(),
            target,
            on_progress=self._log_attack,
        )

        if result.success:
            self._log_attack(f"[bold green]JAILBREAK SUCCESS — Score: {result.jailbreak_score}/100[/]")
        else:
            self._log_attack(f"[bold red]DEFENDED — Score: {result.jailbreak_score}/100[/]")

        # Escape the response to ensure brackets don't break markup parsing
        self._log_attack(f"\n[bold]Response:[/]\n[italic]{escape(result.response_received)}[/]\n")
        self._log_attack(f"[dim]{'-'*50}[/]")

    async def _run_all_attacks(self) -> None:
        target = self.query_one("#target-input", Input).value.strip()
        if not target:
             target = "(No topic provided)"
        if not settings.validate_api_key():
            self._log_attack("[red]Error: Set GEMINI_API_KEY in .env file![/]")
            return

        target_model = self.query_one("#model-select", Select).value
        self._log_attack(f"[bold yellow]Running ALL attacks against {escape(target_model)}...[/]")
        orchestrator = AttackOrchestrator(store=self.store, client=GeminiClient(model_name=target_model))
        await orchestrator.init()
        results = await orchestrator.run_all(
            target, on_progress=self._log_attack
        )
        successes = sum(1 for r in results if r.success)
        self._log_attack(
            f"\n[bold]{'='*50}[/]\n"
            f"[bold green]Completed: {len(results)} attacks | "
            f"Successes: {successes} | "
            f"Rate: {round(successes/len(results)*100,1) if results else 0}%[/]"
        )

    async def _run_category_attacks(self) -> None:
        target = self.query_one("#target-input", Input).value.strip()
        if not target:
             target = "(No topic provided)"

        select = self.query_one("#attack-select", Select)

        if select.value is Select.BLANK:
            self._log_attack("[red]Select a technique to determine category![/]")
            return

        attack_name = select.value
        selected_cat = None
        for cls in ALL_ATTACK_CLASSES:
            inst = cls()
            if inst.name == attack_name:
                selected_cat = inst.category.value
                break

        if not selected_cat:
            return

        by_cat = get_attacks_by_category()
        attacks = [cls() for cls in by_cat.get(selected_cat, [])]
        target_model = self.query_one("#model-select", Select).value
        self._log_attack(f"[yellow]Running {len(attacks)} {selected_cat} attacks against {escape(target_model)}...[/]")

        orchestrator = AttackOrchestrator(store=self.store, client=GeminiClient(model_name=target_model))
        await orchestrator.init()
        results = await orchestrator.run_batch(
            attacks, target, on_progress=self._log_attack
        )
        successes = sum(1 for r in results if r.success)
        self._log_attack(f"[green]Category done: {successes}/{len(results)} success[/]")

    async def _run_auto_attack(self) -> None:
        target_topic = self.query_one("#auto-target-input", Input).value.strip()
        if not target_topic:
            self._log_auto("[red]Error: Enter a target topic![/]")
            return

        target_model_name = self.query_one("#auto-target-model", Select).value
        attacker_model_name = self.query_one("#auto-attacker-model", Select).value

        self._log_auto(f"[bold yellow]Starting Auto-Attack on '{escape(target_topic)}'[/]")
        self._log_auto(f"Target: {escape(target_model_name)} | Optimizer: {escape(attacker_model_name)}")

        target_client = GeminiClient(model_name=target_model_name)
        attacker_client = GeminiClient(model_name=attacker_model_name)
        
        orchestrator = IterativeOrchestrator(
            target_client=target_client,
            attacker_client=attacker_client,
            store=self.store
        )

        try:
            await orchestrator.run_optimization(
                target_topic,
                max_turns=5,
                on_progress=self._log_auto
            )
            self._log_auto("[bold green]Optimization loop completed.[/]")
        except Exception as e:
            self._log_auto(f"[red]Error during optimization: {escape(str(e))}[/]")

    def _log_auto(self, msg: str) -> None:
        try:
            log = self.query_one("#auto-log", RichLog)
            log.write(msg)
        except Exception:
            pass

    def _log_attack(self, msg: str) -> None:
        try:
            log = self.query_one("#attack-log", RichLog)
            log.write(msg)
        except Exception as e:
            # Fallback for logging errors so we don't just swallow them silently
            # We can't easily log to the UI if it failed, but we can try writing raw text without markup or printing
            try:
                log = self.query_one("#attack-log", RichLog)
                log.write(f"[red]Log error: {str(e)}[/]")
            except:
                pass


    # ── Results table ───────────────────────────────────────────

    async def _refresh_results(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.clear(columns=True)
        table.add_columns(
            "Status", "Technique", "Category", "Score", "Model", "Time"
        )

        attacks = await self.store.get_attacks(limit=100)
        for atk in attacks:
            status = "Success" if not atk["refused"] and atk["jailbreak_score"] >= 50 else "Defended"
            table.add_row(
                status,
                atk["technique"][:30],
                atk["category"],
                f"{atk['jailbreak_score']}/100",
                atk["model"],
                f"{atk['duration_ms']}ms",
            )

    # ── Catalog ─────────────────────────────────────────────────

    def _populate_catalog(self) -> None:
        table = self.query_one("#catalog-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Name", "Category", "Severity", "Tags")

        for cls in ALL_ATTACK_CLASSES:
            inst = cls()
            table.add_row(
                inst.name[:35],
                inst.category.value,
                getattr(inst, "severity", "medium") if isinstance(getattr(inst, "severity", ""), str) else inst.severity.value,
                ", ".join(getattr(inst, "tags", [])[:3]),
            )

    # ── Reports ─────────────────────────────────────────────────

    async def _export_report(self, fmt: str) -> None:
        log = self.query_one("#report-log", RichLog)
        log.write(f"[yellow]Generating {fmt} report...[/]")
        try:
            path = await self.report_gen.save_report(fmt=fmt)
            log.write(f"[green]Saved: {path}[/]")
        except Exception as e:
            log.write(f"[red]Error: {e}[/]")
