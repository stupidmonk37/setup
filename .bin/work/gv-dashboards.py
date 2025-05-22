#!/usr/bin/env python3

import os
import sys
import subprocess
import json
import argparse
import shutil
import re
from concurrent.futures import ThreadPoolExecutor

# -------- ANSI COLOR SUPPORT -------- #
def supports_color():
    return sys.stdout.isatty() and os.environ.get("TERM", "") not in ("dumb", "")

USE_COLOR = supports_color()
GREEN = "\033[92m" if USE_COLOR else ""
RED = "\033[91m" if USE_COLOR else ""
YELLOW = "\033[93m" if USE_COLOR else ""
RESET = "\033[0m" if USE_COLOR else ""

# -------- HELPER UTILITIES -------- #
def strip_ansi(s):
    return re.sub(r'\x1b\[[0-9;]*m', '', s)

def pad(s, width):
    visible = len(strip_ansi(s))
    return s + " " * max(0, width - visible)

def colorize_status(status, width=9):
    color_map = {
        "success": GREEN,
        "failure": RED,
    }
    text = status if status else "N/A"
    color = color_map.get(text.lower(), YELLOW)
    colored = f"{color}{text}{RESET}"
    return pad(colored,width)

def kubectl_get_json(resource, name=None):
    cmd = ["kubectl", "get", resource]
    if name:
        cmd.append(name)
    cmd.extend(["-o", "json"])
    return json.loads(subprocess.check_output(cmd, text=True))

def parse_node_name(name):
    match = re.match(r"(.*?)-gn(\d+)", name)
    return match.groups() if match else (None, None)

def extract_rack_prefix(name):
    parts = name.split("-")
    return parts[0] if len(parts) >= 2 and parts[1].startswith("gn") else None

# This checks the status of k8s nodes and racks, 
# and reports missing or NotReady nodes and labels.
# Specifically, "gv-dashboard.py --cluster, -c" is looking for the following:

# node=READY
# validation.groq.io/node-complete=true ### This needs to be true on all 9 nodes in a rack
# validation.groq.io/rack-complete=true
# validation.groq.io/cross-rack-complete=true

# If the above are missing, a detailed report of which node/rack/xrk that has 
# missing items will be generated at the bottom of the table. ie:

# Rack c1r2 missing 2 node(s): c1r2-gn4, c1r2-gn9
# Node c1r2-gn1 missing 'validation.groq.io/node-complete=true'
# Node c1r2-gn3 not Ready.
# Rack c1r2 missing 'validation.groq.io/rack-complete=true'
# Cross-rack c1r2-c1r3 missing 'validation.groq.io/cross-rack-complete=true'



