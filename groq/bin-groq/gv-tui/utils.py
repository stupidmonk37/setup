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


def process_node_validations(rack_name: str, validations: dict) -> dict:
    summary = {}
    for test_name, nodes_data in validations.items():
        node_group = {}
        for i in range(1, 10):
            short = f"gn{i}"
            full = f"{rack_name}-{short}"
            node_group[short] = nodes_data.get(full, {})

        phases = []
        for node_set, pdata in node_group.items():
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



# ====================================================================================================
# ===== DISPLAY TABLES ===============================================================================
# ====================================================================================================
def display_cluster_table(data, rack_filter=None, render=True) -> Table | None:
    context = get_kubectl_context()
    table = Table(title=f"Groq Validation Status - {context}", header_style="white")
    pod_prefixes = []
    if data["racks"]:
        for rack in data["racks"]:
            pod_prefixes.extend(rack.get("pod_health", {}).keys())

        pod_prefixes = sorted(set(pod_prefixes))

    columns = ["Rack", "Health"] + pod_prefixes + ["Node GV", "Rack GV", "XRK Name", "XRK GV"]
    for col in columns:
        table.add_column(col)

    for rack in data["racks"]:
        if rack_filter and rack["rack"] not in rack_filter:
            continue

        row = [rack["rack"], colorize(rack["health"])]
        for prefix in pod_prefixes:
            status = rack.get("pod_health", {}).get(prefix, "-")
            row.append(colorize(status))

        row.extend([
            colorize(rack["node_status"]),
            colorize(rack["rack_status"]),
            rack.get("xrk_name") or "",
            colorize(rack.get("xrk_status")),
        ])
        table.add_row(*row)

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
            validations = fetch_validations(rack_name)
            dashboard = process_node_validations(rack_name, validations)
            entries = collect_pod_entries([rack_name])
            pod_status_map = {}
            pod_ready_map = {}
            pod_issues_map = defaultdict(list)
            pods_seen = defaultdict(set)
            for name, ready, status, node in entries:
                pod_base = base_name(name)
                pod_ready_map[node] = ready
                pod_status_map[node] = status
                if pod_base in REQUIRED_POD_TYPES:
                    pods_seen[node].add(pod_base)
                    if status.lower() != "running":
                        pod_issues_map[node].append(f"[yellow]{pod_base} (not running)[/yellow]")

            all_nodes = [f"{rack_name}-gn{i}" for i in range(1, 10)]
            for node in all_nodes:
                missing = REQUIRED_POD_TYPES - pods_seen[node]
                for pod_base in missing:
                    pod_issues_map[node].append(f"[red]{pod_base} (missing)[/red]")

            per_node_pod_status = defaultdict(dict)
            for name, _, status, node in entries:
                pod_base = base_name(name)
                if pod_base in REQUIRED_POD_TYPES:
                    per_node_pod_status[node][pod_base] = status

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
            for pod_base in REQUIRED_POD_TYPES:
                row = [pod_base]
                for i in range(1, 10):
                    node = f"{rack_name}-gn{i}"
                    if pod_base in per_node_pod_status[node]:
                        status = per_node_pod_status[node][pod_base]

                    elif pod_base in pod_issues_map[node]:
                        status = "[red]Missing[/red]"

                    else:
                        status = "-"

                    row.append(colorize(status))

                table.add_row(*row)

            if render:
                console.print(table)

            tables.append(table)

        except Exception as e:
            if render:
                console.print(f"[red]Error processing rack {rack_name}: {e}[/red]")

            else:
                tables.append(None)

    return tables if not render else None


def display_rack_table(rack_names: list[str], render: bool = True) -> list[Table] | None:
    console = Console()
    tables = []
    for rack_name in rack_names:
        try:
            rack_data = kubectl_get_json_validation(rack_name)
            context = get_kubectl_context()
            table = Table(title=f"{rack_name} - Rack Validation Status - {context}", header_style="white")
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



# ====================================================================================================
# ===== PODS =========================================================================================
# ====================================================================================================
def collect_pod_entries(base_nodes):
    entries = []
    for base in base_nodes:
        for node in [f"{base}-gn{i}" for i in range(1, 10)]:
            pods = get_pods_json(field_selector=f"spec.nodeName={node}")
            for pod in pods:
                if pod.get("status", {}).get("phase") == "Succeeded":
                    continue

                name = pod["metadata"]["name"]
                pod_base = base_name(name)  # consistent use here
                status = pod["status"]["phase"]
                node_name = pod["spec"]["nodeName"]
                container_statuses = pod.get("status", {}).get("containerStatuses", [])
                total = len(container_statuses)
                ready = sum(int(bool(cs.get("ready"))) for cs in container_statuses)

                entries.append((pod_base, f"{ready}/{total}", status, node_name))

    return sorted(entries, key=lambda x: (x[0], x[3]))


