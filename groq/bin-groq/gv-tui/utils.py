import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.table import Table
from datetime import datetime
from collections import defaultdict
from textual.widgets import RichLog

def format_timestamp(ts: str) -> str:
    try:
        dt_utc = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone()
        return dt_local.strftime("%Y-%m-%d %I:%M %p %Z")
    except Exception:
        return ts or "N/A"


ALLOWED_POD_PREFIXES = ["bios-conformance", "mcu-comm-server", "tspd"]
EXPECTED_POD_COUNTS = {"bios-conformance": 9, "mcu-comm-server": 9, "tspd": 9}
REQUIRED_POD_TYPES = set(EXPECTED_POD_COUNTS)

EXPECTED_NODES = {f"gn{i}" for i in range(1, 10)}



# ====================================================================================================
# ===== COLOR MAPPING ================================================================================
# ====================================================================================================
COLOR_MAP = {
    "green": {"success", "healthy"},
    "blue": {"in progress", "running"},
    "cyan": {"pending", "started"},
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
    try:
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        return json.loads(output)

    except subprocess.CalledProcessError:
        return {}


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


def get_pods_json(field_selector=None, namespace="groq-system"):
    cmd = ["kubectl", "get", "pods", "-n", namespace, "-o", "json"]
    if field_selector:
        cmd.insert(3, "--field-selector")
        cmd.insert(4, field_selector)

    try:
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
        return json.loads(output).get("items", [])

    except subprocess.CalledProcessError:
        return []

    except json.JSONDecodeError:
        return []



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
    match = re.match(r"c(\d+)r(\d+)", s)
    if match:
        return tuple(map(int, match.groups()))
    
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', s)]


def valid_rack_name(value: str) -> str:
    if not is_rack_name(value):
        raise ValueError(f"Invalid rack format: '{value}'. Must match c<digit>r<digits> (e.g., c0r1)")

    return value


def valid_crossrack_name(value: str) -> str:
    if not is_xrk_name(value):
        raise ValueError(f"Invalid crossrack format: '{value}'. Must match c<digit>r<digits>-c<digit>r<digits>")
    
    return value


def base_name(pod_name: str) -> str:
    return re.sub(r"-[a-z0-9]{5}$", "", pod_name)



# ====================================================================================================
# ===== VALIDATION PHASES ============================================================================
# ====================================================================================================
def determine_validation_phases(node_groups: dict) -> list[dict]:
    phases = []
    for node_set, pdata in node_groups.items():
        phase = pdata.get("phase", "")
        results = pdata.get("results")
        if results:
            first_result = results[0]
            faults = first_result.get("faults")
            results_status = first_result.get("status", "")

        else:
            faults = []
            results_status = ""

        started_at = pdata.get("startedAt")
        if faults:
            fault_descriptions = sorted(
                f"{f.get('fault_type', 'Unknown')} ({f.get('component', '?')})"
                for f in faults
            )
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


def process_node_validations(rack_name: str, validations: dict) -> dict:
    summary = {}
    for test_name, nodes_data in validations.items():
        node_group = {
            f"gn{i}": nodes_data.get(f"{rack_name}-gn{i}", {})
            for i in range(1, 10)
        }

        phases = determine_validation_phases(node_group)
        node_statuses = {
            phase_info["phase"]: {
                "results_status": phase_info["status"],
                "class": phase_info.get("class"),
                "started_at": phase_info.get("started_at"),
                "phase": node_group[phase_info["phase"]].get("phase", "Unknown"),
                "validator": test_name,
            }
            for phase_info in phases
        }

        summary[test_name] = node_statuses

    return summary


def fetch_validations(rack_name: str) -> dict:
    node_names = [f"{rack_name}-gn{i}" for i in range(1, 10)]
    validations = {}
    def fetch_node_validation(node):
        return node, kubectl_get_json_validation(node).get("status", {}).get("validations", {})

    with ThreadPoolExecutor(max_workers=9) as executor:
        results = executor.map(fetch_node_validation, node_names)

    for node_name, node_validations in results:
        for test_name, test_data in node_validations.items():
            validations.setdefault(test_name, {})[node_name] = test_data.get(node_name, {})

    return validations



# ====================================================================================================
# ===== DISPLAY TABLES ===============================================================================
# ====================================================================================================
def display_cluster_table(data, rack_filter=None, render=True) -> Table | None:
    """Renders a table of the cluster status"""
    context = get_kubectl_context()
    table = Table(title=f"Groq Validation Status - {context}", header_style="white")
    racks = data.get("racks", [])
    pod_prefixes = sorted({prefix for rack in racks for prefix in rack.get("pod_health", {}).keys()})
    columns = ["Rack", "Health"] + pod_prefixes + ["Node GV", "Rack GV", "XRK Name", "XRK GV"]
    for col in columns:
        table.add_column(col)

    rack_filter_set = set(rack_filter) if rack_filter else None
    for rack in racks:
        rack_name = rack.get("rack", "")
        if rack_filter_set and rack_name not in rack_filter_set:
            continue

        pod_health = rack.get("pod_health", {})
        row = [rack_name, colorize(rack.get("health", "-"))]
        row.extend(colorize(pod_health.get(prefix, "-")) for prefix in pod_prefixes)
        row.extend([
            colorize(rack.get("node_status", "-")),
            colorize(rack.get("rack_status", "-")),
            rack.get("xrk_name") or "",
            colorize(rack.get("xrk_status", "-")),
        ])
        table.add_row(*row)

    if render:
        Console().print(table)
        return None

    else:
        return table


def display_node_table(rack_names: list[str], render: bool = True) -> list[Table] | None: # NEW
    """Fetches and displays per-node validation and pod status tables"""
    console = Console()
    tables = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(_fetch_node_data, rack_name): rack_name for rack_name in rack_names}
        for future in as_completed(futures):
            rack_name = futures[future]
            try:
                rack_name, node_data = future.result()
                if isinstance(node_data, Exception):
                    raise node_data

                table = _build_node_table(rack_name, node_data, render)
                if table is not None:
                    tables.append(table)

            except Exception as e:
                error_msg = f"[red]Error processing rack {rack_name}: {e}[/red]"
                if render:
                    console.print(error_msg)

                else:
                    error_table = Table()
                    error_table.add_row(error_msg)
                    tables.append(error_table)

    return None if render else tables


