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
BLUE = "\033[94m" if USE_COLOR else ""

# -------- HELPER UTILITIES -------- #
def strip_ansi(s):
    return re.sub(r'\x1b\[[0-9;]*m', '', s)

def pad(s, width):
    visible = len(strip_ansi(s))
    return s + " " * max(0, width - visible)

def colorize_status(status, css_class=None, width=16):
    raw = str(status)
    color_map = {
        "success": GREEN,
        "failure": RED,
        "warning(s)": RED,
        "failed-retryable": RED,
        "in progress": BLUE,
        "notready": RED,
        "not started": YELLOW,
        "pending": YELLOW,
        "info": YELLOW,
        "fault": RED,
    }
    if not USE_COLOR:
        return pad(raw, width)
    if css_class is None:
        css_class = raw.lower()
    color = color_map.get(css_class, RESET)
    return pad(f"{color}{raw}{RESET}", width)

def kubectl_get_json(resource, name=None):
    cmd = ["kubectl", "get", resource]
    if name:
        cmd.append(name)
    cmd.extend(["-o", "json"])
    return json.loads(subprocess.check_output(cmd, text=True))

def extract_rack_prefix(name):
    parts = name.split("-")
    return parts[0] if len(parts) >= 2 and parts[1].startswith("gn") else None

def determine_phase_status(pdata):
    phase = pdata.get("phase")
    results = pdata.get("results", [{}])
    result_status = results[0].get("status", None)
    faults = results[0].get("faults", [])
    report_url = results[0].get("reportURL", "")
    if phase == "finished" and result_status == "success":
        return "Success"
    elif faults:
        fault_types = sorted({f.get("fault_type", "Unknown") for f in faults})
        status_text = ", ".join(fault_types)
        tooltip = "\n".join(
            f"{f['fault_type']}: {f['component_type']} at {f['component']}"
            for f in faults
        )
        return status_text, tooltip, "fault"
    elif phase == "started":
        return "In progress"
    elif phase == "finished":
        return result_status or "Failed"
    else:
        return "Pending"

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

