import argparse
import json
import time
from datetime import datetime
from utils import kubectl_get_json, process_validation_phases, colorize, format_timestamp
from rich.console import Console
from rich.table import Table


def format_timestamp(ts: str) -> str:
    try:
        dt_utc = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone()
        return dt_local.strftime("%Y-%m-%d %I:%M %p %Z")
    except Exception:
        return ts or "N/A"


def run_data_crossrack_dashboard(entity_ids: list[str], entity_type: str = "crossrack", header_suffix: str = "Validation Status") -> list[dict]:
    dashboards = []

    for entity_id in entity_ids:
        try:
            run_data = kubectl_get_json(entity_id)

            result = {"header": f"{entity_type.title()} {entity_id} {header_suffix}", "validations": []}

            validations = run_data.get("status", {}).get("validations", {})
            for validator_name, node_groups in validations.items():
                phases = process_validation_phases(node_groups)
                result["validations"].append({"name": validator_name, "phases": phases})

            dashboards.append(result)

        except Exception as e:
            dashboards.append({"error": f"Error fetching {entity_type} {entity_id}: {str(e)}"})

    return dashboards


def display_crossrack_table(results: list[dict]):
    console = Console()

    for result in results:
        if "error" in result:
            console.print(f"[red]{result['error']}[/red]")
            continue

        table = Table(title=result["header"], title_style="bold cyan")
        table.add_column("Validator")
        table.add_column("Phase")
        table.add_column("Status")
        table.add_column("Started At")

        last_validator = None
        for validation in result["validations"]:
            validator_name = validation["name"]

            if last_validator and last_validator != validator_name:
                table.add_section()

            for phase_info in validation["phases"]:
                table.add_row(
                    f"[cyan]{validator_name}[/cyan]",
                    f"[bright white]{phase_info.get('phase', 'N/A')}[/bright white]",
                    phase_info.get("status", "N/A"),
                    f"[bright white]{format_timestamp(phase_info.get('started_at', '-'))}[/bright white]",
                )
            last_validator = validator_name

        console.print(table)


def main():
    parser = argparse.ArgumentParser(description="Crossrack validation dashboard CLI")
    parser.add_argument(
        "--racks",
        nargs="+",
        required=True,
        help="List of crossrack names (e.g. c0r1-c0r2)"
    )
    parser.add_argument(
        "--type",
        default="crossrack",
        help="Entity type (default: crossrack)"
    )
    parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format: table (default) or json"
    )
    args = parser.parse_args()

    dashboards = run_data_crossrack_dashboard(args.racks, args.type)

    if args.format == "json":
        print(json.dumps(dashboards, indent=2))
    else:
        display_crossrack_table(dashboards)


if __name__ == "__main__":
    main()