def display_rack_table(rack_names: list[str], render: bool = True) -> list[Table] | None:
    """Fetches and displays validation status for a list of racks"""
    console = Console()
    tables = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(_fetch_rack_crossrack_data, rn): rn for rn in rack_names}
        for future in as_completed(futures):
            rack_name = futures[future]
            try:
                rack_name, rack_data = future.result()
                if isinstance(rack_data, Exception):
                    raise rack_data

                validations = rack_data.get("status", {}).get("validations", {})
                table = _build_rack_crossrack_table(rack_name, validations, render)
                if table is not None:
                    tables.append(table)

            except Exception as e:
                error_msg = f"[red]Error fetching rack {rack_name}: {e}[/red]"
                if render:
                    console.print(error_msg)
                else:
                    error_table = Table()
                    error_table.add_row(error_msg)
                    tables.append(error_table)

    return None if render else tables


def display_crossrack_table(rack_names: list[str], render: bool = True) -> list[Table] | None:
    """Fetches and displays validation status for a list of cross-racks"""
    console = Console()
    tables = []

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(_fetch_rack_crossrack_data, rn): rn for rn in rack_names}

        for future in as_completed(futures):
            rack_name = futures[future]
            try:
                rack_name, xrk_data = future.result()
                if isinstance(xrk_data, Exception):
                    raise xrk_data
                
                validations = xrk_data.get("status", {}).get("validations", {})
                table = _build_rack_crossrack_table(rack_name, validations, render)
                if table is not None:
                    tables.append(table)

            except Exception as e:
                error_msg = f"[red]Error fetching rack {rack_name}: {e}[/red]"
                if render:
                    console.print(error_msg)
                else:
                    error_table = Table()
                    error_table.add_row(error_msg)
                    tables.append(error_table)

    return None if render else tables


def _fetch_node_data(rack_name: str) -> tuple[str, dict | Exception]: # NEW
    try:
        validations = fetch_validations(rack_name)
        dashboard = process_node_validations(rack_name, validations)
        entries = collect_pod_entries([rack_name])
        return rack_name, {
            "dashboard": dashboard,
            "entries": entries,
        }

    except Exception as e:
        return rack_name, e


