import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.table import Table
from datetime import datetime
from collections import defaultdict, OrderedDict
from textual.widgets import RichLog
from typing import List, Dict, Any, Optional, Iterable, Tuple, Set



# ====================================================================================================
# ===== CONSTANTS ====================================================================================
# ====================================================================================================
ALLOWED_POD_PREFIXES = ["bios-conformance", "mcu-comm-server", "tspd"]
EXPECTED_POD_COUNTS = {"bios-conformance": 9, "mcu-comm-server": 9, "tspd": 9}
REQUIRED_POD_TYPES = set(EXPECTED_POD_COUNTS)
EXPECTED_NODES = {f"gn{i}" for i in range(1, 10)}
EXPECTED_FW_VERSION = "0.0.15"
FW_LABEL_KEYS: List[str] = [f"validation.groq.io/firmware-bundle-groqA{i}" for i in range(8)]


# ====================================================================================================
# ===== TIMESTAMPT / COLOR HELPERS ===================================================================
# ====================================================================================================
def format_timestamp(ts: str) -> str:
    try:
        dt_utc = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone()
        return dt_local.strftime("%Y-%m-%d %I:%M %p %Z")
    except Exception:
        return ts or "N/A"


COLOR_MAP = {
    "green": {"success", "healthy", "ready"},
    "blue": {"in progress", "running"},
    "cyan": {"pending", "started"},
    "bright white": {"not made"},
    "yellow": {"not started", "info"},
    "red": {"failure", "fault", "warning(s)", "failed-retryable", "notready", "failed"},
}


STATUS_COLOR_LOOKUP = {status: color for color, statuses in COLOR_MAP.items() for status in statuses}


def colorize(text: str) -> str:
    if not text or ("[" in text and "]" in text):
        return text
    return f"[{STATUS_COLOR_LOOKUP.get(text.strip().lower(), 'red')}]{text.title()}[/]"



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


def kubectl_get_json_nodes_by_rack(rack_name: str) -> dict: # NEW
    cmd = ["kubectl", "get", "nodes", "-l", f"topology.groq.io/rack={rack_name}", "-o", "json"]
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
        return json.loads(output)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return {"items": []}


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
def _normalize_rows(rows: Any) -> List[Dict[str, Any]]:
    """Accept list[dict], dict[str, dict], or full cluster payload {'summary':..., 'racks':[...]}."""
    if rows is None:
        return []
    if isinstance(rows, dict) and isinstance(rows.get("racks"), list):
        return [r for r in rows["racks"] if isinstance(r, dict)]
    if isinstance(rows, list):
        return [r for r in rows if isinstance(r, dict)]
    if isinstance(rows, dict):
        out = []
        for _, v in rows.items():
            if isinstance(v, dict):
                rec = dict(v)
                if "node" not in rec and ("Node" in rec or "name" in rec):
                    rec.setdefault("node", rec.get("Node", rec.get("name")))
                out.append(rec)
        return out
    return []


def _filter_by_racks(rows: List[Dict[str, Any]], racks: Optional[Iterable[str]]) -> List[Dict[str, Any]]:
    if not racks:
        return rows
    rs = set(racks)
    if any("rack" in r for r in rows):
        return [r for r in rows if r.get("rack") in rs]
    return rows