def run_cluster_dashboard(only_warnings=False, suppress_warnings=False):
    TABLE_WIDTH = 84
    TOP_COLUMN = 18
    RACK_WIDTH = 7
    XRK_WIDTH = 15
    VALUE_WIDTH = 16
    TOP_BORDER_LINE = f"+{'-' * TABLE_WIDTH}+"

    def is_watch_mode():
        try:
            ppid = os.getppid()
            parent = subprocess.check_output(["ps", "-o", "comm=", "-p", str(ppid)], text=True).strip()
            return "watch" in parent
        except Exception:
            return False

    use_color = sys.stdout.isatty() and not is_watch_mode()

    if not shutil.which("kubectl"):
        raise EnvironmentError("Missing required command: kubectl")

    clear_screen()
    data = kubectl_get_json("nodes")

    racks, rack_to_nodes = {}, {}
    node_complete, rack_complete, cross_rack = {}, {}, {}
    node_issues = {}
    warning_summary = {}
    cross_expected = set()

    for node in data["items"]:
        name = node["metadata"]["name"]
        labels = node["metadata"].get("labels", {})
        conditions = node["status"].get("conditions", [])
        rack = extract_rack_prefix(name)
        if not rack:
            continue

        racks.setdefault(rack, {"node": "Missing Label", "rack": "Missing Label"})
        rack_to_nodes.setdefault(rack, set()).add(name)

        healthy = any(c["type"] == "Ready" and c["status"] == "True" for c in conditions)
        label_complete = labels.get("validation.groq.io/node-complete") == "true"
        is_complete = healthy and label_complete
        node_complete[name] = is_complete

        # Collect issues per node
        issues = []
        if not healthy:
            issues.append("NotReady")
        if not label_complete:
            issues.append("Missing Label")
        if issues:
            node_issues[name] = "; ".join(issues)

        if labels.get("validation.groq.io/rack-complete") == "true":
            rack_complete[rack] = True

        if labels.get("validation.groq.io/cross-rack-complete") == "true":
            match = re.match(r"(.*?r)(\d+)", rack)
            if match:
                prefix, num = match.groups()
                next_rack = f"{prefix}{int(num) + 1}"
                cross_rack[f"{rack}-{next_rack}"] = "Success"

    for rack, nodes in rack_to_nodes.items():
        expected = {f"{rack}-gn{i}" for i in range(1, 10)}
        issues = {n: node_issues[n] for n in expected if n in node_issues}

        if expected == nodes and not issues:
            racks[rack]["node"] = "Success"
        else:
            if issues:
                racks[rack]["node"] = "WARNING(S)"
                detail = ", ".join(f"{n} ({reason})" for n, reason in sorted(issues.items()))
                warning_summary[rack] = detail
            else:
                racks[rack]["node"] = "Missing Nodes"

        # Determine rack status
        if rack_complete.get(rack):
            racks[rack]["rack"] = "Success"
        elif racks[rack]["node"] == "Success":
            racks[rack]["rack"] = "In progress"
        else:
            racks[rack]["rack"] = "Missing Label"

    def rack_sort(r):
        m = re.match(r"(.*?r)(\d+)", r)
        return (m.group(1), int(m.group(2))) if m else (r, 0)

    rack_ids = sorted(racks.keys(), key=rack_sort)
    print(TOP_BORDER_LINE)
    print(f"| {'Rack':^{RACK_WIDTH}} | {'Node':^{VALUE_WIDTH}} | {'Rack':^{VALUE_WIDTH}} | {'Cross-rack':^{XRK_WIDTH}} | {'Status':^{VALUE_WIDTH}} |")
    print(TOP_BORDER_LINE)

    for rack in rack_ids:
        node_status = racks[rack]["node"]
        rack_status = racks[rack]["rack"]
        match = re.match(r"(.*?r)(\d+)", rack)
        prefix, num = match.groups() if match else (rack, "?")
        next_rack = f"{prefix}{int(num) + 1}" if num != "?" else "?"
        cross_key = f"{rack}-{next_rack}"
        cross_expected.add(cross_key)

        cross_status = cross_rack.get(cross_key)
        if not cross_status:
            if node_status == "Success" and rack_status == "Success":
                cross_status = "In progress"
            else:
                cross_status = "Missing Label"

        if only_warnings:
            statuses = [node_status, rack_status, cross_status]
            if all(s == "Success" for s in statuses):
                continue

        print(f"| {pad(rack, 7)} | {colorize_status(node_status)} | {colorize_status(rack_status)} | {pad(cross_key, 15)} | {colorize_status(cross_status)} |")

    print(TOP_BORDER_LINE)

    total_racks = len(rack_ids)
    total_nodes = len(node_complete)
    ready_nodes = sum(1 for n, ready in node_complete.items() if ready)
    print(f"\nSummary:\n  Nodes:       {ready_nodes}/{total_nodes}")
    print(f"  Racks:       {sum(racks[r]['rack']=='Success' for r in rack_ids)}/{total_racks}")
    print(f"  Cross-Rack:  {len(cross_rack)}/{total_racks}")

    warnings_found = False
    warnings_output = []

    if warning_summary and not suppress_warnings:
        print("\nWARNINGS:")
        hostname_pattern = re.compile(r'\b[\w-]+-gn\d+\b')  # Matches hostnames like c1r2-gn4

        for rack, detail in sorted(warning_summary.items()):
            def yellowize_hostname(match):
                return f"{YELLOW}{match.group(0)}{RESET}"

            colored_detail = hostname_pattern.sub(yellowize_hostname, detail)
            print(f"- {YELLOW}{rack}{RESET}: {detail}")

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
# RACK/CROSS_RACK
def run_validation_dashboard(entity_type, ids, header_suffix):
    TABLE_WIDTH = 111
    COL_WIDTH = 90
    COLOR_WIDTH = 16
    VALUE_WIDTH = 16
    TOP_BORDER_LINE = f"+{'-' * TABLE_WIDTH}+"

    for entity in ids:
        try:
            data = kubectl_get_json("gv", entity)
        except subprocess.CalledProcessError as e:
            print(f"{RED}❌ Error fetching {entity}:{RESET} {e.stderr.strip()}")
            continue

        validations = data.get("status", {}).get("validations", {})
        title = f"{entity} -- {header_suffix} Tests"

        print(TOP_BORDER_LINE)
        print(f"|{title.center(TABLE_WIDTH)}|")
        print(f"|{'-' * TABLE_WIDTH}|")

        if not validations:
            print(f"| {'No validations found.':<{COL_WIDTH + 18}} |")
            print(f"|{'-' * TABLE_WIDTH}|")
            continue

        for vname, phases in validations.items():
            print(f"| {vname:^{COL_WIDTH}} | {'Status':^{VALUE_WIDTH}} |")
            print(f"|{'-' * TABLE_WIDTH}|")

            for pname, pdata in phases.items():
                status = determine_phase_status(pdata)
                if isinstance(status, tuple):
                    short_status, tooltip, css_class = status
                    print(f"| {pname:<{COL_WIDTH}} | {colorize_status(short_status, css_class, COLOR_WIDTH)} |")
                else:
                    print(f"| {pname:<{COL_WIDTH}} | {colorize_status(status, None, COLOR_WIDTH)} |")

            print(f"|{'-' * TABLE_WIDTH}|")

