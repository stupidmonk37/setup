# server.py
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Tuple
import subprocess
import json
import re
from utils import (
    get_data_cluster,
    fetch_validations,
    process_node_validations,
    collect_pod_entries,
    kubectl_get_json_nodes_by_rack,
    expand_crossrack_names,
    rack_key,
    determine_validation_phases,
    kubectl_get_json_validation,
    get_inference_engine_pods,
)
from bmctools import run_pre_validation_check, get_rack_list_fast, run_detailed_rack_analysis
from functools import lru_cache
from kubernetes import client, config

# ---- Context-aware Kubernetes clients (cached) ----
@lru_cache(maxsize=16)
def get_kube_clients(context: Optional[str]) -> Tuple[client.CoreV1Api, client.CustomObjectsApi]:
    config.load_kube_config(context=context)
    return client.CoreV1Api(), client.CustomObjectsApi()

def list_kube_contexts():
    contexts, active = config.list_kube_config_contexts()
    names = [c["name"] for c in (contexts or [])]
    current = active["name"] if active else None
    return {"contexts": names, "current": current}

# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
app = FastAPI(title="Groq Validation Dashboard API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/api/k8s/contexts")
def api_k8s_contexts():
    return list_kube_contexts()

class NodeBundle(BaseModel):
    rack: str
    dashboard: Dict[str, Any]
    pods: List[Dict[str, Any]]
    firmware: Dict[str, Optional[str]]
    firmware_versions: Optional[Dict[str, Optional[str]]] = None

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _run(cmd: List[str]) -> str:
    """Run a shell command and return stdout or raise HTTP 500 with stderr."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return out.stdout
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"{' '.join(cmd)} -> {e.stderr}")

def kubectl_json(args: List[str], context: Optional[str]) -> Dict[str, Any]:
    """
    Run 'kubectl ... -o json' with an optional --context override and return parsed JSON.
    Prefer this helper anywhere we shell out so the ?context=... param is respected.
    """
    base = ["kubectl"]
    if context:
        base += ["--context", context]
    stdout = _run(base + args + ["-o", "json"])
    return json.loads(stdout or "{}")

def _get_fault_rows(rack_filter: Optional[List[str]] = None, *, context: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    API-friendly reimplementation of faults printing logic.
    Returns structured rows instead of printing a table.
    """
    faults = kubectl_json(["get", "faults"], context).get('items', [])
    tickets = kubectl_json(["get", "tickets"], context).get('items', [])
    ticket_map = {t['metadata']['name']: t for t in tickets}

    rows: List[Dict[str, Any]] = []
    for fault in faults:
        meta = fault.get('metadata', {})
        spec = fault.get('spec', {})
        status = fault.get('status', {})
        component = spec.get('component', 'N/A')
        ftype = spec.get('faultType', 'N/A')
        phase = status.get('phase', 'N/A')
        ticket_ref = status.get('ticketRef', {})
        ticket_name = ticket_ref.get('name')

        jira_status = 'N/A'
        ticket_url = 'N/A'
        if ticket_name and ticket_name in ticket_map:
            t = ticket_map[ticket_name]
            jira_status = t.get('status', {}).get('jiraStatus', 'N/A')
            ticket_url = t.get('status', {}).get('ticketURL', 'N/A')

        rows.append({
            'component': component,
            'faultType': ftype,
            'phase': phase,
            'jiraStatus': jira_status,
            'ticketUrl': ticket_url,
            'rackKey': rack_key(component) if component else None,
        })

    if rack_filter:
        rset = {r.lower() for r in rack_filter}
        rows = [r for r in rows if (r.get('rackKey') or '').lower() in rset]

    # natural-ish sort by component label
    def nkey(text: str):
        def atoi(t):
            return int(t) if t.isdigit() else t.lower()
        return [atoi(c) for c in re.split(r'(\d+)', text or '')]

    rows.sort(key=lambda r: nkey(r.get('component', '')))
    return rows