def display_cluster_table(
    rows: Any,
    racks: Optional[Iterable[str]] = None,
    *,
    title: Optional[str] = None,
    expected_fw_version: str = EXPECTED_FW_VERSION,
    selector: str = "groq.node=true",
    context: Optional[str] = None,
    render: bool = True,
) -> Table:
    """
    Cluster overview with a single 'FW Version' column placed right after 'tspd'.

    Rack view:
      - If all nodes OK: shows expected version (green), e.g., "0.0.15"
      - Else: shows offending value groups, e.g., "0.0.12: gn2 | Missing: gn3 | Invalid: gn4,gn7"

    Node view:
      - If OK: expected version (green)
      - If bad: offending node's value label ("0.0.12", "Missing", or "Invalid") in red
    """
    console = Console()
    ctx = context or get_kubectl_context()

    norm_rows = _normalize_rows(rows)
    norm_rows = _filter_by_racks(norm_rows, racks)

    is_rack_view = any("rack" in r for r in norm_rows) and not any("node" in r for r in norm_rows)

    # ----- Choose base columns (insert "FW Version" right after 'tspd') -----
    if is_rack_view:
        pod_prefixes: List[str] = []
        seen = set()
        for r in norm_rows:
            for p in (r.get("pod_health") or {}):
                if p not in seen:
                    seen.add(p)
                    pod_prefixes.append(p)

        base_cols = ["Rack", "Health"]
        inserted_fw = False
        for p in pod_prefixes:
            base_cols.append(p)
            if p == "tspd":
                base_cols.append("FW Version")
                base_cols.append("BMC Match")
                inserted_fw = True
        if not inserted_fw:
            base_cols.append("FW Version")  # if tspd not present, put FW after pods
            base_cols.append("BMC Match")

        base_cols += ["Node GV", "Rack GV", "XRK Name", "XRK GV"]

    else:
        seen_keys: List[str] = []
        for r in norm_rows:
            for k in r.keys():
                if k not in seen_keys:
                    seen_keys.append(k)
        base_cols = (["node"] + [k for k in seen_keys if k != "node"]) if "node" in seen_keys else seen_keys
        base_cols.append("FW Version")

    table_title = title or f"Cluster Overview - {ctx or 'unknown context'}"
    table = Table(title=table_title, header_style="white")

    for col in base_cols:
        label = col if isinstance(col, str) else str(col)
        if label.lower() in ("node", "rack"):
            table.add_column(label.title(), justify="left", no_wrap=True)
        else:
            table.add_column(label, justify="center")

    # ----- Firmware mismatches -----
    mismatched_nodes, mismatch_details = fetch_firmware_mismatch_nodes(
        expected_version=expected_fw_version,
        selector=selector,
        context=ctx,
    )
    bmc_offenders = fetch_bmc_mismatch_nodes(context=ctx)

    def _node_offending_value(node: str) -> str:
        """
        Summarize a node's offending value from its mismatch details:
          - single non-MISSING value -> that value (e.g., '0.0.12')
          - only MISSING -> 'Missing'
          - multiple differing values / mix -> 'Invalid'
        """
        details = mismatch_details.get(node, {})
        if not details:
            return expected_fw_version  # shouldn't be called for OK nodes, but safe
        uniq = set(details.values())
        non_missing = {v for v in uniq if v != "MISSING"}
        if len(uniq) == 1 and "MISSING" in uniq:
            return "Missing"
        if len(non_missing) == 1 and "MISSING" not in uniq:
            return next(iter(non_missing))
        return "Invalid"

    def rack_fw_value(rack: str) -> str:
        offenders = [f"gn{i}" for i in range(1, 10) if f"{rack}-gn{i}" in mismatched_nodes]
        for i in range(1, 10):
            node = f"{rack}-gn{i}"
            if node in mismatched_nodes:
                label = _node_offending_value(node)
                offenders.append((label, f"gn{i}"))
        if not offenders:
            return f"[green]{expected_fw_version}[/green]"

        # group by offending value for clarity (existing logic)
        grouped = {}
        for i in range(1, 10):
            node = f"{rack}-gn{i}"
            if node in mismatched_nodes:
                details = mismatch_details.get(node, {})
                uniq = set(details.values())
                non_missing = {v for v in uniq if v != "MISSING"}
                if len(uniq) == 1 and "MISSING" in uniq:
                    label = "Missing"
                elif len(non_missing) == 1 and "MISSING" not in uniq:
                    label = next(iter(non_missing))
                else:
                    label = "Invalid"
                grouped.setdefault(label, []).append(f"gn{i}")
        parts = [f"{label}: {','.join(sfx)}" for label, sfx in grouped.items()]
        return f"[red]{' | '.join(parts)}[/red]"

    # ----- Precompute firmware + BMC offenders -----
    mismatched_nodes, mismatch_details = fetch_firmware_mismatch_nodes(
        expected_version=expected_fw_version, selector=selector, context=ctx
    )
    bmc_offenders, bmc_details = fetch_bmc_mismatch_nodes(context=ctx)  # <-- now returns details too
    
    def rack_bmc_value(rack: str) -> str:
        # Group offenders by their value label: e.g., "false: gn2,gn5 | Missing: gn3"
        grouped: Dict[str, list] = {}
        for i in range(1, 10):
            node = f"{rack}-gn{i}"
            if node in bmc_offenders:
                label = bmc_details.get(node, "Missing")
                grouped.setdefault(label, []).append(f"gn{i}")
        if not grouped:
            return "[green]True[/green]"
        parts = [f"{label}: {','.join(sfx)}" for label, sfx in grouped.items()]
        return f"[red]{' | '.join(parts)}[/red]"

    def node_fw_value(node: str) -> str:
        if node in mismatched_nodes:
            details = mismatch_details.get(node, {})
            uniq = set(details.values())
            non_missing = {v for v in uniq if v != "MISSING"}
            if len(uniq) == 1 and "MISSING" in uniq:
                label = "Missing"
            elif len(non_missing) == 1 and "MISSING" not in uniq:
                label = next(iter(non_missing))
            else:
                label = "Invalid"
            return f"[red]{label}[/red]"
        return f"[green]{expected_fw_version}[/green]"

    # ----- Rows -----
    for r in norm_rows:
        cells: List[str] = []
        if is_rack_view:
            rack = r.get("rack", "")
            health = colorize(r.get("health", "-"))
            pod_health = r.get("pod_health", {}) or {}

            for col in base_cols:
                if col == "Rack":
                    cells.append(rack)
                elif col == "Health":
                    cells.append(health)
                elif col in ("Node GV", "Rack GV", "XRK Name", "XRK GV"):
                    if col == "Node GV":
                        cells.append(colorize(r.get("node_status", "-")))
                    elif col == "Rack GV":
                        cells.append(colorize(r.get("rack_status", "-")))
                    elif col == "XRK Name":
                        cells.append(r.get("xrk_name") or "")
                    elif col == "XRK GV":
                        cells.append(colorize(r.get("xrk_status", "-")))
                elif col == "FW Version":
                    cells.append(rack_fw_value(rack))
                elif col == "BMC Match":            # <— NEW
                    cells.append(rack_bmc_value(rack))
                else:  # pod columns
                    cells.append(colorize(pod_health.get(col, "-")))
        else:
            for col in base_cols:
                if col == "FW Version":
                    node_name = r.get("node") or r.get("Node") or r.get("name") or ""
                    cells.append(node_fw_value(node_name))
                else:
                    v = r.get(col, "")
                    cells.append("" if v is None else str(v))

        table.add_row(*cells)

    if render:
        console.print(table)
    return table