def _build_node_table(rack_name: str, node_data: dict, render: bool = True) -> Table | None: # NEW
    console = Console()
    required_pod_types = REQUIRED_POD_TYPES
    entries = node_data["entries"]
    dashboard = node_data["dashboard"]
    pod_ready_map = {}
    pod_status_map = {}
    pod_issues_map = defaultdict(list)
    pods_seen = defaultdict(set)
    per_node_pod_status = defaultdict(dict)
    for name, ready, status, node in entries:
        pod_base = base_name(name)
        pod_ready_map[node] = ready
        pod_status_map[node] = status
        if pod_base in required_pod_types:
            pods_seen[node].add(pod_base)
            per_node_pod_status[node][pod_base] = status
            if status.lower() != "running":
                pod_issues_map[node].append(f"[yellow]{pod_base} (not running)[/yellow]")

    all_nodes = [f"{rack_name}-gn{i}" for i in range(1, 10)]
    for node in all_nodes:
        missing = required_pod_types - pods_seen[node]
        for pod_base in missing:
            pod_issues_map[node].append(f"[red]{pod_base} (missing)[/red]")

    context = get_kubectl_context()
    table = Table(title=f"{rack_name} - Node Dashboard - {context}", header_style="white")
    table.add_column("Validator", style="cyan")
    for i in range(1, 10):
        table.add_column(f"gn{i}", justify="center")

    for validator, nodes in dashboard.items():
        row = [validator]
        for i in range(1, 10):
            node = f"{rack_name}-gn{i}"
            status = nodes.get(f"gn{i}", {}).get("results_status", "N/A")
            row.append(colorize(status))

        table.add_row(*row)

    table.add_section()
    for pod_base in required_pod_types:
        row = [pod_base]
        for i in range(1, 10):
            node = f"{rack_name}-gn{i}"
            if pod_base in per_node_pod_status[node]:
                status = per_node_pod_status[node][pod_base]

            elif pod_issues_map[node]:
                status = "[red]Missing[/red]"

            else:
                status = "-"

            row.append(colorize(status))

        table.add_row(*row)

    if render:
        console.print(table)
        return None

    else:
        return table


def _fetch_rack_crossrack_data(rack_name: str) -> tuple[str, dict | Exception]:
    try:
        data = kubectl_get_json_validation(rack_name)
        return (rack_name, data)
    except Exception as e:
        return (rack_name, e)


def _build_rack_crossrack_table(rack_name, validations, render=True):
    console = Console()
    context = get_kubectl_context()
    table = Table(title=f"{rack_name} - Validation Status - {context}", header_style="white")
    for col in ("Validator", "Phase", "Status", "Started At"):
        table.add_column(col)

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
        return None
    else:
        return table



# ====================================================================================================
# ===== PODS =========================================================================================
# ====================================================================================================
def collect_pod_entries(base_nodes):
    """Collects pod entries for a list of base nodes"""
    entries = []
    nodes = [f"{base}-gn{i}" for base in base_nodes for i in range(1, 10)]
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(get_pods_json, field_selector=f"spec.nodeName={node}"): node for node in nodes}
        for future in as_completed(futures):
            node = futures[future]
            try:
                pods = future.result()

            except Exception as e:
                Console().print(f"[red]Failed to fetch pods for node {node}: {e}[/red]")
                continue

            for pod in pods:
                if pod.get("status", {}).get("phase") == "Succeeded":
                    continue

                name = pod["metadata"]["name"]
                pod_base = base_name(name)
                status = pod["status"]["phase"]
                node_name = pod["spec"]["nodeName"]
                container_statuses = pod.get("status", {}).get("containerStatuses", [])
                total = len(container_statuses)
                ready = sum(int(bool(cs.get("ready"))) for cs in container_statuses)

                entries.append((pod_base, f"{ready}/{total}", status, node_name))

    return sorted(entries, key=lambda x: (x[0], x[3]))


def parse_pods(filter_base_nodes=None):
    """Parses pod statuses and returns a summary of pod states"""
    summary = defaultdict(lambda: defaultdict(dict))
    pod_prefixes = set()
    pods = get_pods_json()
    for pod in pods:
        metadata = pod.get("metadata", {})
        name = metadata.get("name", "")
        node_name = pod.get("spec", {}).get("nodeName", "")
        container_statuses = pod.get("status", {}).get("containerStatuses", [])
        if not is_node_name(node_name):
            continue

        base, gn_node = node_name.split("-", 1)
        if filter_base_nodes and base not in filter_base_nodes:
            continue

        pod_prefix = next((p for p in ALLOWED_POD_PREFIXES if name.startswith(p)), None)
        if not pod_prefix:
            continue

        pod_prefixes.add(pod_prefix)
        if not container_statuses:
            state_str = "-"

        else:
            all_states = [next(iter(cs.get("state", {}).keys()), "-") for cs in container_statuses]
            state_str = "running" if all(s == "running" for s in all_states) else "; ".join(s for s in all_states if s != "running")

        summary[base][pod_prefix][gn_node] = state_str

    return summary, sorted(pod_prefixes)