@app.get('/api/cluster')
def api_cluster(
    racks: Optional[List[str]] = Query(None),
    context: Optional[str] = Query(default=None)
) -> Dict[str, Any]:
    """Cluster overview: rack health, pod health, GV ratios, summary."""
    data = get_data_cluster(context=context)
    if racks:
        rset = set(racks)
        data['racks'] = [r for r in data.get('racks', []) if r.get('rack') in rset]
    return data

@app.get('/api/nodes')
def api_nodes(
    racks: List[str] = Query(default=[]),
    context: Optional[str] = Query(default=None)
) -> List[NodeBundle]:
    """Per-rack node validations + tspd pods + firmware labels."""
    bundles: List[NodeBundle] = []
    for rack in racks:
        # Build dashboard via your validation pipeline
        validations = fetch_validations(rack, context=context)
        dashboard = process_node_validations(rack, validations)

        # Normalize pods (tuples → dicts) for Pydantic/JSON
        raw_pods = collect_pod_entries([rack], context=context)
        pods: List[Dict[str, Any]] = []
        for item in raw_pods:
            if isinstance(item, dict):
                pods.append(item)
            elif isinstance(item, (list, tuple)):
                # common shape: (name, ready, phase, node)
                name = item[0] if len(item) > 0 else None
                ready = item[1] if len(item) > 1 else None
                phase = item[2] if len(item) > 2 else None
                node  = item[3] if len(item) > 3 else None
                pods.append({"name": name, "ready": ready, "phase": phase, "node": node})
            else:
                pods.append({"raw": item})

        # Firmware by node
        nodes_json = kubectl_get_json_nodes_by_rack(rack, context)
        firmware: Dict[str, Optional[str]] = {}
        for node in nodes_json.get('items', []):
            name = node.get('metadata', {}).get('name')
            if not name:
                continue
            fw = node.get('metadata', {}).get('labels', {}).get('validation.groq.io/firmware-bundle-lowest')
            labels = node.get('metadata', {}).get('labels', {}) or {}
            # Prefer explicit “lowest” bundle, but be resilient to naming
            fw = (
                labels.get('validation.groq.io/firmware-bundle-lowest')
                or labels.get('validation.groq.io/firmware-bundle')
                or labels.get('firmware-bundle-lowest')
                or labels.get('firmware-bundle')
            )
            firmware[name] = fw

        bundles.append(
            NodeBundle(
                rack=rack,
                dashboard=dashboard,
                pods=pods,
                firmware=firmware,
                firmware_versions=firmware,  # alias for UI compatibility
            )
        )
    # Return plain dicts for JSON
    return [b.dict() for b in bundles]

try:
    from utils import _build_rack_crossrack_table as build_rack_crossrack_table
except ImportError:  # pragma: no cover
    from utils import build_rack_crossrack_table  # type: ignore

_GN_KEY_RE = re.compile(r"^([a-z0-9\-]+-)?gn\d+$", re.IGNORECASE)

def _is_node_map(obj: Any) -> bool:
    """True if obj is a dict whose keys look like gn names (node-scoped)."""
    if not isinstance(obj, dict):
        return False
    keys = list(obj.keys())
    if not keys:
        return False
    return any(_GN_KEY_RE.match(str(k)) for k in keys)

def _extract_resultish(d: Any) -> Dict[str, Any]:
    """
    Normalize a test-like object to {results_status, phase, extra}.
    """
    if d is None:
        return {"results_status": None, "phase": None, "extra": None}

    if isinstance(d, (str, int, float, bool)):
        return {"results_status": d, "phase": None, "extra": None}

    if isinstance(d, list) and d:
        return _extract_resultish(d[0])

    if isinstance(d, dict):
        rs = None
        for k in (
            "results_status", "result_status", "resultsStatus", "resultStatus",
            "result", "status", "verdict", "outcome"
        ):
            if k in d and d[k] is not None:
                rs = d[k]
                break
        phase = d.get("phase") or d.get("state")
        extra = {k: v for k, v in d.items()
                 if k not in ("results_status", "result_status", "resultsStatus", "resultStatus", "phase", "state")}
        return {"results_status": rs, "phase": phase, "extra": extra or None}

    return {"results_status": str(d), "phase": None, "extra": None}