def fetch_bmc_mismatch_nodes(
    *,
    context: str = "",
    exclude_substrings: Tuple[str, ...] = ("c0g", "c0n"),
) -> Tuple[Set[str], Dict[str, str]]:
    """
    JSON-native equivalent of:
      kubectl get nodes -l groq.node.bmc-match!=true | awk 'NR>1 {print $1}' | grep -v c0g | grep -v c0n | sort -V

    Returns:
      offenders: set of node names where groq.node.bmc-match != "true"
      details:   { node_name: offending_value }, where offending_value is:
                  - "Missing" (label absent)
                  - the actual label string (e.g. "false", "invalid", etc.), case-preserved
    """
    cmd = ["kubectl"]
    if context:
        cmd += ["--context", context]
    cmd += ["get", "nodes", "-o", "json"]  # get all, filter ourselves for full control

    try:
        raw = subprocess.check_output(cmd, text=True)
        data = json.loads(raw)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return set(), {}

    offenders: Set[str] = set()
    details: Dict[str, str] = {}

    for item in data.get("items", []):
        name = (item.get("metadata") or {}).get("name", "")
        if not name:
            continue
        if any(s in name for s in exclude_substrings):
            continue

        labels = (item.get("metadata") or {}).get("labels", {}) or {}
        v = labels.get("groq.node.bmc-match", None)
        if v is None:
            offenders.add(name)
            details[name] = "Missing"
            continue

        v_norm = str(v).strip().lower()
        if v_norm != "true":
            offenders.add(name)
            details[name] = str(v)  # keep original casing for display

    return offenders, details


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
        
        # Fetch node labels to get firmware versions
        nodes_json = kubectl_get_json_nodes_by_rack(rack_name)
        firmware_versions = {}
        for node in nodes_json.get("items", []):
            node_name = node.get("metadata", {}).get("name")
            if node_name:
                firmware = node.get("metadata", {}).get("labels", {}).get("validation.groq.io/firmware-bundle-lowest")
                firmware_versions[node_name] = firmware

        return rack_name, {
            "dashboard": dashboard,
            "entries": entries,
            "firmware_versions": firmware_versions,
        }

    except Exception as e:
        return rack_name, e


