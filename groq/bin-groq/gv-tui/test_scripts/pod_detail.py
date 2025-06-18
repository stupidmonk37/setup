#!/usr/bin/env python3

import subprocess
import json
import re
import sys
from collections import defaultdict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.measure import Measurement
from rich.align import Align

from utils import colorize

console = Console()

EXPECTED_POD_COUNTS = {
    "bios-conformance": 9,
    "mcu-comm-server": 9,
    "tspd": 9,
}

REQUIRED_POD_TYPES = set(EXPECTED_POD_COUNTS)


def get_pods_for_node(node):
    try:
        result = subprocess.run(
            ["kubectl", "get", "pods", "--field-selector", f"spec.nodeName={node}", "-o", "json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False
        )
        return json.loads(result.stdout) if result.stdout else {}
    except Exception:
        return {}


def base_name(pod_name: str) -> str:
    return re.sub(r"-[a-z0-9]{5}$", "", pod_name)


def collect_pod_entries(base_nodes):
    entries = []

    for base in base_nodes:
        for i in range(1, 10):
            node = f"{base}-gn{i}"
            pod_data = get_pods_for_node(node)

            for item in pod_data.get("items", []):
                if item.get("status", {}).get("phase") == "Succeeded":
                    continue

                name = item["metadata"]["name"]
                status = item["status"]["phase"]
                node_name = item["spec"]["nodeName"]
                container_statuses = item.get("status", {}).get("containerStatuses", [])

                total = len(container_statuses)
                ready = sum(cs.get("ready") for cs in container_statuses)

                gn_match = re.search(r"c\d+r\d+-gn(\d+)", node_name)
                gn = int(gn_match.group(1)) if gn_match else 0

                entries.append((name, gn, f"{ready}/{total}", status, node_name))

    return sorted(entries, key=lambda x: (x[0], x[1]))


def build_status_table(entries, base_nodes):
    table = Table(title=f"Pod Statuses for: {', '.join(base_nodes)}", header_style="white", show_lines=False)
    table.add_column("NAME", style="cyan", overflow="fold")
    table.add_column("READY", justify="center")
    table.add_column("STATUS", justify="center")
    table.add_column("NODE", justify="center")

    last_base = None
    for name, _, ready, status, node in entries:
        current_base = base_name(name)
        if last_base and current_base != last_base:
            table.add_section()

        table.add_row(name, ready, colorize(status), node)
        last_base = current_base

    return table


def build_summary_panel(entries):
    node_issues = defaultdict(list)
    pods_seen = defaultdict(set)

    for name, _, _, status, node in entries:
        pod_base = base_name(name)

        if pod_base in REQUIRED_POD_TYPES:
            pods_seen[node].add(pod_base)
            if status.lower() != "running":
                node_issues[node].append(f"[yellow]{pod_base} (not running)[/yellow]")

    all_nodes = set(pods_seen.keys()).union(e[4] for e in entries)
    for node in all_nodes:
        missing = REQUIRED_POD_TYPES - pods_seen[node]
        for pod_base in missing:
            node_issues[node].append(f"[red]{pod_base} (missing)[/red]")

    if node_issues:
        lines = [
            f"{node}\n  " + "\n  ".join(issues)
            for node, issues in sorted(node_issues.items())
        ]
        summary_text = Text.from_markup("\n\n".join(lines))
        max_width = max(Measurement.get(console, console.options, Text.from_markup(line)).maximum for line in lines)

        return Panel(
            Align.right(summary_text),
            title="Summary: Pod Issues by Node",
            title_align="center",
            border_style="magenta",
            width=max_width + 4,
        )

    return Panel(
        Align("All expected pods are running on all nodes.", align="right"),
        title="Summary",
        title_align="center",
        border_style="green",
        width=len("All expected pods are running on all nodes.") + 4
    )


def main(base_nodes):
    entries = collect_pod_entries(base_nodes)
    table = build_status_table(entries, base_nodes)
    summary = build_summary_panel(entries)

    console.print(table)
    console.print(summary)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print("[bold red]Usage:[/bold red] ./k_pod_check.py <base-node-prefix> [<base-node-prefix> ...]")
        sys.exit(1)
    main(sys.argv[1:])
