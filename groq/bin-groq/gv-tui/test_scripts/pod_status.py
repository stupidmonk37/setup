#!/usr/bin/env python3

import subprocess
import json
import re
import argparse
from itertools import product
from collections import defaultdict
from rich.table import Table
from rich.console import Console

ALLOWED_POD_PREFIXES = ["bios-conformance", "mcu-comm-server", "tspd"]

def get_all_pods():
    """Fetch all pods in the groq-system namespace."""
    try:
        output = subprocess.check_output(
            ["kubectl", "get", "pods", "-n", "groq-system", "-o", "json"],
            stderr=subprocess.DEVNULL
        )
        return json.loads(output).get("items", [])
    except subprocess.CalledProcessError:
        return []

def parse_pods(filter_base_nodes=None):
    summary = defaultdict(lambda: defaultdict(dict))
    pod_prefixes = set()

    try:
        output = subprocess.check_output(
            ["kubectl", "get", "pods", "-n", "groq-system", "-o", "json"],
            stderr=subprocess.DEVNULL
        )
        pods = json.loads(output).get("items", [])
    except subprocess.CalledProcessError:
        return summary, []

    ALLOWED_POD_PREFIXES = ["bios-conformance", "mcu-comm-server", "tspd"]

    for pod in pods:
        metadata = pod.get("metadata", {})
        name = metadata.get("name", "")
        node = pod.get("spec", {}).get("nodeName", "")
        status = pod.get("status", {})
        container_statuses = status.get("containerStatuses", [])

        # Expect node like c0r1-gn1
        node_match = re.match(r"^(c\d+r\d+)-(gn\d+)$", node)
        if not node_match:
            continue
        base, gn_node = node_match.groups()

        if filter_base_nodes and base not in filter_base_nodes:
            continue

        if not any(name.startswith(prefix) for prefix in ALLOWED_POD_PREFIXES):
            continue

        pod_prefix = next(prefix for prefix in ALLOWED_POD_PREFIXES if name.startswith(prefix))
        pod_prefixes.add(pod_prefix)

        state_str = "-"
        if container_statuses:
            state_obj = container_statuses[0].get("state", {})
            state_str = next(iter(state_obj.keys()), "-") if state_obj else "-"

        summary[base][pod_prefix][gn_node] = state_str

    return summary, sorted(pod_prefixes)


def summarize_status(pod_states):
    expected_nodes = [f"gn{i}" for i in range(1, 10)]
    missing = [gn for gn in expected_nodes if gn not in pod_states]

    if missing:
        return "Missing: " + ", ".join(missing)

    not_running = [(gn, state) for gn, state in pod_states.items() if state != "running"]
    if not_running:
        return ", ".join(f"{state}: {gn}" for gn, state in not_running)

    return "Running"

def natural_sort_key(hostname):
    match = re.match(r"c(\d+)r(\d+)", hostname)
    if match:
        cnum, rnum = map(int, match.groups())
        return (cnum, rnum)
    return (0, 0)  # fallback in case of unexpected format

def expand_braces(arg):
    # Match patterns like c0r{1..3}
    match = re.match(r"(c\d+r)\{(\d+)\.\.(\d+)\}", arg)
    if match:
        base, start, end = match.groups()
        return [f"{base}{i}" for i in range(int(start), int(end) + 1)]
    else:
        return [arg]


def render_table(summary, pod_prefixes, include_all=False):
    table = Table(show_header=True, header_style="white")
    table.add_column("Rack", style="cyan")

    for prefix in pod_prefixes:
        table.add_column(f"{prefix}", justify="left")

    rows = []

    for base in sorted(summary.keys(), key=natural_sort_key):
        row = [base]
        has_issue = False

        for prefix in pod_prefixes:
            pod_states = summary[base].get(prefix, {})
            status_str = summarize_status(pod_states)
            row.append(status_str)
            if status_str != "Running":
                has_issue = True

        if include_all or has_issue:
            rows.append(row)

    console = Console()
    if rows:
        for row in rows:
            table.add_row(*row)
        console.print(table)
    else:
        console.print("\nAll pods are running 🎉")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check pod statuses by rack.")
    parser.add_argument(
        "--racks",
        nargs="+",
        help="Specify rack hostnames (e.g. c0r1 c1r3) or use brace expansion (e.g. c0r{1..3})"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Show all pod statuses, including those that are fully running"
    )
    args = parser.parse_args()

    if args.racks:
        base_nodes = []
        for arg in args.racks:
            base_nodes.extend(expand_braces(arg))
    else:
        base_nodes = None  # Will fetch all in groq-system

    summary, prefixes = parse_pods(base_nodes)
    render_table(summary, prefixes, include_all=args.all)


