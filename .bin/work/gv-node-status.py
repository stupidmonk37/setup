#!/usr/bin/env python3

import os
import subprocess
import sys
import tempfile
import venv
import shutil

def main_script():
    import yaml
    import shlex
    from concurrent.futures import ThreadPoolExecutor

    GREEN = "\033[92m"
    RED = "\033[91m"
    RESET = "\033[0m"

    NODE_COUNT = 9
    TABLE_WIDTH = 129

    def get_node_validation_status(node_name):
        cmd = f"kubectl get gv {node_name} -o yaml"
        try:
            output = subprocess.check_output(shlex.split(cmd), text=True)
            data = yaml.safe_load(output)
            return node_name, data.get("status", {}).get("validations", {})
        except subprocess.CalledProcessError as e:
            print(f"{RED}Error running kubectl for {node_name}:{RESET} {e}")
        except yaml.YAMLError as ye:
            print(f"{RED}YAML parsing error for {node_name}:{RESET} {ye}")
        return node_name, {}

    def generate_validation_table(cluster_id_prefix):
        full_node_names = [f"{cluster_id_prefix}-gn{i}" for i in range(1, NODE_COUNT + 1)]
        short_node_names = [f"gn{i}" for i in range(1, NODE_COUNT + 1)]
        merged_validations = {}

        with ThreadPoolExecutor(max_workers=NODE_COUNT) as executor:
            results = executor.map(get_node_validation_status, full_node_names)

        for full_node, validations in results:
            for test, nodes in validations.items():
                if test not in merged_validations:
                    merged_validations[test] = {}
                merged_validations[test][full_node] = nodes.get(full_node, {})

        table_lines = [
            "+" + "-" * TABLE_WIDTH + "+",
            f"|{' ' * ((TABLE_WIDTH - len(cluster_id_prefix) - 19) // 2)}{cluster_id_prefix} -- Node Tests:{' ' * ((TABLE_WIDTH - len(cluster_id_prefix) - 19 + 1) // 2)}    |",
            "+" + "-" * TABLE_WIDTH + "+",
            "| Test / Node:                          |" + "".join([f"  {n:^7}|" for n in short_node_names]),
            "+" + "-" * 39 + "+" + ("-" * 9 + "+") * NODE_COUNT
        ]

        for test, node_data in merged_validations.items():
            formatted_test = test.replace("-", " ").title().replace(" ", " - ", 1) if test.startswith("single") else test.replace("-", " ").title()
            row = f"| {formatted_test:<37} |"
            for short_node in short_node_names:
                full_node = f"{cluster_id_prefix}-{short_node}"
                data = node_data.get(full_node, {})
                status = "N/A"
                if isinstance(data, dict):
                    results = data.get("results", [])
                    if results and isinstance(results[0], dict):
                        status_val = results[0].get("status", "N/A").capitalize()
                        if status_val.lower() == "success":
                            status = "Success"
                colorized = f"{GREEN}{status:^9}{RESET}" if status == "Success" else f"{RED}{status:^9}{RESET}"
                row += colorized + "|"
            table_lines.append(row)

        table_lines.append("+" + "-" * TABLE_WIDTH + "+")
        return "\n".join(table_lines)

    def print_multiple_tables(cluster_id_prefixes):
        for prefix in cluster_id_prefixes:
            print("\n" + generate_validation_table(prefix) + "\n")

    if len(sys.argv) < 2:
        print(f"{RED}Usage: {sys.argv[0]} <cluster_id_prefix1> [<cluster_id_prefix2> ...]{RESET}")
        sys.exit(1)

    print_multiple_tables(sys.argv[1:])


# Only create a venv if not already in one
def in_virtualenv():
    return hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.prefix != sys.base_prefix)

def run_with_temp_venv():
    venv_dir = tempfile.mkdtemp(prefix="tmp_venv_")
    try:
        print(f"🔧 Creating temporary virtualenv in {venv_dir}")
        venv.create(venv_dir, with_pip=True)

        pip = os.path.join(venv_dir, "bin", "pip")
        python = os.path.join(venv_dir, "bin", "python")

        # Silence pip output
        subprocess.check_call([pip, "install", "pyyaml"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print("🚀 Running script inside venv...")
        subprocess.check_call([python, __file__, *sys.argv[1:]])
    finally:
        print("🧹 Cleaning up virtualenv...")
        shutil.rmtree(venv_dir)


if __name__ == "__main__":
    if in_virtualenv():
        main_script()
    else:
        run_with_temp_venv()
