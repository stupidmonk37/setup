#!/usr/bin/env python3

import subprocess
import argparse
import sys
import os
import tempfile
import shutil
import venv

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

COLUMN_WIDTH = 88

def run_kubectl_get_validation(cluster_id):
    import yaml
    command = f"kubectl get gv {cluster_id} -o yaml"
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
        return yaml.safe_load(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"{RED}Error: Failed to fetch validation data for cluster '{cluster_id}'{RESET}")
        print(e.stderr.strip())
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"{RED}YAML parsing error:{RESET} {e}")
        sys.exit(1)

def colorize_status(status):
    if not status:
        return f"{YELLOW}{'N/A':<8}{RESET}"
    status_lower = status.lower()
    if status_lower == "success":
        return f"{GREEN}{status:<8}{RESET}"
    elif status_lower == "failure":
        return f"{RED}{status:<8}{RESET}"
    else:
        return f"{YELLOW}{status:<8}{RESET}"

def print_table_header(title):
    total_width = COLUMN_WIDTH + 13
    separator = f"+{'-' * total_width}+"
    title_line = f"|{title:^{total_width}}|"

    print(separator)
    print(title_line)
    print(f"+{'-' * (COLUMN_WIDTH + 2)}+{'-' * 10}+")

def print_table_row(phase_name, status):
    print(f"| {phase_name:<{COLUMN_WIDTH}} | {colorize_status(status)} |")

def print_validation_table(cluster_id):
    data = run_kubectl_get_validation(cluster_id)
    status_data = data.get("status", {})
    validations_data = status_data.get("validations", {})

    title = f"{cluster_id} -- Rack Tests"
    print_table_header(title)

    if not validations_data:
        print(f"| {'No validations found.':<{COLUMN_WIDTH + 10}} |")
        print(f"+{'-' * (COLUMN_WIDTH + 2)}+{'-' * 10}+")
        return

    for validation_name, validation_info in validations_data.items():
        print(f"| {validation_name:<{COLUMN_WIDTH}} |  Status  |")
        print(f"+{'-' * (COLUMN_WIDTH + 2)}+{'-' * 10}+")
        for phase_name, phase_info in validation_info.items():
            status = "N/A"
            if isinstance(phase_info, dict):
                results = phase_info.get("results", [])
                if results and isinstance(results[0], dict):
                    status = results[0].get("status", "N/A")
            print_table_row(phase_name, status)
        print(f"+{'-' * (COLUMN_WIDTH + 2)}+{'-' * 10}+")

def main():
    parser = argparse.ArgumentParser(
        description="Display rack test validations for one or more clusters."
    )
    parser.add_argument(
        "cluster_ids",
        nargs="+",
        help="One or more cluster IDs (e.g., c1r66 c2r55 c3r88)"
    )
    args = parser.parse_args()

    for cluster_id in args.cluster_ids:
        print("\n")
        print_validation_table(cluster_id)
        print("\n")

def run_with_temp_venv():
    venv_dir = tempfile.mkdtemp(prefix="tmp_venv_")
    try:
        print(f"🔧 Creating temporary virtualenv in {venv_dir}")
        venv.create(venv_dir, with_pip=True)

        pip = os.path.join(venv_dir, "bin", "pip")
        python = os.path.join(venv_dir, "bin", "python")

        # Silent pip install
        subprocess.check_call([pip, "install", "pyyaml"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print("🚀 Running script inside venv...")
        subprocess.check_call([python, __file__, *sys.argv[1:]])
    finally:
        print("🧹 Cleaning up virtualenv...")
        shutil.rmtree(venv_dir)

if __name__ == "__main__":
    if sys.prefix == sys.base_prefix:
        # Not inside a venv
        run_with_temp_venv()
    else:
        # Already inside a venv
        main()