# -------- CLUSTER DASHBOARD -------- #
def run_cluster_dashboard(only_warnings=False):
    def is_watch_mode():
        try:
            ppid = os.getppid()
            parent = subprocess.check_output(["ps", "-o", "comm=", "-p", str(ppid)], text=True).strip()
            return "watch" in parent
        except Exception:
            return False

    use_color = sys.stdout.isatty() and not is_watch_mode()

    def color_status(value):
        return colorize_status(value, 7)

    if not shutil.which("kubectl"):
        raise EnvironmentError("Missing required command: kubectl")

    clear_screen()
    data = kubectl_get_json("nodes")

    racks, rack_to_nodes = {}, {}
    node_complete, rack_complete, cross_rack = {}, {}, {}
    cross_expected = set()

    for node in data["items"]:
        name = node["metadata"]["name"]
        labels = node["metadata"].get("labels", {})
        conditions = node["status"].get("conditions", [])
        rack = extract_rack_prefix(name)
        if not rack:
            continue

        racks.setdefault(rack, {"node": "Missing", "rack": "Missing"})
        rack_to_nodes.setdefault(rack, set()).add(name)
        node_complete[name] = labels.get("validation.groq.io/node-complete") == "true"
        rack_complete[rack] = labels.get("validation.groq.io/rack-complete") == "true"
        healthy = any(c["type"] == "Ready" and c["status"] == "True" for c in conditions)
        node_complete[name] &= healthy

        if labels.get("validation.groq.io/cross-rack-complete") == "true":
            match = re.match(r"(.*?r)(\d+)", rack)
            if match:
                prefix, num = match.groups()
                next_rack = f"{prefix}{int(num) + 1}"
                cross_rack[f"{rack}-{next_rack}"] = "Success"

    for rack, nodes in rack_to_nodes.items():
        expected = {f"{rack}-gn{i}" for i in range(1, 10)}
        if all(node_complete.get(n, False) for n in expected if n in nodes) and len(nodes) == 9:
            racks[rack]["node"] = "Success"
        if rack_complete.get(rack):
            racks[rack]["rack"] = "Success"

    def rack_sort(r):
        m = re.match(r"(.*?r)(\d+)", r)
        return (m.group(1), int(m.group(2))) if m else (r, 0)

    rack_ids = sorted(racks.keys(), key=rack_sort)
    print("+-------------------------------------------------------+")
    print("| Rack    | Node    | Rack    | Cross Rack    | Status  |")
    print("|---------+---------+---------+---------------+---------|")

    for rack in rack_ids:
        node_status = racks[rack]["node"]
        rack_status = racks[rack]["rack"]
        match = re.match(r"(.*?r)(\d+)", rack)
        prefix, num = match.groups() if match else (rack, "?")
        next_rack = f"{prefix}{int(num) + 1}" if num != "?" else "?"
        cross_key = f"{rack}-{next_rack}"
        cross_expected.add(cross_key)
        cross_status = cross_rack.get(cross_key, "N/A")

        if only_warnings:
            statuses = [node_status, rack_status, cross_status]
            if all(s == "Success" for s in statuses):  # Ignore empty statuses
                continue

        print(f"| {pad(rack, 7)} | {color_status(node_status)} | {color_status(rack_status)} | {pad(cross_key, 13)} | {color_status(cross_status)} |")

    print("+-------------------------------------------------------+")
    total_racks = len(rack_ids)
    total_nodes = len(node_complete)
    ready_nodes = sum(1 for n, ready in node_complete.items() if ready)
    print(f"\nSummary:\n  Nodes:       {ready_nodes}/{total_nodes}")
    print(f"  Racks:       {sum(racks[r]['rack']=='Success' for r in rack_ids)}/{total_racks}")
    print(f"  Cross-Rack:  {len(cross_rack)}/{total_racks}")

    if not only_warnings:
        total_racks = len(rack_ids)
        total_nodes = len(node_complete)
        ready_nodes = sum(1 for n, ready in node_complete.items() if ready)
        print(f"\nSummary:\n  Nodes:       {ready_nodes}/{total_nodes}")
        print(f"  Racks:       {sum(racks[r]['rack']=='Success' for r in rack_ids)}/{total_racks}")
        print(f"  Cross-Rack:  {len(cross_rack)}/{total_racks}")

    warnings_found = False
    warnings_output = []

    for rack in rack_ids:
        expected = {f"{rack}-gn{i}" for i in range(1, 10)}
        found = rack_to_nodes[rack]
        for node in sorted(found):
            if not node_complete.get(node, False):
                warnings_output.append(f"  Node {node} NotReady")
                warnings_found = True
        if expected - found:
            warnings_output.append(f"  Rack {rack} missing nodes: {', '.join(sorted(expected - found))}")
            warnings_found = True
        if not rack_complete.get(rack, False):
            warnings_output.append(f"  Rack {rack} missing 'validation.groq.io/rack-complete=true' label")
            warnings_found = True

    for cross_key in sorted(cross_expected - cross_rack.keys()):
        warnings_output.append(f"  Cross-rack {cross_key} missing 'validation.groq.io/cross-rack-complete=true' label")
        warnings_found = True

    print("\nWarnings:")
    if warnings_found:
        print("\n".join(warnings_output))
    elif only_warnings:
        print("🎉 All nodes are ready and validation labels present! 🎉")

def clear_screen():
    if sys.stdout.isatty():
        print("\033[H\033[J", end="")

# This checks the status of validations for nodes, rack or cross-rack.
# It doesn't tell you what tests should exist, rather which tests have
# actually been run on the given argument. 

# Usage:
# gv-dashboards.py --nodes, -n <rack>
# gv-dashboards.py --rack, -r <rack>
# gv-dashboards.py --cross-rack, -x <rack1>-<rack2>

# -------- NODE/RACK/CROSS-RACK VIEWS -------- #
def run_validation_dashboard(entity_type, ids, header_suffix):
    COL_WIDTH = 88

    for entity in ids:
        try:
            data = kubectl_get_json("gv", entity)
        except subprocess.CalledProcessError as e:
            print(f"{RED}❌ Error fetching {entity}:{RESET} {e.stderr.strip()}")
            continue

        validations = data.get("status", {}).get("validations", {})
        title = f"{entity} -- {header_suffix} Tests"

        print("+" + "-" * (COL_WIDTH + 13) + "+")
        print(f"|{title.center(COL_WIDTH + 13)}|")
        print("+" + "-" * (COL_WIDTH + 2) + "+" + "-" * 10 + "+")

        if not validations:
            print(f"| {'No validations found.':<{COL_WIDTH + 10}} |")
            print("+" + "-" * (COL_WIDTH + 2) + "+" + "-" * 10 + "+")
            continue

        for vname, phases in validations.items():
            print(f"| {vname:<{COL_WIDTH}} |  Status  |")
            print("+" + "-" * (COL_WIDTH + 2) + "+" + "-" * 10 + "+")
            for pname, pdata in phases.items():
                status = pdata.get("results", [{}])[0].get("status", "N/A") if isinstance(pdata, dict) else "N/A"
                print(f"| {pname:<{COL_WIDTH}} | {colorize_status(status, 8)} |")
            print("+" + "-" * (COL_WIDTH + 2) + "+" + "-" * 10 + "+")