def aggregate_pod_issues(entries):
    node_issues = defaultdict(list)
    pods_seen = defaultdict(set)
    for name, _, status, node in entries:
        if not is_node_name(node):
            continue
        
        pod_base = base_name(name)
        if pod_base in REQUIRED_POD_TYPES:
            pods_seen[node].add(pod_base)
            if status.lower() != "running":
                node_issues[node].append(f"[yellow]{pod_base} (not running)[/yellow]")

    all_nodes = set(pods_seen) | {e[3] for e in entries if is_node_name(e[3])}
    for node in all_nodes:
        missing = REQUIRED_POD_TYPES - pods_seen[node]
        for pod_base in missing:
            node_issues[node].append(f"[red]{pod_base} (missing)[/red]")

    return node_issues


def build_pod_status_ui(entries, base_nodes):
    table = Table(title=f"Pod Statuses for: {', '.join(base_nodes)}", header_style="white", show_lines=False)
    table.add_column("NAME", style="cyan", overflow="fold")
    table.add_column("READY", justify="center")
    table.add_column("STATUS", justify="center")
    table.add_column("NODE", justify="center")
    last_base = None
    for name, ready, status, node in entries:
        current_base = base_name(name)
        if last_base and current_base != last_base:
            table.add_section()

        table.add_row(name, ready, colorize(status), node)
        last_base = current_base

    node_issues = aggregate_pod_issues(entries)
    if node_issues:
        lines = [f"{node}\n  " + "\n  ".join(issues) for node, issues in sorted(node_issues.items())]
        summary_text = Text.from_markup("\n\n".join(lines))
        max_width = max(
            Measurement.get(Console(), Console().options, Text.from_markup(line)).maximum
            for line in lines
        )
        summary_panel = Panel(
            Align.right(summary_text),
            title="Summary: Pod Issues by Node",
            title_align="center",
            border_style="magenta",
            width=max_width + 4,
        )
    else:
        message = "All expected pods are running on all nodes."
        summary_panel = Panel(
            Align(message, align="right"),
            title="Summary",
            title_align="center",
            border_style="green",
            width=len(message) + 4,
        )

    return table, summary_panel


def parse_pods(filter_base_nodes=None):
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


def summarize_status(pod_states):
    expected_nodes = [f"gn{i}" for i in range(1, 10)]
    missing_nodes = [gn for gn in expected_nodes if gn not in pod_states]
    if missing_nodes:
        return "Missing: " + ", ".join(missing_nodes)

    not_running_nodes = [(gn, state) for gn, state in pod_states.items() if state != "running"]
    if not_running_nodes:
        return ", ".join(f"{state}: {gn}" for gn, state in not_running_nodes)

    return "Running"



# ====================================================================================================
# ===== CLUSTER ======================================================================================
# ====================================================================================================
def cluster_table_default_status(name):
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
    for item in items:
        name = item.get("metadata", {}).get("name", "")
        status = item.get("status", {}).get("status", "Not Made")
        if is_rack_name(name):
            key = name
            field = "rack_status"

        elif is_xrk_name(name):
            key = name.split("-", 1)[0]
            racks[key]["xrk_name"] = name
            field = "xrk_status"

        else:
            key = extract_rack_prefix(name)
            field = "node_status"

        if key:
            if key not in racks:
                racks[key] = cluster_table_default_status(key)

            racks[key][field] = status


def get_data_cluster():
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(kubectl_get_json_resource, "nodes"): "nodes",
            executor.submit(kubectl_get_json_validation): "gv",
        }
        results = {name: future.result() for future, name in ((f, futures[f]) for f in as_completed(futures))}

    racks = get_rack_health_info(results["nodes"])
    update_rack_statuses(results["gv"].get("items", []), racks)
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
    node_complete = sum(1 for r in rack_list if r["node_status"] == "Success") * 9
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
    if racks:
        filtered_racks = {r["rack"]: r for r in data["racks"] if r["rack"] in racks}
        print(json.dumps(filtered_racks, indent=2))

    else:
        print(json.dumps(data["racks"], indent=2))


def output_cluster_table(data, rack_filter):
    display_cluster_table(data, rack_filter=rack_filter)


def print_cluster_summary(output=None, summary=None):
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
        lines = ["\n[red]Error running validation command:[/red]", stderr]
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
            lines = ["\n[green]🎉 No failed validations found! 🎉[/green]"]

    for line in lines:
        if output:
            output.write(line)
        else:
            print(line)