def summarize_status_og(pod_states):
    """Summarizes the status of pods in a rack"""
    expected_nodes = [f"gn{i}" for i in range(1, 10)]
    missing_nodes = [gn for gn in expected_nodes if gn not in pod_states]
    if missing_nodes:
        return "Missing: " + ", ".join(missing_nodes)

    not_running_nodes = [(gn, state) for gn, state in pod_states.items() if state != "running"]
    if not_running_nodes:
        return ", ".join(f"{state}: {gn}" for gn, state in not_running_nodes)

    return "Running"


def summarize_status(pod_states):
    """Summarizes the status of pods in a rack"""
    expected_nodes = [f"gn{i}" for i in range(1, 10)]
    missing_nodes = [gn for gn in expected_nodes if gn not in pod_states]
    if missing_nodes:
        return "Missing: " + ", ".join(sorted(missing_nodes))

    not_running_nodes = defaultdict(list)
    for gn, state in pod_states.items():
        if state != "running":
            not_running_nodes[state.capitalize()].append(gn.capitalize())

    if not_running_nodes:
        return ", ".join(f"{state}: {', '.join(sorted(nodes))}" for state, nodes in not_running_nodes.items())

    return "Running"



# ====================================================================================================
# ===== CLUSTER ======================================================================================
# ====================================================================================================
def cluster_table_default_status(name):
    """Returns a default status for a rack or cross-rack"""
    return {
        "rack": name,
        "nodes": {},
        "node_status": "Not Made",
        "rack_status": "Not Made",
        "xrk_status": "Not Made",
        "xrk_name": None,
        "health": None,
        "pod_health": {}
    }


def get_rack_health_info(nodes_json):
    """Returns a dictionary of rack health information"""
    racks = defaultdict(lambda: cluster_table_default_status(""))
    for item in nodes_json.get("items", []):
        name = item["metadata"]["name"]
        rack = extract_rack_prefix(name)
        if not rack:
            continue

        gn = name.split("-")[-1]
        gn_name = gn if gn.startswith("gn") else f"gn{gn}"
        conditions = item.get("status", {}).get("conditions", [])
        ready = any(c["type"] == "Ready" and c["status"] == "True" for c in conditions)
        racks[rack]["rack"] = rack
        racks[rack]["nodes"][gn_name] = ready

    for rack_data in racks.values():
        found_nodes = set(rack_data["nodes"])
        node_statuses = rack_data["nodes"]
        missing = sorted(EXPECTED_NODES - found_nodes)
        not_ready = sorted(n for n in found_nodes if not node_statuses.get(n, False))
        messages = []
        if missing:
            messages.append(f"Missing: {', '.join(missing)}")

        if not_ready:
            messages.append(f"NotReady: {', '.join(not_ready)}")

        rack_data["health"] = "; ".join(messages) if messages else "Healthy"

    return racks


def update_rack_statuses(items, racks):
    """Updates the rack statuses based on the node validation results"""
    node_statuses = {}
    total_success_nodes = 0
    expected_nodes = [f"gn{i}" for i in range(1, 10)]

    for item in items:
        name = item.get("metadata", {}).get("name", "")
        status = item.get("status", {}).get("status", "Not Made")
        if is_rack_name(name):
            key = name
            field = "rack_status"

        elif is_xrk_name(name):
            key = name.split("-", 1)[0]
            racks.setdefault(key, cluster_table_default_status(key))
            racks[key]["xrk_name"] = name
            field = "xrk_status"

        else:
            key = extract_rack_prefix(name)
            field = None  # node-level validator

        if key:
            racks.setdefault(key, cluster_table_default_status(key))
            if field in {"rack_status", "xrk_status"}:
                racks[key][field] = status
            elif field is None:
                node_statuses.setdefault(key, []).append((name, status))

    # Summarize node statuses per rack and count successful nodes
    for rack_name, name_statuses in node_statuses.items():
        statuses_by_node = {}  # {gn1: [Success, Started], ...}
        for name, status in name_statuses:
            match = re.search(r"\b(gn[1-9])\b", name)
            if match:
                node = match.group(1)
                statuses_by_node.setdefault(node, []).append(status)

        missing_nodes = [n for n in expected_nodes if n not in statuses_by_node]

        if missing_nodes:
            # Are any of the existing nodes 'Success' or 'Partial'?
            existing_statuses = [s for status_list in statuses_by_node.values() for s in status_list]
            if any(s in {"Success", "Partial"} for s in existing_statuses):
                summary = "Partial"
            elif any(s in {"Started", "Running"} for s in existing_statuses):
                summary = "Running"
            else:
                summary = "Not Made"

        else:
            all_statuses = [s for status_list in statuses_by_node.values() for s in status_list]
            if any(s in {"Started", "Running"} for s in all_statuses):
                summary = "Running"
            else:
                flat_node_summaries = []
                for node in expected_nodes:
                    node_status_list = statuses_by_node[node]
                    if all(s == "Success" for s in node_status_list):
                        flat_node_summaries.append("Success")
                    elif any(s == "Success" for s in node_status_list):
                        flat_node_summaries.append("Partial")
                    else:
                        flat_node_summaries.append("Failed")

                success_count = sum(1 for s in flat_node_summaries if s == "Success")
                total_success_nodes += success_count

                if success_count == len(expected_nodes):
                    summary = "Success"
                elif success_count > 0:
                    summary = "Partial"
                else:
                    summary = "Failed"

        racks[rack_name]["node_status"] = summary

    # Mark racks without any node entries as "Not Made"
    for rack_name, rack in racks.items():
        if "node_status" not in rack:
            rack["node_status"] = "Not Made"

    return total_success_nodes


