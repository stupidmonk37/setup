import asyncio
import re
import contextlib
import time
from datetime import datetime
from functools import lru_cache
from rich.table import Table
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer, Tabs, Tab, RichLog, Input, Button

from data_cluster import is_rack_name, is_xrk_name
from data_cluster import get_data_cluster
from data_rack import display_rack_table
from data_node import build_node_table, display_node_table
from data_crossrack import display_crossrack_table

from utils import COLOR_MAP, STATUS_COLOR_LOOKUP, colorize, kubectl_get_json, extract_rack_prefix, is_node_name, is_rack_name, is_xrk_name, format_timestamp, display_crossrack_table, display_rack_table, build_cluster_table



# ====================================================================================================
# ===== UNIQUE =======================================================================================
# ====================================================================================================
VALIDATION_RULES = {
    "Nodes": (is_rack_name, "Rack", display_node_table),
    "Racks": (is_rack_name, "Rack", display_rack_table),
    "Cross-Racks": (is_xrk_name, "Cross-Rack", display_crossrack_table),
}


TAB_SEARCH_ENABLED = {"Nodes", "Racks", "Cross-Racks"}



# ====================================================================================================
# ===== DETERMINE WHICH TABLE TO PRINT - NODE / RACK / CROSSRACK ==========================DONE=======
# ====================================================================================================
async def table_chooser(output: RichLog, tab: str, entity_ids: list[str]):
    validator, label, _ = VALIDATION_RULES[tab]
    try:
        await render_table(output, tab, entity_ids, label)
    except Exception as e:
        write_message(output, f"❌ Error: {e}", "red")


async def render_table(output: RichLog, tab: str, entity_ids: list[str], label: str):
    if tab == "Nodes":
        results = await asyncio.to_thread(display_node_table, entity_ids, render=False)
    elif tab == "Racks":
        results = await asyncio.to_thread(display_rack_table, entity_ids, render=False)
    elif tab == "Cross-Racks":
        results = await asyncio.to_thread(display_crossrack_table, entity_ids, render=False)
    else:
        return

    if (
        not results
        or not isinstance(results, list)
        or not isinstance(results[0], Table)
    ):
        write_message(output, f"No data found for '{', '.join(entity_ids)}'", "yellow")
        return

    for table in results:
        output.write(table)




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


@lru_cache(maxsize=1)
def cached_get_data_cluster():
    return get_data_cluster()

# ===== APP
class StatusDashboard(App):
    CSS_PATH = "dashboard.css"
    TITLE = "Groq Cluster Validation Dashboard"
    BINDINGS = [("q", "quit", "Quit")]
    refresh_task = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Tabs(Tab("Cluster"), *[Tab(name) for name in VALIDATION_RULES], id="tabs")
        yield Container(
            Container(Input(placeholder="Enter hostname or ID...", id="search-input"),
                      Button("Search", id="search-button", variant="primary"),
                      id="search-container"),
            RichLog(id="main-output", highlight=True, wrap=False),
            id="scrollable-content",
        )
        yield Footer()

    async def on_mount(self):
        self.query_one("#search-container").display = False
        self.query_one("#main-output", RichLog).write("Select a tab ^^^.")
        self.active_tab = "Cluster"
        self.refresh_task = asyncio.create_task(self.refresh_loop())

    async def on_shutdown_request(self):
        if self.refresh_task:
            self.refresh_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.refresh_task

    async def refresh_loop(self):
        while True:
            await asyncio.sleep(60)
            cached_get_data_cluster.cache_clear()
            await self.refresh_active_tab()

    async def refresh_active_tab(self):
        output = self.query_one("#main-output", RichLog)
        if self.active_tab == "Cluster":
            output.clear()
            await self.render_cluster_tab(output)
        elif self.active_tab in TAB_SEARCH_ENABLED:
            input_value = self.query_one("#search-input", Input).value.strip()
            if input_value:
                entity_ids = input_value.split()
                output.clear()
                await table_chooser(output, self.active_tab, entity_ids)

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

        if not input_value:
            write_message(output, "Please enter one or more IDs.")
            return

        error = validate_input(self.active_tab, input_value)
        if error:
            write_message(output, error)
            return

        entity_ids = input_value.split()
        await table_chooser(output, self.active_tab, entity_ids)

    async def render_cluster_tab(self, output: RichLog):
        start = time.perf_counter()
        status = await asyncio.to_thread(cached_get_data_cluster)
        print(f"Cluster status fetched in {time.perf_counter() - start:.2f}s")
        table = build_cluster_table(status)
        output.write(table)






if __name__ == "__main__":
    StatusDashboard().run()
