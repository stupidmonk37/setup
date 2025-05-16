#!/usr/bin/env python3

import subprocess
import json
import os
import time
import signal
from collections import defaultdict

# Configurable refresh interval (in seconds)
REFRESH_INTERVAL = 10

# Graceful exit
def handle_exit(sig, frame):
    print("\nExiting...")
    exit(0)

signal.signal(signal.SIGINT, handle_exit)

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')

def fetch_node_data():
    try:
        result = subprocess.run(
            ["kubectl", "get", "nodes", "-o", "json"],
            capture_output=True, text=True, check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print("Error fetching node data:", e.stderr)
        return None

def summarize_nodes(data):
    rack_summary = defaultdict(lambda: {"node": True, "rack": True})
    cross_rack_summary = {}

    for node in data["items"]:
        name = node["metadata"]["name"]
        labels = node["metadata"].get("labels", {})

        rack = "-".join(name.split("-")[:2])  # e.g., "c1r5" from "c1r5-gn4"
        node_label = labels.get("validation.groq.io/node-complete")
        rack_label = labels.get("validation.groq.io/rack-complete")
        cross_label = labels.get("validation.groq.io/cross-rack-complete")

        if node_label != "true":
            rack_summary[rack]["node"] = False
        if rack_label != "true":
            rack_summary[rack]["rack"] = False

        if cross_label == "true":
            cross_rack_summary[rack] = "Success"
        else:
            cross_rack_summary[rack] = "Missing"

    return rack_summary, cross_rack_summary

def print_summary_table(rack_summary, cross_rack_summary):
    racks = sorted(rack_summary.keys(), key=lambda r: int(r.replace("c1r", "")))
    total_racks = len(racks)
    complete_nodes = sum(1 for v in rack_summary.values() if v["node"])
    complete_racks = sum(1 for v in rack_summary.values() if v["rack"])
    complete_cross = sum(1 for v in cross_rack_summary.values() if v == "Success")

    print("+---------------------------------------------------------------+")
    print("| Rack   | Node      | Rack Level | Cross Rack Pair |  Status   |")
    print("|--------+-----------+------------+------------------+-----------|")
    for i, rack in enumerate(racks):
        node_status = "Success" if rack_summary[rack]["node"] else "Missing"
        rack_status = "Success" if rack_summary[rack]["rack"] else "Missing"

        if i < len(racks) - 1:
            pair = f"{racks[i]}-{racks[i+1]}"
            cross_status = cross_rack_summary.get(racks[i], "Missing")
        else:
            pair = ""
            cross_status = ""

        print(f"| {rack:<6} | {node_status:<9} | {rack_status:<10} | {pair:<16} | {cross_status:<9} |")

    print("+---------------------------------------------------------------+")
    print(f"| Totals: Nodes: {complete_nodes}/{total_racks}, "
          f"Rack: {complete_racks}/{total_racks}, "
          f"Cross Rack: {complete_cross}/{total_racks}                 |")
    print("+---------------------------------------------------------------+")

def main():
    while True:
        clear_screen()
        node_data = fetch_node_data()
        if node_data:
            rack_summary, cross_rack_summary = summarize_nodes(node_data)
            print_summary_table(rack_summary, cross_rack_summary)
        else:
            print("Failed to load node data.")

        time.sleep(REFRESH_INTERVAL)

if __name__ == "__main__":
    main()
