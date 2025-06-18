#!/usr/bin/env python3

import argparse
import json
import subprocess
import re
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console
from rich.table import Table
from utils import is_rack_name, kubectl_get_json_validation, process_node_validations, colorize

console = Console()

STATUS_COLOR_LOOKUP = {
    status: color
    for color, statuses in {
        "green": {"success", "healthy"},
        "blue": {"in progress", "running"},
        "cyan": {"pending"},
        "bright white": {"not made"},
        "yellow": {"not started", "info"},
        "red": {"failure", "fault", "warning(s)", "failed-retryable", "notready", "failed"},
    }.items()
    for status in statuses
}


def get_kubectl_context() -> str:
    try:
        result = subprocess.run(
            ["kubectl", "config", "current-context"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "Unknown Context"


def valid_rack_name(value: str) -> str:
    if not is_rack_name(value):
        raise argparse.ArgumentTypeError(
            f"Invalid rack format: '{value}'. Must match c<digit>r<digits> (e.g., c0r1)"
        )
    return value


def fetch_validations(rack_name: str) -> dict:
    node_names = [f"{rack_name}-gn{i}" for i in range(1, 10)]
    validations = {}

    with ThreadPoolExecutor(max_workers=9) as executor:
        results = executor.map(
            lambda node: (node, kubectl_get_json_validation(node).get("status", {}).get("validations", {})),
            node_names
        )

    for node_name, node_validations in results:
        for test_name, test_data in node_validations.items():
            validations.setdefault(test_name, {})[node_name] = test_data.get(node_name, {})

    return validations


def display_node_table(rack_names: list[str], render: bool = True) -> list[Table] | None:
    tables = []

    for rack_name in rack_names:
        try:
            validations = fetch_validations(rack_name)
            dashboard = process_node_validations(rack_name, validations)
            context = get_kubectl_context()

            table = Table(title=f"{rack_name} - Node Validation Status - {context}", header_style="white")
            table.add_column("Validator", style="cyan")
            for i in range(1, 10):
                table.add_column(f"gn{i}", justify="center")

            for validator, nodes in dashboard.items():
                row = [validator]
                for i in range(1, 10):
                    node = f"gn{i}"
                    status = nodes.get(node, {}).get("results_status", "N/A")
                    row.append(colorize(status))
                table.add_row(*row)

            if render:
                console.print(table)
            else:
                tables.append(table)

        except Exception as e:
            msg = f"[red]Error fetching rack {rack_name}: {str(e)}[/red]"
            if render:
                console.print(msg)
            else:
                error_table = Table()
                error_table.add_row(msg)
                tables.append(error_table)

    return None if render else tables


def main():
    parser = argparse.ArgumentParser(description="Node validation dashboard CLI")
    parser.add_argument(
        "--racks", nargs="+", type=valid_rack_name, required=True,
        help="List of racks (e.g. c0r1, c1r55)"
    )
    parser.add_argument(
        "--format", choices=["json", "table"], default="table",
        help="Output format: table (default) or json"
    )
    args = parser.parse_args()

    if args.format == "json":
        output = {}
        for rack in args.racks:
            try:
                validations = fetch_validations(rack)
                output[rack] = process_node_validations(rack, validations)
            except Exception as e:
                output[rack] = {"error": str(e)}

        print(json.dumps(output, indent=2))
    else:
        display_node_table(args.racks, render=True)


if __name__ == "__main__":
    main()
