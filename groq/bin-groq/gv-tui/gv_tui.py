#! /usr/bin/env python3

import asyncio
import contextlib
import re
import time
from datetime import datetime
from functools import lru_cache
from rich.table import Table
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Tabs, Tab, RichLog, Input, Button

from data_cluster import get_data_cluster
from utils import(
    colorize, is_rack_name, is_xrk_name,
    display_crossrack_table, display_rack_table,
    display_node_table, display_cluster_table,
)


VALIDATION_RULES = {
    "Nodes": (is_rack_name, "Rack", display_node_table),
    "Racks": (is_rack_name, "Rack", display_rack_table),
    "Cross-Racks": (is_xrk_name, "Cross-Rack", display_crossrack_table),
}


TAB_SEARCH_ENABLED = {"Nodes", "Racks", "Cross-Racks"}


async def table_chooser(output: RichLog, tab: str, rack_names: list[str]):
    try:
        if tab == "Nodes":
            results = await asyncio.to_thread(display_node_table, rack_names, render=False)
        elif tab == "Racks":
            results = await asyncio.to_thread(display_rack_table, rack_names, render=False)
        elif tab == "Cross-Racks":
            results = await asyncio.to_thread(display_crossrack_table, rack_names, render=False)
        else:
            write_message(output, "Invalid tab.", "red")
            return

        if (
            not results
            or not isinstance(results, list)
            or not isinstance(results[0], Table)
        ):
            write_message(output, f"No data found for '{', '.join(rack_names)}'", "yellow")
            return

        for table in results:
            output.write(table)

    except Exception as e:
        write_message(output, f"❌ Error: {e}", "red")


def write_message(output: RichLog, text: str, style: str = "yellow"):
    output.write(f"[{style}]{text}[/{style}]")


def validate_input(tab: str, input_value: str):
    if tab not in VALIDATION_RULES:
        return "This tab does not support search."
    validator, label, _ = VALIDATION_RULES[tab]

    for val in input_value.split():
        if not validator(val):
            return f"Invalid {label} format: {val}"
    return None


class StatusDashboard(App):
    CSS_PATH = "dashboard.css"
    TITLE = "Groq Cluster Validation Dashboard"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh")
    ]
    refresh_task = None

    def compose(self) -> ComposeResult:
        yield Tabs(Tab("Cluster"), *[Tab(name) for name in VALIDATION_RULES], id="tabs")
        yield Container(
            Container(Input(placeholder="Enter <rack> or <rack1>-<rack2>...", id="search-input"), Button("Search", variant="primary", id="search-button"), id="search-container"),
            RichLog(highlight=True, wrap=False, id="main-output"), id="scrollable-content",
        )
        yield Footer()

    # 'r' to force refresh
    async def action_refresh(self):
        await self.refresh_active_tab()

    # automatically refresh every 60 seconds
    async def auto_refresh(self):
        while True:
            await asyncio.sleep(60)
            await self.refresh_active_tab()


    async def on_mount(self):
        self.query_one("#search-container").display = False
        self.active_tab = "Cluster"
        self.refresh_task = asyncio.create_task(self.auto_refresh())


    async def refresh_active_tab(self):
        output = self.query_one("#main-output", RichLog)
        if self.active_tab == "Cluster":
            output.clear()
            await self.render_cluster_tab(output)
        elif self.active_tab in TAB_SEARCH_ENABLED:
            input_value = self.query_one("#search-input", Input).value.strip()
            rack_names = input_value.split()
            if rack_names:
                output.clear()
                await table_chooser(output, self.active_tab, rack_names)


    async def on_tabs_tab_activated(self, event: Tabs.TabActivated):
        self.active_tab = event.tab.label
        output = self.query_one("#main-output", RichLog)
        output.clear()

        if self.active_tab in TAB_SEARCH_ENABLED:
            self.query_one("#search-container").display = True
            output.write("Enter a hostname above and click Search.")
        else:
            self.query_one("#search-container").display = False
            await self.render_cluster_tab(output)


    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id != "search-button":
            return

        input_value = self.query_one("#search-input", Input).value.strip()
        output = self.query_one("#main-output", RichLog)
        output.clear()

        rack_names = input_value.split()
        if not rack_names:
            write_message(output, "Please enter one or more rack.")
            return

        error = validate_input(self.active_tab, input_value)
        if error:
            write_message(output, error)
            return

        await table_chooser(output, self.active_tab, rack_names)


    async def render_cluster_tab(self, output: RichLog):
        data = await asyncio.to_thread(get_data_cluster)
        table = display_cluster_table(data, render=False)
        output.write(table)

        # print summary under table
        summary = data.get("summary", {})
        output.write("")
        output.write("Summary:")

        output.write(f"            Rack Total: {summary.get('total_racks', 0)}")
        output.write(f"           Nodes Ready: {summary.get('ready_nodes', 0)}/{summary.get('total_nodes', 0)} " f"({summary.get('ready_ratio', 0.0) * 100:.2f}%)")
        output.write(f"       Validated Racks: {summary.get('racks_complete', 0)}/{summary.get('total_racks', 0)} " f"({summary.get('racks_ratio', 0.0) * 100:.2f}%)")
        output.write(f"  Validated Crossracks: {summary.get('xrk_complete', 0)}/{summary.get('total_racks', 0)} " f"({summary.get('xrk_ratio', 0.0) * 100:.2f}%)")



    async def on_shutdown_request(self):        
        if self.refresh_task:
            self.refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.refresh_task


if __name__ == "__main__":
    StatusDashboard().run()
