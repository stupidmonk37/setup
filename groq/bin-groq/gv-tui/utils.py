import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console
from rich.table import Table
from datetime import datetime

def format_timestamp(ts: str) -> str:
    try:
        dt_utc = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone()
        return dt_local.strftime("%Y-%m-%d %I:%M %p %Z")
    except Exception:
        return ts or "N/A"


# ====================================================================================================
# ===== COLOR MAPPING ================================================================================
# ====================================================================================================
COLOR_MAP = {
    "green": {"success", "healthy"},
    "blue": {"in progress", "running"},
    "cyan": {"pending"},
    "bright white": {"not made"},
    "yellow": {"not started", "info"},
    "red": {"failure", "fault", "warning(s)", "failed-retryable", "notready", "failed"},
}


STATUS_COLOR_LOOKUP = {
    status: color for color, statuses in COLOR_MAP.items() for status in statuses
}


def colorize(text: str) -> str:
    if not text or ("[" in text and "]" in text):
        return text

    normalized = text.strip().lower()
    color = STATUS_COLOR_LOOKUP.get(normalized, "red")
    return f"[{color}]{normalized.title()}[/{color}]"



# ====================================================================================================
# ===== KUBECTL JSON HELPERS =========================================================================
# ====================================================================================================
def kubectl_get_json_resource(resource: str) -> dict:
    cmd = ["kubectl", "get", resource, "-o", "json", "-n", "groq-system"]
    return json.loads(subprocess.check_output(cmd, text=True))


def kubectl_get_json_validation(name: str = None) -> dict:
    cmd = ["kubectl", "get", "groqvalidations.validation.groq.io"]
    if name:
        cmd.append(name)
    cmd.extend(["-n", "groq-system", "-o", "json"])
    return json.loads(subprocess.check_output(cmd, text=True))



def get_kubectl_context() -> str:
    """Returns the current kubectl context, or 'Unknown Context' on failure."""
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



# ====================================================================================================
# ===== NAMING + IDENTIFICATION ======================================================================
# ====================================================================================================
def extract_rack_prefix(name: str) -> str:
    parts = name.split("-")
    return parts[0] if len(parts) == 2 and parts[1].startswith("gn") and parts[1][2:].isdigit() else None


def is_node_name(name: str) -> bool:
    parts = name.split("-")
    return (
        len(parts) == 2
        and parts[1].startswith("gn")
        and parts[1][2:].isdigit()
        and is_rack_name(parts[0])
    )


def is_rack_name(name: str) -> bool:
    return re.fullmatch(r"c\d+r\d+", name) is not None


def is_xrk_name(name: str) -> bool:
    parts = name.split("-")
    return len(parts) == 2 and all(is_rack_name(p) for p in parts)


def natural_sort_key(s):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', s)]



# ====================================================================================================
# ===== VALIDATION PHASES ============================================================================
# ====================================================================================================
def process_node_validations(rack_name: str, validations: dict) -> dict:
    summary = {}

    for test_name, nodes_data in validations.items():
        node_group = {}
        for i in range(1, 10):
            short = f"gn{i}"
            full = f"{rack_name}-{short}"
            node_group[short] = nodes_data.get(full, {})

        phases = determine_validation_phases(node_group)

        node_statuses = {}
        for phase_info in phases:
            node_name = phase_info["phase"]
            node_statuses[node_name] = {
                "results_status": phase_info["status"],
                "class": phase_info.get("class"),
                "started_at": phase_info.get("started_at"),
                "phase": node_group[node_name].get("phase", "Unknown"),
                "validator": test_name,
            }

        summary[test_name] = node_statuses

    return summary


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



# ====================================================================================================
# ===== DISPLAY TABLES ===============================================================================
# ====================================================================================================
def display_cluster_table(data, rack_filter=None, render=True) -> Table | None:
    context = get_kubectl_context()
    table = Table(title=f"Groq Validation Status - {context}",
            header_style="white")
    for col in ("Rack", "Health", "Node GV", "Rack GV", "XRK Name", "XRK GV"):
        table.add_column(col)

    for rack in data["racks"]:
        if rack_filter and rack["rack"] not in rack_filter:
            continue
        table.add_row(
            rack["rack"],
            colorize(rack["health"]),
            colorize(rack["node_status"]),
            colorize(rack["rack_status"]),
            rack["xrk_name"] or "",
            colorize(rack["xrk_status"]),
        )

    if render:
        Console().print(table)
        return None
    else:
        return table


def display_node_table(rack_names: list[str], render: bool = True) -> list[Table] | None:
    console = Console()
    tables = []

    for rack_name in rack_names:
        try:
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

            dashboard = process_node_validations(rack_name, validations)

            context = get_kubectl_context()
            table = Table(title=f"{rack_name} - Node Validation Status - {context}",
            header_style="white")
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


def display_rack_table(rack_names: list[str], render: bool = True) -> list[Table] | None:
    console = Console()
    tables = []

    for rack_name in rack_names:
        try:
            rack_data = kubectl_get_json_validation(rack_name)
            context = get_kubectl_context()
            table = Table(title=f"{rack_name} - Rack Validation Status - {context}",
            header_style="white")
            for col in ("Validator", "Phase", "Status", "Started At"):
                table.add_column(col)

            validations = rack_data.get("status", {}).get("validations", {})
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
                        f"[white]{format_timestamp(phase.get('started_at', '-'))}[/white]",
                    )

                last_validator = validator_name

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


def display_crossrack_table(rack_names: list[str], render: bool = True) -> list[Table] | None:
    console = Console()
    tables = []

    for rack_name in rack_names:
        try:
            xrk_data = kubectl_get_json_validation(rack_name)
            context = get_kubectl_context()
            table = Table(title=f"{rack_name} - Cross-Rack - Validation Status - {context}",
            header_style="white")
            for col in ("Validator", "Phase", "Status", "Started At"):
                table.add_column(col)

            validations = xrk_data.get("status", {}).get("validations", {})
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
