import argparse
import json
import sys

from rich.console import Console
from rich.table import Table

from utils import kubectl_get_json, colorize, format_timestamp, is_rack_name, display_rack_table

def determine_validation_phase_status(pdata: dict) -> dict:
    phase = pdata.get("phase", "").lower()
    results = pdata.get("results", [])
    raw_status = results[0].get("status", "") if results else ""
    faults = results[0].get("faults", []) if results else []

    if faults:
        fault_descriptions = sorted({
            f"{f.get('fault_type', 'Unknown')} ({f.get('component', '?')})"
            for f in faults
        })
        fault_text = "; ".join(fault_descriptions)

        tooltip = "\n".join(
            f"{f.get('fault_type', 'Unknown')}: {f.get('component_type', '?')} at {f.get('component', '?')}"
            for f in faults
        )

        return {
            "text": colorize(fault_text),
            "tooltip": tooltip,
            "class": "fault"
        }

    if not results or not raw_status:
        if phase == "started":
            return {"text": colorize("In Progress")}
        return {"text": colorize("Not Started")}

    readable_status = raw_status.replace("-", " ").title()
    return {"text": colorize(readable_status)}



def determine_validation_phases(node_groups: dict) -> list[dict]:
    # from utils import determine_validation_phase_status
    phases = []
    for node_set, pdata in node_groups.items():
        status = determine_validation_phase_status(pdata)
        phases.append({
            "phase": node_set,
            "status": status.get("text"),
            "class": status.get("class"),
            "started_at": pdata.get("startedAt"),
        })
    return phases





def build_rack_table(entity_id: str, entity_type: str = "rack", header_suffix: str = "Validation Status") -> Table:
    # from utils import kubectl_get_json, determine_validation_phases
    run_data = kubectl_get_json(entity_id)
    table = Table(title=f"{entity_type.title()} {entity_id} {header_suffix}", title_style="bold cyan")

    table.add_column("Validator")
    table.add_column("Phase")
    table.add_column("Status")
    table.add_column("Started At")

    validations = run_data.get("status", {}).get("validations", {})
    last_validator = None

    for validator_name, node_groups in validations.items():
        phases = determine_validation_phases(node_groups)

        if last_validator:
            table.add_section()

        for phase in phases:
            table.add_row(
                f"[cyan]{validator_name}[/cyan]",
                f"[white]{phase.get('phase', 'N/A')}[/white]",
                colorize(phase.get('status', 'N/A')),
                f"[white]{format_timestamp(phase.get('started_at', '-'))}[/white]"
            )

        last_validator = validator_name

    return table




def display_rack_table(entity_ids: list[str], render: bool = True) -> list[Table] | None:
    console = Console()
    tables = []

    for entity_id in entity_ids:
        try:
            table = build_rack_table(entity_id)
            if render:
                console.print(table)
            else:
                tables.append(table)

        except Exception as e:
            error_msg = f"[red]Error fetching rack {entity_id}: {str(e)}[/red]"
            if render:
                console.print(error_msg)
            else:
                error_table = Table()
                error_table.add_row(error_msg)
                tables.append(error_table)

    return None if render else tables




















































def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--racks",
        nargs="+",
        required=True,
        help="List of rack(s) (e.g. c0r1 c0r2)"
    )
    parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format: table (default) or json"
    )
    args = parser.parse_args()

    invalid_racks = [rack for rack in args.racks if not is_rack_name(rack)]
    if invalid_racks:
        print(f"[ERROR] Invalid rack name(s): {', '.join(invalid_racks)}", file=sys.stderr)
        sys.exit(1)

    if args.format == "json":
        output = {}
        for rack in args.racks:
            try:
                output[rack] = kubectl_get_json(rack)
            except Exception as e:
                output[rack] = {"error": str(e)}
        print(json.dumps(output, indent=2))

    else:
        display_rack_table(args.racks, render=True)

if __name__ == "__main__":
    main()
