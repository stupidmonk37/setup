#!/usr/bin/env python3

import subprocess
import json
import shutil
import sys
import re
import os

def is_watch():
    """Detect if the script is run under 'watch'."""
    try:
        ppid = os.getppid()
        output = subprocess.check_output(["ps", "-o", "comm=", "-p", str(ppid)], text=True).strip()
        return "watch" in output
    except Exception:
        return False

# Enable ANSI colors
USE_COLOR = sys.stdout.isatty() and not is_watch()

def colorize(text, code):
    return f"\033[{code}m{text}\033[0m" if USE_COLOR else text

GREEN = "92"
RED = "91"

def color_status(value):
    if value == "Success":
        return colorize(value, GREEN)
    return colorize(value or "Missing", RED)

def run_kubectl_get_nodes():
    if not shutil.which("kubectl"):
        raise EnvironmentError("Missing required command: kubectl")
    raw = subprocess.check_output(["kubectl", "get", "nodes", "-o", "json"], text=True)
    return json.loads(raw)

def extract_rack_prefix(name):
    parts = name.split("-")
    if len(parts) < 2 or not parts[1].startswith("gn"):
        return None
    return parts[0]

def strip_ansi(s):
    return re.sub(r'\x1b\[[0-9;]*m', '', s)

def pad(s, width):
    visible = len(strip_ansi(s))
    return s + " " * max(0, width - visible)

def clear_screen():
    if not sys.stdout.isatty():
        print("\033[H\033[J", end="")

def main():
    clear_screen()
    nodes_data = run_kubectl_get_nodes()

    racks = {}
    cross_rack = {}
    rack_to_nodes = {}
    node_health = {}
    node_complete = {}
    rack_complete = {}
    cross_expected = set()

    for node in nodes_data["items"]:
        name = node["metadata"]["name"]
        labels = node["metadata"].get("labels", {})
        conditions = node["status"].get("conditions", [])

        rack = extract_rack_prefix(name)
        if not rack:
            continue

        if rack not in racks:
            racks[rack] = {"node": "Missing", "rack": "Missing"}
            rack_to_nodes[rack] = set()
            rack_complete[rack] = False

        rack_to_nodes[rack].add(name)

        # Track node-complete label
        node_complete[name] = labels.get("validation.groq.io/node-complete") == "true"

        # Track node health
        node_health[name] = any(
            cond["type"] == "Ready" and cond["status"] == "True"
            for cond in conditions
        )

        # Track rack-complete
        if labels.get("validation.groq.io/rack-complete") == "true":
            rack_complete[rack] = True

        # Track cross-rack-complete
        if labels.get("validation.groq.io/cross-rack-complete") == "true":
            try:
                match = re.match(r'(.*?r)(\d+)', rack)
                prefix, num = match.groups()
                next_rack = f"{prefix}{int(num)+1}"
                key = f"{rack}-{next_rack}"
                cross_rack[key] = "Success"
            except (ValueError, AttributeError):
                continue

    # Evaluate per-rack status
    for rack, nodes in rack_to_nodes.items():
        expected = {f"{rack}-gn{i}" for i in range(1, 10)}
        complete = all(node_complete.get(node, False) for node in expected if node in nodes)
        if complete and len(nodes) == 9:
            racks[rack]["node"] = "Success"
        if rack_complete.get(rack):
            racks[rack]["rack"] = "Success"

    def rack_sort_key(r):
        match = re.match(r'(.*?r)(\d+)', r)
        return (match.group(1), int(match.group(2))) if match else (r, 0)

    rack_ids = sorted(racks.keys(), key=rack_sort_key)

    print("+-------------------------------------------------------+")
    print("| Rack    | Node    | Rack    | Cross Rack    | Status  |")
    print("|---------+---------+---------+---------------+---------|")

    for rack in rack_ids:
        node_status = racks[rack]["node"]
        rack_status = racks[rack]["rack"]
        try:
            match = re.match(r'(.*?r)(\d+)', rack)
            prefix, num = match.groups()
            next_rack = f"{prefix}{int(num)+1}"
            cross_key = f"{rack}-{next_rack}"
            cross_expected.add(cross_key)
        except (ValueError, AttributeError):
            cross_key = f"{rack}-?"
        cross_status = cross_rack.get(cross_key, "")
        print(f"| {pad(rack, 7)} | {pad(color_status(node_status), 6)} | {pad(color_status(rack_status), 6)} | {pad(cross_key, 13)} | {pad(color_status(cross_status), 6)} |")

    print("+-------------------------------------------------------+")

    total_racks = len(rack_ids)
    completed_nodes = sum(1 for r in rack_ids if racks[r]["node"] == "Success")
    completed_racks = sum(1 for r in rack_ids if racks[r]["rack"] == "Success")
    completed_cross = len(cross_rack)

    print("\nSummary:")
    print(f"  Nodes:       {completed_nodes * 9}/{total_racks * 9}")
    print(f"  Racks:       {completed_racks}/{total_racks}")
    print(f"  Cross-Rack:  {completed_cross}/{total_racks}")

    # Warnings section
    print("\nWarnings:")

    for rack in rack_ids:
        expected_nodes = {f"{rack}-gn{i}" for i in range(1, 10)}
        found_nodes = rack_to_nodes.get(rack, set())
        missing_nodes = expected_nodes - found_nodes

        if missing_nodes:
            print(f"  Rack {rack} missing {len(missing_nodes)} node(s): {', '.join(sorted(missing_nodes))}")

        for node in sorted(found_nodes):
            if not node_complete.get(node, False):
                print(f"  Node {node} missing 'validation.groq.io/node-complete=true'")
            if not node_health.get(node, True):
                print(f"  Node {node} not Ready.")

        if not rack_complete.get(rack, False):
            print(f"  Rack {rack} missing 'validation.groq.io/rack-complete=true'")

    # Expected cross-racks that are not marked as complete
    for cross_key in sorted(cross_expected):
        if cross_key not in cross_rack:
            print(f"  Cross-rack {cross_key} missing 'validation.groq.io/cross-rack-complete=true'")

if __name__ == "__main__":
    main()
