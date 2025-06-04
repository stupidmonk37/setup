# gv_tui maybe?

import asyncio
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer, Input, Button, RichLog, Tabs, Tab

from dashboard_logic import run_dashboard
from render import build_validation_table
from utils import colorize

ENTITY_TYPES = {
    "Nodes": "node",
    "Racks": "rack",
    "Cross-Racks": "crossrack"
}

class StatusDashboard(App):
    CSS_PATH = "dashboard.css"
    TITLE = "Groq Cluster Validation Dashboard"
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Tabs(Tab("Nodes"), Tab("Racks"), Tab("Cross-Racks"))
        yield Container(
            Container(Input(placeholder="Enter entity ID...", id="search-input"),
                      Button("Search", id="search-button"), id="search-controls"),
            RichLog(id="main-output", highlight=True, wrap=False),
            id="main-container"
        )
        yield Footer()

    async def on_mount(self):
        self.active_tab = "Racks"
        self.query_one("#main-output", RichLog).write("Enter an entity ID above and click Search.")

    async def on_tabs_tab_activated(self, event: Tabs.TabActivated):
        self.active_tab = event.tab.label
        self.query_one("#main-output", RichLog).clear()
        self.query_one("#main-output", RichLog).write("Enter an entity ID above and click Search.")

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id != "search-button":
            return

        entity_id = self.query_one("#search-input", Input).value.strip()
        output = self.query_one("#main-output", RichLog)
        output.clear()

        if not entity_id:
            output.write("[yellow]Please enter a valid entity ID.[/yellow]")
            return

        entity_type = ENTITY_TYPES.get(self.active_tab, "rack")

        dashboard = await asyncio.to_thread(run_dashboard, entity_id, entity_type)

        if "error" in dashboard:
            output.write(f"[red]{dashboard['error']}[/red]")
        else:
            table = build_validation_table(dashboard)
            output.write(table)