# NODE - Obvivously
def run_node_dashboard(rack_names):
    NODE_COUNT = 9
    TABLE_WIDTH = 188
    TEST_WIDTH = 25
    VALUE_WIDTH = 17
    TOP_BORDER_LINE = f"+{'-' * TABLE_WIDTH}+"

    for prefix in rack_names:
        full_nodes = [f"{prefix}-gn{i}" for i in range(1, NODE_COUNT + 1)]
        validations = {}

        with ThreadPoolExecutor(max_workers=NODE_COUNT) as ex:
            results = ex.map(lambda n: (n, kubectl_get_json("gv", n).get("status", {}).get("validations", {})), full_nodes)

        for node, vdata in results:
            for test, data in vdata.items():
                validations.setdefault(test, {})[node] = data.get(node, {})

        print(TOP_BORDER_LINE)
        print(f"|{(prefix + ' -- Node Tests').center(TABLE_WIDTH)}|")
        print(TOP_BORDER_LINE)

        short_names = [f"gn{i}" for i in range(1, NODE_COUNT + 1)]
        print(f"|{('Test / Node:').center(TEST_WIDTH + 1)}|{''.join(f'{n:^{VALUE_WIDTH}}|' for n in short_names)}")
        print(TOP_BORDER_LINE)

        for test, nodes in validations.items():
            row = f"| {test:<{TEST_WIDTH}}| "
            for short in short_names:
                full = f"{prefix}-{short}"
                pdata = nodes.get(full, {})
                status = determine_phase_status(pdata)
                row += colorize_status(status) + "| "
            print(row)

        print(TOP_BORDER_LINE)

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

    parser = argparse.ArgumentParser(description="Validation Dashboard for Groq Clusters", usage="gv-dashboards.py [--cluster] [--only-warnings] [--no-warnings] [--nodes <rack>] [--rack <rack>] [--cross-rack <rack1>-<rack2>] [<rack> ...]", formatter_class=lambda prog: CustomHelpFormatter(prog, max_help_position=40))
    parser.add_argument("rack_name", nargs="*", metavar="<rack>", help="One or more rack names (e.g., c1r1, c1r1-c1r2, or c1r{1..2})")
    parser.add_argument("--cluster", "-c", action="store_true", help="View the cluster-wide dashboard")
    parser.add_argument("--only-warnings", action="store_true", help="Only show warnings in the cluster view (requires --cluster)")
    parser.add_argument("--no-warnings", action="store_true", help="Suppress warnings summary (only valid with --cluster)")
    parser.add_argument("--nodes", "-n", nargs="+", type=validate_rack_name, metavar="<rack>", help="View node-level validation status (multiple allowed)")
    parser.add_argument("--rack", "-r", nargs="+", type=validate_rack_name, metavar="<rack>", help="View rack-level validation status (multiple allowed)")
    parser.add_argument("--cross-rack", "-x", nargs="+", type=validate_cross_rack, metavar="<rack1>-<rack2>", help="View cross-rack validation status (multiple allowed)")

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    if args.only_warnings and not args.cluster:
        parser.error("--only-warnings can only be used with --cluster")
    if args.no_warnings and not args.cluster:
        parser.error("--no-warnings can only be used with --cluster")
    if args.cluster:
        run_cluster_dashboard(only_warnings=args.only_warnings, suppress_warnings=args.no_warnings)
    if args.nodes:
        run_node_dashboard(args.nodes)
    if args.rack:
        run_validation_dashboard("rack", args.rack, "Rack")
    if args.cross_rack:
        run_validation_dashboard("cross-rack", args.cross_rack, "Cross-Rack")

if __name__ == "__main__":
    main()
