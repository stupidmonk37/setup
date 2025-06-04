import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console
from rich.table import Table
from utils import colorize, display_node_table, is_rack_name, kubectl_get_json_validation, process_node_validations


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
                        lambda node: (node, kubectl_get_json_validation(node).get("status", {}).get("validations", {})),
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