def get_data_cluster():
    """Main function to get cluster data, node and pod health and summaries"""
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(kubectl_get_json_resource, "nodes"): "nodes",
            executor.submit(kubectl_get_json_validation): "gv",
        }
        results = {name: future.result() for future, name in ((f, futures[f]) for f in as_completed(futures))}

    racks = get_rack_health_info(results["nodes"])
    rack_list = sorted(racks.values(), key=lambda r: natural_sort_key(r["rack"]))
    pod_summary, pod_prefixes = parse_pods()
    for rack in rack_list:
        pod_health = {}
        rack_name = rack["rack"]
        for prefix in pod_prefixes:
            states = pod_summary.get(rack_name, {}).get(prefix, {})
            pod_health[prefix] = summarize_status(states)

        rack["pod_health"] = pod_health

    total_nodes = len(rack_list) * 9
    ready_nodes = sum(1 for r in rack_list for ready in r["nodes"].values() if ready)
    node_complete = update_rack_statuses(results["gv"].get("items", []), racks)
    rack_complete = sum(1 for r in rack_list if r["rack_status"] == "Success")
    xrk_complete = sum(1 for r in rack_list if r["xrk_status"] == "Success")
    return {
        "summary": {
            "total_nodes": total_nodes,
            "total_racks": len(rack_list),
            "ready_nodes": ready_nodes,
            "node_complete": node_complete,
            "node_ratio": node_complete / total_nodes if total_nodes else 0.0,
            "ready_ratio": ready_nodes / total_nodes if total_nodes else 0.0,
            "racks_complete": rack_complete,
            "racks_ratio": rack_complete / len(rack_list) if len(rack_list) else 0.0,
            "xrk_complete": xrk_complete,
            "xrk_ratio": xrk_complete / len(rack_list) if len(rack_list) else 0.0
        },
        "racks": rack_list
    }


def output_cluster_json(data, racks):
    """Prints the cluster data in JSON format"""
    if racks:
        filtered_racks = {r["rack"]: r for r in data["racks"] if r["rack"] in racks}
        print(json.dumps(filtered_racks, indent=2))

    else:
        print(json.dumps(data["racks"], indent=2))


def print_cluster_summary(output=None, summary=None):
    """Prints the cluster summary"""
    lines = [
        "Summary:",
        f"            Rack Total: {summary['total_racks']}",
        f"           Nodes Ready: {summary['ready_nodes']}/{summary['total_nodes']} ({summary['ready_ratio']*100:.2f}%)",
        f"       Validated Nodes: {summary['node_complete']}/{summary['total_nodes']} ({summary['node_ratio']*100:.2f}%)",
        f"       Validated Racks: {summary['racks_complete']}/{summary['total_racks']} ({summary['racks_ratio']*100:.2f}%)",
        f"  Validated Crossracks: {summary['xrk_complete']}/{summary['total_racks']} ({summary['xrk_ratio']*100:.2f}%)",
    ]

    for line in lines:
        if output:
            output.write(line)
        else:
            print(line)


def print_failed_validations(output=None):
    """Run and print 'kubectl validation status --only-failed' output"""
    try:
        result = subprocess.run(
            ["kubectl", "validation", "status", "--only-failed"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.CalledProcessError as e:
        stderr = e.stderr
        stdout = ""

    if stderr:
        lines = ["\n❌ Error running validation command:", stderr]
    else:
        lines = stdout.splitlines()
        start_index = next(
            (i for i, line in enumerate(lines)
             if line.lstrip().startswith("Some failures were identified. To inspect the logs, run:")),
            None
        )
        if start_index is not None:
            lines = [""] + lines[start_index:]
        else:
            lines = ["\n🎉 No failed validations found!"]

    for line in lines:
        if output:
            output.write(line)
        else:
            print(line)