def _build_node_table(rack_name: str, node_data: dict, render: bool = True) -> Table | None:
    console = Console()
    entries = node_data["entries"]
    dashboard = node_data["dashboard"]
    firmware_versions = node_data.get("firmware_versions", {})

    # Build per-node tspd status (unchanged from your logic)
    required_pod_types = {"tspd"}
    pods_seen = defaultdict(set)
    per_node_pod_status = defaultdict(dict)
    pod_issues_map = defaultdict(list)

    for pod_base, ready, status, node in entries:
        if pod_base in required_pod_types:
            pods_seen[node].add(pod_base)
            per_node_pod_status[node][pod_base] = status
            if (status or "").lower() != "running":
                pod_issues_map[node].append(f"[yellow]{pod_base} (not running)[/yellow]")

    all_nodes = [f"{rack_name}-gn{i}" for i in range(1, 10)]
    for node in all_nodes:
        missing = required_pod_types - pods_seen[node]
        for pod_base in missing:
            pod_issues_map[node].append(f"[red]{pod_base} (missing)[/red]")

    context = get_kubectl_context()

    # 10 columns total: "Validator" + gn1..gn9
    table = Table(title=f"{rack_name} - Node Dashboard - {context}", header_style="white")
    table.add_column("Validator", style="cyan", no_wrap=True)
    for i in range(1, 10):
        table.add_column(f"gn{i}", justify="center")

    # ===== Top block: validators =====
    for validator, nodes in dashboard.items():
        row = [validator]
        for i in range(1, 10):
            key = f"gn{i}"
            status = nodes.get(key, {}).get("results_status", "N/A")
            row.append(colorize(status))
        table.add_row(*row)

    # ===== Pod block (e.g., tspd) =====
    table.add_section()
    for pod_base in sorted(required_pod_types):
        row = [pod_base]
        for i in range(1, 10):
            node = f"{rack_name}-gn{i}"
            if pod_base in per_node_pod_status[node]:
                status = per_node_pod_status[node][pod_base]
            elif pod_issues_map[node]:
                status = "Missing"
            else:
                status = "-"
            row.append(colorize(status))
        table.add_row(*row)

    # ===== FW block (own section) =====
    table.add_section()
    fw_row = ["FW Bundle Lowest"]
    for i in range(1, 10):
        node_name = f"{rack_name}-gn{i}"
        version = firmware_versions.get(node_name)
        if version == EXPECTED_FW_VERSION:
            fw_row.append(f"[green]{version}[/green]")
        elif version:
            fw_row.append(f"[red]{version}[/red]")
        else:
            fw_row.append("[red]Missing[/red]")
    table.add_row(*fw_row)

    # ===== BMC block (own section, separate from FW) =====
    table.add_section()
    bmc_offenders, bmc_details = fetch_bmc_mismatch_nodes(context=context)

    bmc_row = ["BMC Match"]
    for i in range(1, 10):
        node_name = f"{rack_name}-gn{i}"
        if node_name in bmc_offenders:
            label = bmc_details.get(node_name, "Missing")
            # normalize for nicer display
            friendly = "Missing" if label is None or str(label).strip() == "" else str(label)
            bmc_row.append(f"[red]{friendly}[/red]")
        else:
            bmc_row.append("[green]True[/green]")
    table.add_row(*bmc_row)

    if render:
        console.print(table)
        return None
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
    """Collects only tspd pod entries for a list of base nodes"""
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
                pod_base = base_name(pod["metadata"]["name"])
                if pod_base != "tspd":
                    continue
                if pod.get("status", {}).get("phase") == "Succeeded":
                    continue

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