def run_node_dashboard(rack_names):
    NODE_COUNT = 9
    TABLE_WIDTH = 129

    for prefix in rack_names:
        full_nodes = [f"{prefix}-gn{i}" for i in range(1, NODE_COUNT + 1)]
        validations = {}

        with ThreadPoolExecutor(max_workers=NODE_COUNT) as ex:
            results = ex.map(lambda n: (n, kubectl_get_json("gv", n).get("status", {}).get("validations", {})), full_nodes)

        for node, vdata in results:
            for test, data in vdata.items():
                validations.setdefault(test, {})[node] = data.get(node, {})

        print("+" + "-" * TABLE_WIDTH + "+")
        print("|" + f"{prefix} -- Node Tests".center(TABLE_WIDTH) + "|")
        print("+" + "-" * TABLE_WIDTH + "+")
        short_names = [f"gn{i}" for i in range(1, NODE_COUNT + 1)]
        print("| Test / Node:                          |" + "".join(f" {n:^7} |" for n in short_names))
        print("+" + "-" * 39 + "+" + ("-" * 9 + "+") * NODE_COUNT)


        for test, nodes in validations.items():
            row = f"| {test:<37} |"
            for short in short_names:
                full = f"{prefix}-{short}"
                status = nodes.get(full, {}).get("results", [{}])[0].get("status", "N/A")
                row += colorize_status(status) + "|"
            print(row)

        print("+" + "-" * TABLE_WIDTH + "+")

# -------- ARGUMENT PARSING -------- #
def validate_rack_name(value):
    if not re.match(r"^[a-z]+\d+r\d+$", value):
        raise argparse.ArgumentTypeError("Single rack only (e.g. c1r1)")
    return value

def validate_cross_rack(value):
    if not re.match(r"^[a-z]+\d+r\d+-[a-z]+\d+r\d+$", value):
        raise argparse.ArgumentTypeError("Format must be <rack>-<rack> (e.g. c0r1-c0r2)")
    return value

def main():
    class CustomHelpFormatter(argparse.HelpFormatter):
        def _format_args(self, action, default_metavar):
            return action.metavar

    parser = argparse.ArgumentParser(description="Validation Dashboard for Groq Clusters", usage="gv-dashboards.py [--cluster] [--only-warnings] [--nodes <rack>] [--rack <rack>] [--cross-rack <rack1>-<rack2>] [<rack> ...]", formatter_class=lambda prog: CustomHelpFormatter(prog, max_help_position=40))
    parser.add_argument("rack_name", nargs="*", metavar="<rack>", help="One or more rack names (e.g., c1r1, c1r1-c1r2, or c1r{1..2})")
    parser.add_argument("--cluster", "-c", action="store_true", help="View the cluster-wide dashboard")
    parser.add_argument("--only-warnings", action="store_true", help="Only show warnings in the cluster view (requires --cluster)")
    parser.add_argument("--nodes", "-n", nargs="+", type=validate_rack_name, metavar="<rack>", help="View node-level validation status (multiple allowed)")
    parser.add_argument("--rack", "-r", nargs="+", type=validate_rack_name, metavar="<rack>", help="View rack-level validation status (multiple allowed)")
    parser.add_argument("--cross-rack", "-x", nargs="+", type=validate_cross_rack, metavar="<rack1>-<rack2>", help="View cross-rack validation status (multiple allowed)")

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    if args.only_warnings and not args.cluster:
        parser.error("--only-warnings can only be used with --cluster")

    if args.cluster:
        run_cluster_dashboard(only_warnings=args.only_warnings)
    if args.nodes:
        run_node_dashboard(args.nodes)
    if args.rack:
        run_validation_dashboard("rack", args.rack, "Rack")
    if args.cross_rack:
        run_validation_dashboard("cross-rack", args.cross_rack, "Cross-Rack")

if __name__ == "__main__":
    main()
