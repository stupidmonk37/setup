import argparse
import json
import sys
from rich.console import Console
from rich.table import Table
from utils import colorize, display_rack_table, is_rack_name, kubectl_get_json_validation, format_timestamp


def valid_rack_name(value: str) -> str:
    if not is_rack_name(value):
        raise argparse.ArgumentTypeError(
            f"Invalid rack format: '{value}'. Must match c<digit>r<digits> (e.g., c0r1)"
        )
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--racks",
        nargs="+",
        type=valid_rack_name,
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

    if args.format == "json":
        output = {}

        for rack in args.racks:
            try:
                run_data = kubectl_get_json_validation(rack)
                validations = run_data.get("status", {}).get("validations", {})
                rack_summary = {}

                for validator_name, node_groups in validations.items():
                    node_summary = {}

                    for node_name, pdata in node_groups.items():
                        phase = pdata.get("phase", "Unknown")
                        results = pdata.get("results", [])
                        results_status = results[0].get("status", "") if results else ""
                        faults = results[0].get("faults", []) if results else []

                        if faults:
                            fault_descriptions = sorted({
                                f"{f.get('fault_type', 'Unknown')} ({f.get('component', '?')})"
                                for f in faults
                            })
                            fault_text = "; ".join(fault_descriptions)
                            results_status = fault_text
                            status_class = "fault"
                        elif not results_status:
                            results_status = phase.title() if phase else "Not Started"
                            status_class = None
                        else:
                            results_status = results_status.replace("-", " ").title()
                            status_class = None

                        node_summary[node_name] = {
                            "results_status": results_status,
                            "started_at": format_timestamp(pdata.get("startedAt")),
                            "phase": phase,
                            "validator": validator_name,
                        }
                        if status_class:
                            node_summary[node_name]["class"] = status_class

                    # Sort node names alphabetically for each validator
                    rack_summary[validator_name] = dict(sorted(node_summary.items()))

                output[rack] = rack_summary

            except Exception as e:
                output[rack] = {"error": str(e)}

        print(json.dumps(output, indent=2, sort_keys=True))

    else:
        display_rack_table(args.racks)


if __name__ == "__main__":
    main()