def summarize_status(pod_states):
    """Summarizes the status of pods in a rack"""
    expected_nodes = [f"gn{i}" for i in range(1, 10)]
    missing_nodes = [gn for gn in expected_nodes if gn not in pod_states]
    if missing_nodes:
        return "Missing: " + ", ".join(sorted(missing_nodes))

    not_running_nodes = defaultdict(list)
    for gn, state in pod_states.items():
        if state != "running":
            not_running_nodes[state].append(gn)

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

        rack_data["health"] = "; ".join(messages) if messages else "Ready"

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
    """Get cluster data, node and tspd pod health, and summaries"""
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(kubectl_get_json_resource, "nodes"): "nodes",
            executor.submit(kubectl_get_json_validation): "gv",
        }
        results = {name: future.result() for future, name in ((f, futures[f]) for f in as_completed(futures))}

    # Rack health info
    racks = get_rack_health_info(results["nodes"])
    rack_list = sorted(racks.values(), key=lambda r: natural_sort_key(r["rack"]))

    # Parse only tspd pods
    pod_summary, _ = parse_pods()  # existing function
    tspd_summary = {rack: {"tspd": pod_summary[rack]["tspd"]} for rack in pod_summary if "tspd" in pod_summary[rack]}

    # Build pod health per rack (only tspd)
    for rack in rack_list:
        rack_name = rack["rack"]
        states = tspd_summary.get(rack_name, {}).get("tspd", {})
        rack["pod_health"] = {"tspd": summarize_status(states)}

    # Node and rack counts
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
            "racks_ratio": rack_complete / len(rack_list) if rack_list else 0.0,
            "xrk_complete": xrk_complete,
            "xrk_ratio": xrk_complete / len(rack_list) if rack_list else 0.0,
        },
        "racks": rack_list,
    }


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



# ====================================================================================================
# ===== FAULTS / TICKETS =============================================================================
# ====================================================================================================
def handle_faults(args):
    filter_arg = args.filter.lower() if args.filter else None

    def run_command(cmd):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"Error running command {' '.join(cmd)}:\n{e.stderr}", file=sys.stderr)
            sys.exit(1)

    def natural_keys(text):
        def atoi(t):
            return int(t) if t.isdigit() else t.lower()
        return [atoi(c) for c in re.split(r'(\d+)', text)]

    faults_json = run_command(['kubectl', 'get', 'faults', '-o', 'json'])
    tickets_json = run_command(['kubectl', 'get', 'tickets', '-o', 'json'])

    faults = json.loads(faults_json).get('items', [])
    tickets = json.loads(tickets_json).get('items', [])

    ticket_map = {t['metadata']['name']: t for t in tickets}

    rows = []
    header = ["COMPONENT", "FAULTTYPE", "PHASE", "JIRASTATUS", "TICKETURL"]
    rows.append(header)

    for fault in faults:
        spec = fault.get('spec', {})
        status = fault.get('status', {})
        component = spec.get('component', 'N/A')

        if filter_arg:
            parts = component.split('/')
            if len(parts) < 2:
                continue
            chassis_rack = (parts[0] + parts[1]).lower()
            if chassis_rack != filter_arg:
                continue

        faulttype = spec.get('faultType', 'N/A')
        phase = status.get('phase', 'N/A')

        ticket_ref = status.get('ticketRef', {})
        ticket_name = ticket_ref.get('name')

        jira_status = 'N/A'
        ticket_url = 'N/A'

        if ticket_name and ticket_name in ticket_map:
            ticket = ticket_map[ticket_name]
            ticket_status = ticket.get('status', {})
            jira_status = ticket_status.get('jiraStatus', 'N/A')
            ticket_url = ticket_status.get('ticketURL', 'N/A')

        rows.append([component, faulttype, phase, jira_status, ticket_url])

    sorted_rows = [header] + sorted(rows[1:], key=lambda r: natural_keys(r[0]))
    col_widths = [max(len(str(row[i])) for row in sorted_rows) for i in range(len(header))]

    for i, row in enumerate(sorted_rows):
        line = "  ".join(str(cell).ljust(col_widths[idx]) for idx, cell in enumerate(row))
        print(line)
        if i == 0:
            print("  ".join("-" * w for w in col_widths))


def fetch_faults():
    def run_command(cmd):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"Error running command {' '.join(cmd)}:\n{e.stderr}", file=sys.stderr)
            sys.exit(1)

    faults_json = run_command(['kubectl', 'get', 'faults', '-o', 'json'])
    tickets_json = run_command(['kubectl', 'get', 'tickets', '-o', 'json'])

    faults = json.loads(faults_json).get('items', [])
    tickets = json.loads(tickets_json).get('items', [])
    ticket_map = {t['metadata']['name']: t for t in tickets}

    rows = []
    header = ["COMPONENT", "FAULTTYPE", "PHASE", "JIRASTATUS", "TICKETURL"]
    rows.append(header)

    for fault in faults:
        spec = fault.get('spec', {})
        status = fault.get('status', {})
        component = spec.get('component', 'N/A')

        faulttype = spec.get('faultType', 'N/A')
        phase = status.get('phase', 'N/A')

        ticket_ref = status.get('ticketRef', {})
        ticket_name = ticket_ref.get('name')

        jira_status = 'N/A'
        ticket_url = 'N/A'

        if ticket_name and ticket_name in ticket_map:
            ticket = ticket_map[ticket_name]
            ticket_status = ticket.get('status', {})
            jira_status = ticket_status.get('jiraStatus', 'N/A')
            ticket_url = ticket_status.get('ticketURL', 'N/A')

        rows.append([component, faulttype, phase, jira_status, ticket_url])

    return rows