class RackGVTest(BaseModel):
    results_status: Optional[Any] = None
    phase: Optional[Any] = None
    extra: Optional[Dict[str, Any]] = None
    runs: Optional[List[Dict[str, Any]]] = None

class RackGVRow(BaseModel):
    rack: str
    rack_status: Optional[str] = None
    node_status: Optional[str] = None
    health: Optional[str] = None
    pod_health: Optional[Dict[str, Any]] = None
    xrk_name: Optional[str] = None
    xrk_status: Optional[str] = None
    tests: Dict[str, RackGVTest]

class RackGVResponse(BaseModel):
    items: List[RackGVRow]

def _crossrack_lookup_for(racks: List[str]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    """
    Build a dict[rack] -> row by calling utils._build_rack_crossrack_table(rack_name, validations)
    ONLY for the requested racks. Also return a dict of per-rack errors.
    """
    result: Dict[str, Dict[str, Any]] = {}
    errors: Dict[str, str] = {}

    for rk in racks:
        try:
            vals = fetch_validations(rk)

            try:
                row = build_rack_crossrack_table(rk, vals)  # expected signature
            except TypeError:
                # try kwargs form just in case the util uses named params
                row = build_rack_crossrack_table(rack_name=rk, validations=vals)

            # Normalize shapes
            if isinstance(row, dict):
                norm = dict(row)
            elif isinstance(row, (list, tuple)) and row:
                # pick a dict element; prefer one that matches this rack name
                cand = None
                for el in row:
                    if isinstance(el, dict):
                        rn = el.get("rack") or el.get("rack_name") or el.get("name")
                        if rn and str(rn) == rk:
                            cand = el
                            break
                        cand = cand or el
                if not cand:
                    errors[rk] = "No dict row found in list/tuple return"
                    continue
                norm = dict(cand)
            else:
                errors[rk] = f"Unexpected return type: {type(row).__name__}"
                continue

            # Ensure rack key exists
            norm.setdefault("rack", rk)
            result[rk] = norm

        except Exception as e:
            errors[rk] = f"{type(e).__name__}: {e}"

    return result, errors

_SUMMARY_KEYS = {
    "rack", "rack_name", "name",
    "health", "node_status", "rack_status",
    "pod_health", "pod_status",
    "xrk_name", "xrk_status",
    # common ratio/summary fields if present
    "ready_ratio", "node_ratio", "racks_ratio", "xrk_ratio",
    "ready_nodes", "total_nodes",
}

_TEST_CONTAINER_KEYS = ("rack_tests", "rack", "rack_gv", "rackLevel", "tests")

def _collect_rack_tests(row: Dict[str, Any]) -> Dict[str, RackGVTest]:
    """
    Given one row from the crossrack table, return only rack-level tests.
    """
    def normalize_bucket(bucket: Dict[str, Any]) -> Dict[str, RackGVTest]:
        out: Dict[str, RackGVTest] = {}
        for test_name, value in bucket.items():
            if _is_node_map(value):
                continue
            normed = _extract_resultish(value)
            out[str(test_name)] = RackGVTest(
                results_status=normed.get("results_status"),
                phase=normed.get("phase"),
                extra=normed.get("extra"),
            )
        return out

    # 1) Look inside likely containers first
    for key in _TEST_CONTAINER_KEYS:
        val = row.get(key)
        if isinstance(val, dict):
            tests = normalize_bucket(val)
            if tests:
                return tests

    # 2) Otherwise, derive by scanning the row
    derived: Dict[str, RackGVTest] = {}
    for k, v in row.items():
        if k in _SUMMARY_KEYS:
            continue
        if isinstance(v, dict) and not _is_node_map(v):
            normed = _extract_resultish(v)
            derived[str(k)] = RackGVTest(
                results_status=normed.get("results_status"),
                phase=normed.get("phase"),
                extra=normed.get("extra"),
            )
    return derived

@app.get("/api/rack_gv")
def api_rack_gv(rack: str, context: Optional[str] = Query(default=None)):
    rk = (rack or "").strip()
    if not rk:
        raise HTTPException(status_code=400, detail="rack is required")

    # --- 1) get the same source the CLI uses (rack object) ---
    rack_obj = kubectl_get_json_validation(rk, context)  # rack, not nodes
    validations = rack_obj.get("status", {}).get("validations", {})

    # --- 2) build rack table using the same utility as the CLI (side effect: none) ---
    _ = build_rack_crossrack_table(rk, validations, render=False)

    # --- 3) convert to API shape (RackGVRow: summary + tests) ---
    tests: Dict[str, RackGVTest] = {}
    for test_name, node_groups in validations.items():
        phases = determine_validation_phases(node_groups)
        runs = []
        for row in phases:
            runs.append({
                "validator": row.get("validator") or row.get("name") or "—",
                "phase": row.get("phase"),
                "result": row.get("status"),
                "started_at": row.get("started_at"),
                "duration_ms": row.get("duration_ms") or row.get("duration"),
                "extra": {k: v for k, v in row.items() if k not in ("validator","name","phase","status","started_at","duration","duration_ms")}
            })
        if phases:
            p = phases[-1]  # summarize by the last phase
            tests[str(test_name)] = RackGVTest(
                results_status=p.get("status"),
                phase=p.get("phase"),
                extra={"started_at": p.get("started_at")},
                runs=runs,
            )

    return RackGVResponse(items=[RackGVRow(rack=rk, tests=tests)])

# -----------------------------------------------------------------------------
# Other endpoints
# -----------------------------------------------------------------------------
@app.get('/api/crossracks')
def api_crossracks(names: List[str] = Query(...)) -> Dict[str, Any]:
    """Expands cross-rack names (e.g., c0r1-c0r3) into concrete racks."""
    return { 'input': names, 'expanded': expand_crossrack_names(names) }

@app.get('/api/faults')
def api_faults(
    racks: Optional[List[str]] = Query(None),
    context: Optional[str] = Query(default=None)
) -> Dict[str, Any]:
    """List faults, optionally filtered to certain racks."""
    rows = _get_fault_rows(racks, context=context)
    return { 'count': len(rows), 'rows': rows }

@app.get('/api/pre-validation')
def api_pre_validation(
    context: Optional[str] = Query(default=None)
) -> Dict[str, Any]:
    """Fast pre-validation rack list (no network testing) for initial page load."""
    try:
        # Get rack list quickly without running any tests
        results = get_rack_list_fast(context=context)
        return results
        
    except Exception as e:
        # Fallback to error response if something goes wrong
        return {
            "error": f"Pre-validation rack list failed: {str(e)}", 
            "racks": []
        }

@app.get('/api/pre-validation/{rack}')
def api_pre_validation_detailed(
    rack: str,
    context: Optional[str] = Query(default=None)
) -> Dict[str, Any]:
    """Detailed pre-validation analysis for a specific rack (runs actual network tests)."""
    try:
        # Run detailed analysis for the specific rack
        results = run_detailed_rack_analysis(rack, context=context)
        return results
        
    except Exception as e:
        # Fallback to error response if something goes wrong
        return {
            "error": f"Pre-validation detailed analysis failed for {rack}: {str(e)}", 
            "racks": []
        }

@app.get('/api/inference-pods')
def api_inference_pods(context: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """Get inference-engine pods with kubectl-like information."""
    try:
        pods = get_inference_engine_pods(context=context)
        return {
            "count": len(pods),
            "pods": pods
        }
    except Exception as e:
        return {
            "error": f"Failed to get inference-engine pods: {str(e)}", 
            "count": 0,
            "pods": []
        }

@app.get('/healthz')
def healthz():
    return {'ok': True}


from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse

app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")

@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse("dist/index.html")

@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    if full_path.startswith("api/"):
        # Let real API 404s bubble as 404s
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse("dist/index.html")
