import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console
from rich.table import Table
from utils import colorize, display_node_table, is_rack_name, kubectl_get_json

def process_node_validations(rack_name: str, validations: dict) -> dict:
    summary = {}

    for test_name, nodes_data in validations.items():
        node_statuses = {}
        for i in range(1, 10):
            short = f"gn{i}"
            full = f"{rack_name}-{short}"
            pdata = nodes_data.get(full, {})
            status_info = determine_validation_phases(pdata)
            status_info.setdefault("phase", pdata.get("phase", "Unknown"))
            status_info["validator"] = test_name
            node_statuses[short] = status_info
        summary[test_name] = node_statuses

    return summary



def display_node_table(rack_names: list[str], render: bool = True) -> list[Table] | None:
    console = Console()
    tables = []

    for rack_name in rack_names:
        try:
            node_names = [f"{rack_name}-gn{i}" for i in range(1, 10)]
            validations = {}

            with ThreadPoolExecutor(max_workers=9) as executor:
                results = executor.map(
                    lambda node: (node, kubectl_get_json(node).get("status", {}).get("validations", {})),
                    node_names
                )

            for node_name, node_validations in results:
                for test_name, test_data in node_validations.items():
                    validations.setdefault(test_name, {})[node_name] = test_data.get(node_name, {})

            dashboard = process_node_validations(rack_name, validations)

            table = Table(title=f"Node Validation Status - {rack_name}", title_style="bold cyan")
            table.add_column("Validator", style="cyan")
            for i in range(1, 10):
                table.add_column(f"gn{i}", justify="center")

            for validator, nodes in dashboard.items():
                row = [validator]
                for i in range(1, 10):
                    node = f"gn{i}"
                    status_raw = nodes.get(node, {}).get("results_status", "N/A")
                    row.append(colorize(status_raw))
                table.add_row(*row)

            if render:
                console.print(table)
            else:
                tables.append(table)

        except Exception as e:
            error_msg = f"[red]Error fetching rack {rack_name}: {str(e)}[/red]"
            if render:
                console.print(error_msg)
            else:
                error_table = Table()
                error_table.add_row(error_msg)
                tables.append(error_table)

    return None if render else tables

def determine_validation_phases(node_groups: dict) -> list[dict]:
    phases = []

    for node_set, pdata in node_groups.items():
        phase = pdata.get("phase", "").lower()
        results = pdata.get("results", [])
        faults = results[0].get("faults", []) if results else []
        results_status = results[0].get("status", "") if results else ""
        started_at = pdata.get("startedAt")

        if faults:
            fault_descriptions = sorted({
                f"{f.get('fault_type', 'Unknown')} ({f.get('component', '?')})"
                for f in faults
            })
            status_text = "; ".join(fault_descriptions)
            phases.append({
                "phase": node_set,
                "status": status_text,
                "class": "fault",
                "started_at": started_at,
            })
        else:
            status_text = (
                results_status.replace("-", " ").title()
                if results_status else (phase.title() or "Not Started")
            )
            phases.append({
                "phase": node_set,
                "status": status_text,
                "class": None,
                "started_at": started_at,
            })

    return phases













def valid_rack_name(value: str) -> str:
    if not is_rack_name(value):
        raise argparse.ArgumentTypeError(
            f"Invalid rack format: '{value}'. Must match c<digit>r<digits> (e.g., c0r1)"
        )
    return value


def main():
    parser = argparse.ArgumentParser(description="Node validation dashboard CLI")
    parser.add_argument(
        "--racks",
        nargs="+",
        type=valid_rack_name,
        required=True,
        help="List of racks (e.g. c0r1, c1r55)"
    )
    parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format: table (default) or json"
    )
    args = parser.parse_args()

    if args.format == "json":
        output = {}

        for rack in args.racks:
            try:
                node_names = [f"{rack}-gn{i}" for i in range(1, 10)]
                validations = {}

                with ThreadPoolExecutor(max_workers=9) as executor:
                    results = executor.map(
                        lambda node: (node, kubectl_get_json(node).get("status", {}).get("validations", {})),
                        node_names
                    )

                for node_name, node_validations in results:
                    for test_name, test_data in node_validations.items():
                        validations.setdefault(test_name, {})[node_name] = test_data.get(node_name, {})

                output[rack] = process_node_validations(rack, validations)
            except Exception as e:
                output[rack] = {"error": str(e)}

        print(json.dumps(output, indent=2))
    else:
        display_node_table(args.racks, render=True)


if __name__ == "__main__":
    main()