def display_faults(rows, racks=None):
    header, *data = rows
    if racks:
        racks = [r.lower() for r in racks]
        data = [r for r in data if rack_key(r[0]) in racks]

    if not data:
        print("\nNo faults found.")
        return

    # natural sort by component
    def natural_keys(text):
        def atoi(t):
            return int(t) if t.isdigit() else t.lower()
        return [atoi(c) for c in re.split(r'(\d+)', text)]

    sorted_rows = [header] + sorted(data, key=lambda r: natural_keys(r[0]))
    col_widths = [max(len(str(row[i])) for row in sorted_rows) for i in range(len(header))]

    print("\nFaults:")
    for i, row in enumerate(sorted_rows):
        line = "  ".join(str(cell).ljust(col_widths[idx]) for idx, cell in enumerate(row))
        print(line)
        if i == 0:
            print("  ".join("-" * w for w in col_widths))


def rack_key(component: str) -> str:
    """
    Extract rack key like 'c0r88' from a component string
    e.g. 'C0/R88/N5/C4' → 'c0r88'
    """
    comp = component.lower()
    match = re.search(r'c\d+/r\d+', comp)
    if match:
        return match.group(0).replace("/", "")
    return comp


def expand_crossrack_names(racks):
    """Expand crossrack names like 'c0r1-c0r2' into ['c0r1', 'c0r2']."""
    expanded = []
    for r in racks:
        if "-" in r:
            parts = r.split("-")
            # handle "c0r1-c0r2"
            if len(parts) == 2 and parts[0][:2] == parts[1][:2]:  # same chassis prefix
                chassis = parts[0][:2]  # "c0"
                start = int(parts[0][2:].replace("r", ""))
                end = int(parts[1][2:].replace("r", ""))
                for i in range(start, end + 1):
                    expanded.append(f"{chassis}r{i}")
            else:
                expanded.extend(parts)
        else:
            expanded.append(r)
    return expanded



# ====================================================================================================
# ===== FIRMWARE =====================================================================================
# ====================================================================================================
def fetch_firmware_mismatch_nodes(
    expected_version: str = EXPECTED_FW_VERSION,
    selector: str = "groq.node=true",
    context: str = "",
) -> Tuple[Set[str], Dict[str, Dict[str, str]]]:
    """
    Return:
      - a set of node names that have ANY GroqA[0-7] bundle label != expected_version (or MISSING)
      - details: {node: {label_key: actual_value (or 'MISSING') for mismatches}}

    Mirrors:
      kubectl get nodes -l groq.node=true -o json | jq -r '
        .items[] |
        select((... any groqA* label != "0.0.15")) |
        .metadata.name' | sort -V
    """
    cmd = ["kubectl"]
    if context:
        cmd += ["--context", context]
    cmd += ["get", "nodes", "-l", selector, "-o", "json"]

    try:
        raw = subprocess.check_output(cmd, text=True)
        data = json.loads(raw)
    except subprocess.CalledProcessError as e:
        # Return empty to avoid breaking the table; you can render a warning elsewhere
        return set(), {}
    except json.JSONDecodeError:
        return set(), {}

    mismatched: Set[str] = set()
    details: Dict[str, Dict[str, str]] = {}

    for item in data.get("items", []):
        name = item.get("metadata", {}).get("name", "")
        labels = item.get("metadata", {}).get("labels", {}) or {}
        node_bad: Dict[str, str] = {}
        for k in FW_LABEL_KEYS:
            v = labels.get(k, "MISSING")
            if v != expected_version:
                node_bad[k] = v
        if node_bad:
            mismatched.add(name)
            details[name] = node_bad

    return mismatched, details
