import { useEffect, useMemo, useState, useCallback } from "react"
import logoLight from "./assets/groq-logo-black.svg";
import logoDark  from "./assets/groq-logo-white.svg";

const API = import.meta.env.VITE_API_BASE || "http://localhost:8000"
const CROSSRACK_RE = /^c\d+r\d+-c\d+r\d+$/i;
const isCrossrackId = (s) => CROSSRACK_RE.test(String(s).trim());

/* ---------- Loaders & Skeletons ---------- */
function InlineLoader({ label = "Loading…" }) {
  return (
    <div className="flex items-center gap-2 text-sm opacity-80" role="status" aria-live="polite">
      <div className="h-4 w-4 rounded-full border-2 border-neutral-300 border-t-neutral-900 dark:border-neutral-700 dark:border-t-white animate-spin" />
      <span>{label}</span>
    </div>
  );
}

function PageLoader({ show, label = "Loading data…" }) {
  if (!show) return null;
  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-white/80 dark:bg-neutral-900/80 backdrop-blur-sm"
      role="status" aria-live="polite" aria-label={label}
    >
      <div className="flex flex-col items-center gap-3">
        <div className="h-10 w-10 rounded-full border-2 border-neutral-300 border-t-neutral-900 dark:border-neutral-700 dark:border-t-white animate-spin" />
        <div className="text-sm opacity-80">{label}</div>
      </div>
    </div>
  );
}

function TableSkeleton({ cols = 6, rows = 8 }) {
  const C = Math.max(1, cols), R = Math.max(1, rows);
  return (
    <div className="overflow-auto">
      <table className="min-w-full text-sm border border-neutral-200 dark:border-neutral-700 rounded-xl">
        <thead>
          <tr className="bg-black/5 dark:bg-white/5">
            {Array.from({ length: C }).map((_, i) => (
              <th key={i} className="p-2">
                <div className="h-3 w-24 bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: R }).map((_, r) => (
            <tr key={r} className={r % 2 ? "bg-black/5 dark:bg-white/5" : ""}>
              {Array.from({ length: C }).map((_, c) => (
                <td key={c} className="p-2">
                  <div className="h-3 w-full max-w-[12rem] bg-neutral-200 dark:bg-neutral-700 rounded animate-pulse" />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


/* -------------------- hooks -------------------- */
function usePoll(fn, deps, intervalMs) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  
  // Effect for data fetching when deps change (not interval)
  useEffect(() => {
    setData(null) // Reset data when dependencies change
    setError(null)
    let cancelled = false
    const tick = async () => {
      try { const v = await fn(); if (!cancelled) setData(v) }
      catch (e) { if (!cancelled) setError(e) }
    }
    tick()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  
  // Separate effect for timer management based on interval
  useEffect(() => {
    if (!intervalMs) return
    let timer, cancelled = false
    const tick = async () => {
      try { const v = await fn(); if (!cancelled) setData(v) }
      catch (e) { if (!cancelled) setError(e) }
    }
    timer = setInterval(tick, intervalMs)
    return () => { cancelled = true; clearInterval(timer) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, ...deps])
  
  return { data, error }
}

/* -------------------- theme -------------------- */
function useTheme() {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem("theme")
    if (saved === "dark" || saved === "light") return saved
    const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches
    return prefersDark ? "dark" : "light"
  })
  useEffect(() => {
    const root = document.documentElement
    if (theme === "dark") root.classList.add("dark")
    else root.classList.remove("dark")
    localStorage.setItem("theme", theme)
  }, [theme])
  return { theme, setTheme }
}

function ThemeToggle({ theme, setTheme }) {
  const next = theme === "dark" ? "light" : "dark"
  return (
    <button
      onClick={() => setTheme(next)}
      className="border rounded-xl px-2 py-1 bg-white dark:bg-neutral-800 dark:border-neutral-700 text-sm"
      title={`Switch to ${next} mode`}
    >
      {theme === "dark" ? "🌙 Dark" : "☀️ Light"}
    </button>
  )
}

function HamburgerMenu({ currentPage, setCurrentPage }) {
  const [isOpen, setIsOpen] = useState(false)
  
  const menuOptions = [
    { value: "site-layout", label: "Site layout" },
    { value: "pre-validation", label: "Pre-Validation" },
    { value: "pdu-conformance", label: "PDU Conformance" },
    { value: "dashboard", label: "Validation Status" },
    { value: "production-status", label: "Production Status" },
  ]
  
  const currentLabel = menuOptions.find(opt => opt.value === currentPage)?.label || "Menu"
  
  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="border rounded-xl px-2 py-1 bg-white dark:bg-neutral-800 dark:border-neutral-700 text-sm flex items-center gap-2"
        title="Navigation menu"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
        {currentLabel}
      </button>
      
      {isOpen && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 z-10" 
            onClick={() => setIsOpen(false)}
          />
          
          {/* Menu */}
          <div className="absolute right-0 top-full mt-2 w-48 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 rounded-xl shadow-lg z-20">
            <div className="py-2">
              {menuOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => {
                    setCurrentPage(option.value)
                    setIsOpen(false)
                  }}
                  className={`w-full text-left px-4 py-2 text-sm hover:bg-black/5 dark:hover:bg-white/10 ${
                    currentPage === option.value ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400' : ''
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

/* -------------------- UI helpers -------------------- */
function norm(s) { return String(s ?? "").trim().toLowerCase() }

function toneFor(val, ctx = {}) {
  const s = norm(val)
  
  // Context-based rules (from toneForResultStatus)
  if (norm(ctx.class) === "fault") return "red"
  const ph = norm(ctx.phase)
  if (/(fail|failed|error|degraded|blocked|panic|crash)/.test(ph)) return "red"

  // Hard failures first
  if (s.includes("missing")) return "red"
  if (s.startsWith("notready") || s.includes("not ready")) return "red"
  if (s.startsWith("repair:") || s.includes("repair:")) return "red"
  if (s.startsWith("cordoned:") || s.includes("cordoned:")) return "red"
  if (s === "false") return "red"

  // More specific failure patterns BEFORE green patterns
  if (/(fail|failed|error|degraded|blocked|panic|crash|bad|invalid|terminated|unreachable|disconnected|outdated|issues|network_disconnected|red)/.test(s)) {
    return "red"
  }

  // Blue (running/in progress states)
  if (/(^running$|^in[- ]?progress$)/.test(s)) {
    return "blue"
  }

  // Green (only match positive states)
  if (/(^pass$|^passed$|^ok$|^ready$|^success$|^succeeded$|^complete$|^completed$|^finished$|^healthy$|^green$|^reachable$|^connected$|^updated$|^remediated$|^done$|^abandoned$|^true$)/.test(s)) {
    return "green"
  }

  // Gray (explicit neutral/inactive states) - Check specific patterns first
  if (/(not started|not made)/.test(s)) {
    return "gray"
  }

  // Amber (transitional/unknown)
  if (/(warn|warning|partial|amber|pending|unknown|queued|waiting|started)/.test(s)) {
    return "amber"
  }

  // Enhanced error token heuristics (from toneForResultStatus)
  if (/\b(bad|fault|mismatch|timeout|expired|denied|invalid|corrupt|broken|nack|crc|ecc|oom|unhealthy|offline|lost|throttle|retry|panic)\b/i.test(val || "")) {
    return "red"
  }

  return "gray"
}

function toneForColumn(val, columnName) {
  const s = norm(val)
  
  // For tspd column, make "running" green instead of blue
  if (columnName === "tspd" && /(^running$)/.test(s)) {
    return "green"
  }
  
  // For all other cases, use the standard toneFor logic
  return toneFor(val)
}


function extractResultsStatus(value) {
  if (value == null) return { text: "—", tone: "gray", raw: value }

  // primitives
  if (typeof value === "string") return { text: value, tone: toneFor(value), raw: value }
  if (typeof value === "boolean") {
    const text = value ? "passed" : "failed"
    return { text, tone: toneFor(text), raw: value }
  }
  if (typeof value === "number") return { text: String(value), tone: "gray", raw: value }
  if (Array.isArray(value)) return extractResultsStatus(value[0])

  // object
  const ctx = { class: value.class, phase: value.phase }
  const candidates = [
    "results_status", "result_status", "resultsStatus", "resultStatus",
    "result", "status", "verdict", "outcome", "ok", "passed", "success"
  ]
  for (const k of candidates) {
    if (k in value) {
      const v = value[k]
      if (typeof v === "boolean") {
        const text = v ? "passed" : "failed"
        return { text, tone: toneFor(text, ctx), raw: value }
      }
      if (v != null) return { text: String(v), tone: toneFor(v, ctx), raw: value }
    }
  }
  // scan one level deep
  for (const [, inner] of Object.entries(value)) {
    if (inner && typeof inner === "object") {
      const got = extractResultsStatus(inner)
      if (got.text !== "—") return { text: got.text, tone: toneFor(got.text, ctx), raw: value }
    }
  }
  try {
    const keys = Object.keys(value)
    const preview = JSON.stringify(keys.length <= 4 ? value : Object.fromEntries(keys.slice(0,4).map(k=>[k,value[k]])))
    return { text: preview, tone: toneFor(preview, ctx), raw: value }
  } catch {
    return { text: "object", tone: "gray", raw: value }
  }
}

function Badge({ children, tone = "gray", size = "sm" }) {
  const tones = {
    green: "bg-green-600 text-white border-green-700",
    red:   "bg-red-600 text-white border-red-700",
    blue:  "bg-blue-600 text-white border-blue-700",
    amber: "bg-amber-500 text-white border-amber-600",
    gray:  "bg-gray-500 text-white border-gray-600",
  }
  const sizes = {
    xs: "text-[10px] px-2 py-0.5",
    sm: "text-xs px-2.5 py-1",
    md: "text-sm px-3 py-1.5",
  }
  return (
    <span className={`inline-flex items-center rounded-md border font-semibold ${sizes[size]} ${tones[tone]}`}>
      {children}
    </span>
  )
}

function ResultsStatusBadge({ value }) {
  const { text, tone, raw } = extractResultsStatus(value)
  const title = typeof raw === "object" ? JSON.stringify(raw, null, 2) : String(value ?? "")
  return <Badge tone={tone}><span title={title}>{text}</span></Badge>
}

/* -------- helpers for Rack GV details (define once) -------- */
function fmtMs(ms) {
  if (ms == null) return "—";
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m < 60) return `${m}m ${r}s`;
  const h = Math.floor(m / 60);
  const rm = m % 60;
  return `${h}h ${rm}m`;
}

function fmtTime(t) {
  if (!t) return "—";
  try {
    const d = new Date(t);
    if (Number.isNaN(d.getTime())) return String(t);
    return d.toLocaleString();
  } catch { return String(t) }
}

function isUrl(x) { return typeof x === "string" && /^https?:\/\//i.test(x); }

function LinkMaybe({ value }) {
  if (isUrl(value)) return <a className="underline" href={value} target="_blank" rel="noreferrer">Open</a>;
  if (value && typeof value === "object" && isUrl(value.url)) {
    const label = value.label || "Open";
    return <a className="underline" href={value.url} target="_blank" rel="noreferrer">{label}</a>;
  }
  return <code className="text-xs break-all">{String(value)}</code>;
}

/* -------------------- data shaping (fallbacks) -------------------- */
function pickNodeRowsFlexible(dashboard) {
  if (!dashboard || typeof dashboard !== "object") return []
  const preferred = ["nodes", "node_rows", "nodeList", "items", "rows"]
  for (const k of preferred) {
    const v = dashboard[k]
    if (Array.isArray(v) && v.length && typeof v[0] === "object") return v
  }
  for (const v of Object.values(dashboard)) {
    if (Array.isArray(v) && v.length && typeof v[0] === "object") return v
  }
  for (const v of Object.values(dashboard)) {
    if (v && typeof v === "object" && !Array.isArray(v)) {
      const vals = Object.values(v)
      if (vals.length && typeof vals[0] === "object" && !Array.isArray(vals[0])) {
        return Object.entries(v).map(([name, obj]) => ({ name, ...obj }))
      }
    }
  }
  for (const v of Object.values(dashboard)) {
    if (v && typeof v === "object" && !Array.isArray(v)) {
      const vals = Object.values(v)
      if (vals.length && Array.isArray(vals[0])) {
        const maxLen = vals.reduce((m, a) => Math.max(m, a.length || 0), 0)
        return Object.entries(v).map(([name, arr]) => {
          const o = { name }
          for (let i = 0; i < maxLen; i++) o[`c${i}`] = arr[i] ?? null
          return o
        })
      }
    }
  }
  for (const v of Object.values(dashboard)) {
    if (Array.isArray(v) && v.length && Array.isArray(v[0])) {
      const maxLen = v.reduce((m, a) => Math.max(m, a.length || 0), 0)
      return v.map((arr, idx) => {
        const o = { name: arr[0] ?? `row-${idx}` }
        for (let i = 1; i < maxLen; i++) o[`c${i}`] = arr[i] ?? null
        return o
      })
    }
  }
  return []
}

/* -------------------- widgets -------------------- */
function Summary({ summary }) {
  if (!summary) return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
      {[...Array(6)].map((_, i) => (
        <div key={i} className="rounded-2xl shadow p-4 border border-neutral-200 dark:border-neutral-700 animate-pulse">
          <div className="h-4 bg-neutral-200 dark:bg-neutral-700 rounded mb-2"></div>
          <div className="h-8 bg-neutral-200 dark:bg-neutral-700 rounded"></div>
        </div>
      ))}
    </div>
  )
  const pct = (x) => `${((x || 0) * 100).toFixed(1)}%`
  const items = [
    { label: "Racks", value: summary.total_racks },
    { label: "Nodes", value: summary.total_nodes },
    { label: "Ready Nodes", value: `${summary.ready_nodes} (${pct(summary.ready_ratio)})` },
    { label: "Node Validations Passed", value: `${summary.node_complete} (${pct(summary.node_ratio)})` },
    { label: "Rack Validations Passed", value: `${summary.racks_complete} (${pct(summary.racks_ratio)})` },
    { label: "Crossrack Validations Passed", value: `${summary.xrk_complete} (${pct(summary.xrk_ratio)})` },
  ]
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
      {items.map((it, i) => (
        <div key={i} className="rounded-2xl shadow p-4 border border-neutral-200 dark:border-neutral-700">
          <div className="text-sm opacity-70">{it.label}</div>
          <div className="text-2xl font-semibold">{it.value}</div>
        </div>
      ))}
    </div>
  )
}

function NodeAllocation({ racks, inferencePods }) {
  if (!racks?.length) return <div className="text-sm opacity-70">No racks found.</div>
  if (!inferencePods) return <TableSkeleton cols={3} rows={10} />
  
  // Helper function to get inference-engine pods for a specific rack
  const getInferencePodsForRack = (rackName) => {
    if (!inferencePods?.pods) return []
    
    // Match pods by checking if their node names start with the rack name
    const filtered = inferencePods.pods.filter(pod => {
      if (!pod.node) return false
      // Node names typically follow pattern: rackname-gnX (e.g., c0r3-gn1)
      return pod.node.startsWith(rackName + '-')
    })
    return filtered
  }
  
  // Build complete node-to-pod mapping
  const nodeAllocation = []
  racks.forEach(rack => {
    const pods = getInferencePodsForRack(rack.rack)
    const podByNode = new Map()
    
    // Map pods to their nodes
    pods.forEach(pod => {
      if (pod.node) {
        podByNode.set(pod.node, pod.name)
      }
    })
    
    // Add all nodes for this rack
    Object.keys(rack.nodes || {}).forEach(nodeKey => {
      if (rack.nodes[nodeKey]) { // node exists and is true
        const fullNodeName = `${rack.rack}-${nodeKey}`
        const podName = podByNode.get(fullNodeName) || null
        
        // Extract model instance name if pod exists
        let modelInstance = null
        if (podName) {
          const rackFromNode = fullNodeName.split('-')[0]
          const suffixToRemove = `-${rackFromNode}-${nodeKey}`
          if (podName.endsWith(suffixToRemove)) {
            modelInstance = podName.slice(0, -suffixToRemove.length)
          }
        }
        
        nodeAllocation.push({
          node: fullNodeName,
          rack: rack.rack,
          nodeKey: nodeKey,
          pod: podName,
          modelInstance: modelInstance,
          allocated: !!podName
        })
      }
    })
  })
  
  // Sort nodes naturally
  nodeAllocation.sort((a, b) => {
    const parseNode = (node) => {
      const match = node.match(/^c(\d+)r(\d+)-gn(\d+)$/)
      if (match) {
        return [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])]
      }
      return [0, 0, 0]
    }
    
    const [aC, aR, aG] = parseNode(a.node)
    const [bC, bR, bG] = parseNode(b.node)
    
    if (aC !== bC) return aC - bC
    if (aR !== bR) return aR - bR
    return aG - bG
  })
  
  return (
    <div className="overflow-auto">
      <table className="text-sm text-center border border-neutral-200 dark:border-neutral-700 rounded-xl">
        <thead>
          <tr className="bg-black/5 dark:bg:white/5">
            <th className="px-2 py-1 text-left">Node</th>
            <th className="px-2 py-1">Status</th>
            <th className="px-2 py-1 text-left">Model Instance</th>
          </tr>
        </thead>
        <tbody>
          {nodeAllocation.map((allocation) => (
            <tr key={allocation.node} className="odd:bg-black/5 dark:odd:bg-white/5">
              <td className="px-2 py-1 text-left font-mono text-sm">{allocation.node}</td>
              <td className="px-2 py-1">
                {allocation.allocated ? (
                  <Badge tone="red">Allocated</Badge>
                ) : (
                  <Badge tone="green">Unallocated</Badge>
                )}
              </td>
              <td className="px-2 py-1 text-left">
                {allocation.modelInstance ? (
                  <span className="text-xs font-mono">{allocation.modelInstance}</span>
                ) : (
                  <span className="text-xs opacity-50">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ProductionSummary({ summary, racks, inferencePods }) {
  if (!summary || !racks || !inferencePods) return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {[...Array(4)].map((_, i) => (
        <div key={i} className="rounded-2xl shadow p-4 border border-neutral-200 dark:border-neutral-700 animate-pulse">
          <div className="h-4 bg-neutral-200 dark:bg-neutral-700 rounded mb-2"></div>
          <div className="h-8 bg-neutral-200 dark:bg-neutral-700 rounded"></div>
        </div>
      ))}
      {[...Array(2)].map((_, i) => (
        <div key={i + 4} className="md:col-span-2 rounded-2xl shadow p-4 border border-neutral-200 dark:border-neutral-700 animate-pulse">
          <div className="h-4 bg-neutral-200 dark:bg-neutral-700 rounded mb-2"></div>
          <div className="h-32 bg-neutral-200 dark:bg-neutral-700 rounded"></div>
        </div>
      ))}
    </div>
  )
  
  // Helper function to get inference-engine pods for a specific rack (same as ProductionTable)
  const getInferencePodsForRack = (rackName) => {
    if (!inferencePods?.pods) return []
    
    // Match pods by checking if their node names start with the rack name
    const filtered = inferencePods.pods.filter(pod => {
      if (!pod.node) return false
      // Node names typically follow pattern: rackname-gnX (e.g., c0r3-gn1)
      return pod.node.startsWith(rackName + '-')
    })
    return filtered
  }
  
  // Calculate unique power pods
  const powerPods = new Set()
  racks.forEach(rack => {
    if (rack.power_pod) {
      powerPods.add(rack.power_pod)
    }
  })
  
  // Calculate unique model instances and their counts, and track allocated nodes
  const modelInstances = new Set()
  const modelInstanceCounts = new Map()
  const allocatedNodes = new Set()
  
  racks.forEach(rack => {
    const pods = getInferencePodsForRack(rack.rack)
    if (pods.length) {
      pods.forEach(pod => {
        const name = pod.name || ''
        const node = pod.node || ''
        
        // Extract rack from node name (e.g., "c0r10-gn1" -> "c0r10")
        const rackFromNode = node.split('-')[0]
        
        // Remove the specific "-<rack>-<node>" suffix
        const suffixToRemove = `-${rackFromNode}-${node.split('-')[1] || ''}`
        let prefix = name
        if (name.endsWith(suffixToRemove)) {
          prefix = name.slice(0, -suffixToRemove.length)
          // Only count it as a model instance if it had the rack-node suffix
          if (prefix) {
            modelInstances.add(prefix)
            modelInstanceCounts.set(prefix, (modelInstanceCounts.get(prefix) || 0) + 1)
            allocatedNodes.add(node)
          }
        }
      })
    }
  })
  
  // Calculate unallocated nodes
  const allNodes = []
  const unallocatedNodes = []
  racks.forEach(rack => {
    Object.keys(rack.nodes || {}).forEach(nodeKey => {
      if (rack.nodes[nodeKey]) { // node exists and is true
        const fullNodeName = `${rack.rack}-${nodeKey}`
        allNodes.push(fullNodeName)
        if (!allocatedNodes.has(fullNodeName)) {
          unallocatedNodes.push(fullNodeName)
        }
      }
    })
  })
  
  // Calculate site allocation percentage
  const totalNodes = allNodes.length
  const allocatedNodesCount = totalNodes - unallocatedNodes.length
  const siteAllocationPercentage = totalNodes > 0 ? ((allocatedNodesCount / totalNodes) * 100).toFixed(1) : 0

  const items = [
    { label: "Racks", value: summary.total_racks },
    { label: "Nodes", value: summary.total_nodes },
    { label: "Power Pods", value: powerPods.size },
    { label: "Site Allocation", value: `${siteAllocationPercentage}%` },
    { 
      label: "", 
      value: unallocatedNodes.length > 0 ? (
        <div className="text-xs space-y-1 max-h-32 overflow-y-auto">
          <div className="font-semibold border-b border-neutral-200 dark:border-neutral-600 pb-1 mb-1">
            Unallocated Nodes ({unallocatedNodes.length})
          </div>
          {unallocatedNodes.sort((a, b) => {
            // Natural sort for node names like c0r1-gn1, c0r1-gn2, c0r10-gn1, etc.
            const parseNode = (node) => {
              const match = node.match(/^c(\d+)r(\d+)-gn(\d+)$/)
              if (match) {
                return [parseInt(match[1]), parseInt(match[2]), parseInt(match[3])]
              }
              return [0, 0, 0] // fallback
            }
            
            const [aC, aR, aG] = parseNode(a)
            const [bC, bR, bG] = parseNode(b)
            
            if (aC !== bC) return aC - bC
            if (aR !== bR) return aR - bR
            return aG - bG
          }).map(node => (
            <div key={node} className="font-mono text-xs">
              {node}
            </div>
          ))}
        </div>
      ) : (
        <div className="text-xs opacity-50">All nodes allocated</div>
      )
    },
    { 
      label: "", 
      value: modelInstanceCounts.size > 0 ? (
        <div className="text-xs space-y-1 max-h-32 overflow-y-auto">
          <div className="flex justify-between font-semibold border-b border-neutral-200 dark:border-neutral-600 pb-1 mb-1">
            <span>Model Instances ({modelInstances.size})</span>
            <span>Nodes</span>
          </div>
          {Array.from(modelInstanceCounts.entries())
            .sort(([,a], [,b]) => b - a)
            .map(([model, count]) => (
              <div key={model} className="flex justify-between">
                <span className="mr-2" title={model}>
                  {model}
                </span>
                <span className="font-mono">{count}</span>
              </div>
            ))}
        </div>
      ) : (
        <div className="text-xs opacity-50">No model instances</div>
      )
    },
  ]
  
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {items.slice(0, 4).map((it, i) => (
        <div key={i} className="rounded-2xl shadow p-4 border border-neutral-200 dark:border-neutral-700">
          <div className="text-sm opacity-70">{it.label}</div>
          <div className="text-2xl font-semibold">{it.value}</div>
        </div>
      ))}
      {items[4] && (
        <div className="md:col-span-2 rounded-2xl shadow p-4 border border-neutral-200 dark:border-neutral-700">
          <div className="text-sm opacity-70">{items[4].label}</div>
          <div className="text-2xl font-semibold">{items[4].value}</div>
        </div>
      )}
      {items[5] && (
        <div className="md:col-span-2 rounded-2xl shadow p-4 border border-neutral-200 dark:border-neutral-700">
          <div className="text-sm opacity-70">{items[5].label}</div>
          <div className="text-2xl font-semibold">{items[5].value}</div>
        </div>
      )}
    </div>
  )
}

function ClusterTable({ racks, podPrefixes, onSelectRack, onOpenCrossrack }) {
  if (!racks) return <TableSkeleton cols={9} rows={8} />
  if (!racks?.length) return <div className="text-sm opacity-70">No racks found.</div>
  return (
    <div className="overflow-auto">
      <table className="min-w-full text-sm text-center border border-neutral-200 dark:border-neutral-700 rounded-xl">
        <thead>
          <tr className="bg-black/5 dark:bg:white/5">
            <th className="p-2 text-left">Rack</th>
            <th className="p-2">Ready Status</th>
            {podPrefixes.map(p => <th key={p} className="p-2">{p}</th>)}
            <th className="p-2">FW Bundle Lowest</th>
            <th className="p-2">BMC Match</th>
            <th className="p-2">Node Validation</th>
            <th className="p-2">Rack Validation</th>
            <th className="p-2">Crossrack Name</th>
            <th className="p-2">Crossrack Validation</th>
          </tr>
        </thead>
        <tbody>
          {racks.map((r) => (
            <tr key={r.rack} className="odd:bg-black/5 dark:odd:bg-white/5">
              {/* Rack name → opens modal */}
              <td className="p-2 text-left">
                <button
                  type="button"
                  onClick={() => onSelectRack?.(r)}
                  className="text-blue-600 hover:underline focus:underline focus:outline-none"
                  title={`Open ${r.rack} details`}
                >
                  {r.rack}
                </button>
              </td>

              {/* Health → opens modal */}
              <td className="p-2">
                {r.health ? (
                  <button
                    type="button"
                    onClick={() => onSelectRack?.(r)}
                    className="text-blue-600 hover:underline focus:underline focus:outline-none"
                    title={`Open ${r.rack} node validation details`}
                  >
                    <Badge tone={toneFor(r.health)}>
                      {String(r.health).toLowerCase() === "healthy" ? "Ready" : r.health}
                    </Badge>
                  </button>
                ) : "—"}
              </td>

              {/* Pod health columns → opens modal */}
              {podPrefixes.map(p => {
                const val = r.pod_health?.[p]
                return (
                  <td key={p} className="p-2">
                    {val ? (
                      <button
                        type="button"
                        onClick={() => onSelectRack?.(r)}
                        className="text-blue-600 hover:underline focus:underline focus:outline-none"
                        title={`Open ${r.rack} node validation details`}
                      >
                        <Badge tone={toneForColumn(val, p)}>{val}</Badge>
                      </button>
                    ) : "—"}
                  </td>
                )
              })}

              {/* FW Version → opens modal */}
              <td className="p-2">
                {r.firmware_version ? (
                  <button
                    type="button"
                    onClick={() => onSelectRack?.(r)}
                    className="hover:underline focus:underline focus:outline-none"
                    title={`Open ${r.rack} node validation details`}
                  >
                    <code className={`text-xs ${r.firmware_version.toLowerCase() === 'error' ? 'text-red-600' : ''}`}>
                      {r.firmware_version}
                    </code>
                  </button>
                ) : (
                  <span className="text-xs opacity-50">—</span>
                )}
              </td>

              {/* BMC Match → opens modal */}
              <td className="p-2">
                {r.bmc_match ? (
                  <button
                    type="button"
                    onClick={() => onSelectRack?.(r)}
                    className="text-blue-600 hover:underline focus:underline focus:outline-none"
                    title={`Open ${r.rack} node validation details`}
                  >
                    <Badge tone={toneFor(r.bmc_match)}>{r.bmc_match}</Badge>
                  </button>
                ) : (
                  <span className="text-xs opacity-50">—</span>
                )}
              </td>

              {/* Node GV → opens modal */}
              <td className="p-2">
                <button
                  type="button"
                  onClick={() => onSelectRack?.(r)}
                  className="text-blue-600 hover:underline focus:underline focus:outline-none"
                  title={`Open ${r.rack} details`}
                >
                  {r.node_status ? <Badge tone={toneFor(r.node_status)}>{r.node_status}</Badge> : "—"}
                </button>
              </td>

              {/* Rack GV → opens modal */}
              <td className="p-2">
                <button
                  type="button"
                  onClick={() => onSelectRack?.(r, "rack")}
                  className="text-blue-600 hover:underline focus:underline focus:outline-none"
                  title={`Open ${r.rack} rack validation details`}
                >
                  {r.rack_status ? <Badge tone={toneFor(r.rack_status)}>{r.rack_status}</Badge> : "—"}
                </button>
              </td>

              {/* XRK Name */}
              <td className="p-2">
                {isCrossrackId(r.xrk_name) ? (
                  <button
                    type="button"
                    onClick={() => onOpenCrossrack?.(String(r.xrk_name).trim().toLowerCase())}
                    className="text-blue-600 hover:underline focus:underline focus:outline-none"
                    title={`Open crossrack ${r.xrk_name}`}
                  >
                    {r.xrk_name}
                  </button>
                ) : (r.xrk_name ?? "—")}
              </td>

              {/* XRK GV → opens modal */}
              <td className="p-2">
                {r.xrk_status ? (
                  <button
                    type="button"
                    onClick={() => onOpenCrossrack?.(String(r.xrk_name).trim().toLowerCase())}
                    className="text-blue-600 hover:underline focus:underline focus:outline-none"
                    title={`Open crossrack ${r.xrk_name} validation details`}
                  >
                    <Badge tone={toneFor(r.xrk_status)}>{r.xrk_status}</Badge>
                  </button>
                ) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ProductionTable({ racks, podPrefixes, onSelectRack, inferencePods }) {
  if (!racks?.length) return <div className="text-sm opacity-70">No racks found.</div>
  if (!inferencePods) return <TableSkeleton cols={7} rows={8} />
  
  // helper function to get inference-engine pods for a specific rack
  const getInferencePodsForRack = (rackName) => {
    if (!inferencePods?.pods) return []
    
    // Match pods by checking if their node names start with the rack name
    const filtered = inferencePods.pods.filter(pod => {
      if (!pod.node) return false
      // Node names typically follow pattern: rackname-gnX (e.g., c0r3-gn1)
      return pod.node.startsWith(rackName + '-')
    })
    return filtered
  }
  return (
    <div className="overflow-auto">
      <table className="min-w-full text-sm text-center border border-neutral-200 dark:border-neutral-700 rounded-xl">
        <thead>
          <tr className="bg-black/5 dark:bg:white/5">
            <th className="p-2 text-left">Rack</th>
            <th className="p-2">Ready Status</th>
            <th className="p-2">Valid</th>
            {podPrefixes.map(p => <th key={p} className="p-2">{p}</th>)}
            <th className="p-2">FW Bundle Lowest</th>
            <th className="p-2">Model Instance</th>
            <th className="p-2">Power Pod</th>
          </tr>
        </thead>
        <tbody>
          {racks.map((r) => (
            <tr key={r.rack} className="odd:bg-black/5 dark:odd:bg-white/5">
              {/* Rack name → opens modal */}
              <td className="p-2 text-left">
                <button
                  type="button"
                  onClick={() => onSelectRack?.(r)}
                  className="text-blue-600 hover:underline focus:underline focus:outline-none"
                  title={`Open ${r.rack} details`}
                >
                  {r.rack}
                </button>
              </td>

              {/* Health → opens modal */}
              <td className="p-2">
                {r.health ? (
                  <button
                    type="button"
                    onClick={() => onSelectRack?.(r)}
                    className="text-blue-600 hover:underline focus:underline focus:outline-none"
                    title={`Open ${r.rack} node validation details`}
                  >
                    <Badge tone={toneFor(r.health)}>
                      {String(r.health).toLowerCase() === "healthy" ? "Ready" : r.health}
                    </Badge>
                  </button>
                ) : "—"}
              </td>

              {/* Valid */}
              <td className="p-2">
                {r.valid ? (
                  <Badge tone={toneFor(r.valid)}>
                    {r.valid}
                  </Badge>
                ) : "—"}
              </td>

              {/* Pod health columns → opens modal */}
              {podPrefixes.map(p => {
                const val = r.pod_health?.[p]
                return (
                  <td key={p} className="p-2">
                    {val ? (
                      <button
                        type="button"
                        onClick={() => onSelectRack?.(r)}
                        className="text-blue-600 hover:underline focus:underline focus:outline-none"
                        title={`Open ${r.rack} node validation details`}
                      >
                        <Badge tone={toneForColumn(val, p)}>{val}</Badge>
                      </button>
                    ) : "—"}
                  </td>
                )
              })}

              {/* FW Version → opens modal */}
              <td className="p-2">
                {r.firmware_version ? (
                  <button
                    type="button"
                    onClick={() => onSelectRack?.(r)}
                    className="hover:underline focus:underline focus:outline-none"
                    title={`Open ${r.rack} node validation details`}
                  >
                    <code className={`text-xs ${r.firmware_version.toLowerCase() === 'error' ? 'text-red-600' : ''}`}>
                      {r.firmware_version}
                    </code>
                  </button>
                ) : (
                  <span className="text-xs opacity-50">—</span>
                )}
              </td>

              {/* Model Instance */}
              <td className="p-2 text-left">
                {(() => {
                  const pods = getInferencePodsForRack(r.rack)
                  if (!pods.length) return <span className="text-xs opacity-50">—</span>
                  
                  // Sort pods by node number (gn1, gn2, gn3, etc.)
                  const sortedPods = pods.sort((a, b) => {
                    const getNodeNum = (pod) => {
                      const node = pod.node || ''
                      const match = node.match(/gn(\d+)$/)
                      return match ? parseInt(match[1]) : 999
                    }
                    return getNodeNum(a) - getNodeNum(b)
                  })
                  
                  // Extract pod prefixes in sorted order, preserving duplicates for different nodes
                  const prefixes = []
                  const seen = new Set()
                  
                  sortedPods.forEach(pod => {
                    const name = pod.name || ''
                    const node = pod.node || ''
                    
                    // Extract rack from node name (e.g., "c0r10-gn1" -> "c0r10")
                    const rackFromNode = node.split('-')[0]
                    
                    // Remove the specific "-<rack>-<node>" suffix
                    // For "dropbox-gpt-oss-20b-yka1-prod1-1-c0r10-gn1", remove "-c0r10-gn1"
                    const suffixToRemove = `-${rackFromNode}-${node.split('-')[1] || ''}`
                    let prefix = name
                    if (name.endsWith(suffixToRemove)) {
                      prefix = name.slice(0, -suffixToRemove.length)
                    }
                    
                    if (prefix && !seen.has(prefix)) {
                      prefixes.push(prefix)
                      seen.add(prefix)
                    }
                  })
                  
                  return (
                    <div className="text-xs space-y-1">
                      {prefixes.map(prefix => (
                        <div key={prefix} className="font-mono text-xs">
                          {prefix}
                        </div>
                      ))}
                    </div>
                  )
                })()}
              </td>

              {/* Power Pod */}
              <td className="p-2">
                {r.power_pod ? (
                  <span className="text-xs font-mono">
                    {r.power_pod}
                  </span>
                ) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* -------------------- Nodes table -------------------- */
function PodsRow({ pods, nodeNames }) {
  const grouped = {}
  for (const p of pods) {
    const { name, ready, phase, node } = p
    if (!grouped[name]) grouped[name] = {}
    const nodeKey = node?.split("-").pop() || node
    grouped[name][nodeKey] = { ready, phase }
  }

  return Object.entries(grouped).map(([podName, byNode]) => (
    <tr key={podName} className="bg-black/5 dark:bg:white/5">
      <td className="p-2 text-left whitespace-nowrap sticky left-0 bg-white dark:bg-neutral-900">{podName}</td>
      {nodeNames.map(n => {
        const cell = byNode[n] || {}
        const txt = cell.phase || "—"
        return (
          <td key={n} className="p-2 text-center">
            {txt === "—" ? "—" : <Badge tone={toneForColumn(txt, podName.includes("tspd") ? "tspd" : "other")}>{txt}</Badge>}
          </td>
        )
      })}
    </tr>
  ))
}

function PodsList({ pods, nodeNames }) {
  if (!pods || !pods.length || !nodeNames || !nodeNames.length) return null
  return <PodsRow pods={pods} nodeNames={nodeNames} />
}

function NodesTable({ bundle }) {
  const dashboard = bundle?.dashboard || {}

  // Detect test-matrix: { testName: { nodeName: statusObjOrStr } }
  const testNames = Object.keys(dashboard)
  const looksLikeMatrix = testNames.length > 0 && testNames.every(t => {
    const v = dashboard[t]
    return v && typeof v === "object" && !Array.isArray(v)
  })

  if (looksLikeMatrix) {
    const nodeNames = Array.from(
      new Set(testNames.flatMap(t => Object.keys(dashboard[t] || {})))
    ).sort((a,b) => String(a).localeCompare(String(b), undefined, { numeric: true }))

    const firmwareFor = (shortName) => {
      const direct = bundle?.firmware?.[shortName]
      if (direct) return direct
      const rackPrefixed = bundle?.firmware?.[`${bundle?.rack}-${shortName}`]
      return rackPrefixed || "—"
    }

    return (
      <div className="overflow-auto">
        <table className="min-w-full text-sm text-center border border-neutral-200 dark:border-neutral-700 rounded-xl table-fixed">
          <thead>
            <tr className="bg-black/5 dark:bg:white/5">
              <th className="p-2 text-left whitespace-nowrap sticky left-0 bg-white dark:bg-neutral-900 min-w-[10rem]">
                Test
              </th>
              {nodeNames.map(n => (
                <th key={n} className="p-2 min-w-[7rem]">{n}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {testNames.map(test => (
              <tr key={test} className="odd:bg-black/5 dark:odd:bg-white/5">
                <td className="p-2 font-medium text-left whitespace-nowrap sticky left-0 bg-white dark:bg-neutral-900 min-w-[10rem]">
                  {test}
                </td>
                {nodeNames.map(node => {
                  const val = dashboard?.[test]?.[node]
                  return (
                    <td key={node} className="p-2 min-w-[5rem]">
                      {val == null || val === "" ? "—" : <ResultsStatusBadge value={val} />}
                    </td>
                  )
                })}
              </tr>
            ))}
            {/* Firmware row */}
            <tr className="bg-black/10 dark:bg:white/10 font-medium">
              <td className="p-2 text-left whitespace-nowrap sticky left-0 bg-white dark:bg-neutral-900 min-w-[10rem]">
                Firmware
              </td>
              {nodeNames.map(n => (
                <td key={n} className="p-2 min-w-[5rem]">
                  <code className="text-xs">{firmwareFor(n)}</code>
                </td>
              ))}
            </tr>
            {/* Pods rows */}
            <PodsList pods={bundle.pods} nodeNames={nodeNames} />
          </tbody>
        </table>
      </div>
    )
  }

  // Fallback: unknown shape → generic renderer
  const rows = pickNodeRowsFlexible(dashboard)
  if (!rows.length) {
    return (
      <div className="text-sm">
        <div className="mb-2 opacity-70">Couldn’t detect a node table; showing raw bundle:</div>
        <pre className="text-xs bg-black/5 dark:bg:white/5 rounded-xl p-3 overflow-auto">
          {JSON.stringify(bundle, null, 2)}
        </pre>
      </div>
    )
  }

  return (
    <div className="overflow-auto">
      <table className="min-w-full text-sm text-center border border-neutral-200 dark:border-neutral-700 rounded-xl">
        <thead>
          <tr className="bg-black/5 dark:bg:white/5">
            {Object.keys(rows[0]).map(k => (
              <th key={k} className={`p-2 ${k === "name" ? "text-left" : ""}`}>{k}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((n, i) => (
            <tr key={i} className="odd:bg-black/5 dark:odd:bg-white/5">
              {Object.entries(n).map(([k, v]) => (
                <td key={k} className={`p-2 ${k === "name" ? "text-left" : ""}`}>
                  {String(v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Tabs({ value, onChange, options }) {
  return (
    <div className="inline-flex rounded-xl border border-neutral-200 dark:border-neutral-700 overflow-hidden">
      {options.map(opt => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={[
            "px-3 py-1.5 text-sm",
            value === opt.value
              ? "bg-neutral-900 text-white dark:bg-white dark:text-neutral-900"
              : "bg-white dark:bg-neutral-800 text-neutral-700 dark:text-neutral-200"
          ].join(" ")}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

/* -------------------- Rack GV table (updated) -------------------- */
function RackGVRow({ name, obj, isFirstOfTest = false }) {

  // normalize and guard
  const result = obj?.results_status ?? obj?.result ?? obj
  const phase  = obj?.phase ?? "—"
  const extra  = (obj && typeof obj === "object" && obj.extra) ? obj.extra : {}
  const started = extra.started_at || extra.start_time || extra.started || extra.start || null
  const message = extra.message || extra.msg || null
  const reason = extra.reason || null
  const desc = extra.description || extra.detail || null
  const owner = extra.owner || extra.owners || null
  const retries = extra.retries ?? extra.attempts ?? null
  const logs = extra.logs || extra.log || null
  const artifacts = extra.artifacts || extra.outputs || null
  const validator = extra.validator || extra.name || extra.validator_name || "—"

  return (
    <>
      <tr className={isFirstOfTest ? "border-t border-gray-200 dark:border-gray-700" : ""}>
        {/* Test Name (first column) */}
        <td className="p-2 text-left whitespace-nowrap">
          <span className="font-medium">{name}</span>
        </td>

        {/* Phase */}
        <td className="p-2">
          {toneFor(phase) === "gray" ? (
            <span>{phase}</span>
          ) : (
            <Badge tone={toneFor(phase)}>{phase}</Badge>
          )}
        </td>

        <td className="p-2"><ResultsStatusBadge value={result} /></td>
        <td className="p-2 whitespace-nowrap">{fmtTime(started)}</td>

      </tr>

    </>
  )
}

function RackGVTable({ rack, rackMeta, emptyMessage, withCtx }) {
  const { data, error } = usePoll(
    async () => {
      if (!rack) return null
      if (typeof withCtx !== "function") throw new Error("withCtx prop must be a function");
      const u = new URL(withCtx("/api/rack_gv"))      
      u.searchParams.append("rack", rack)
      const res = await fetch(u)
      const json = await res.json()
      return json?.items?.[0] ?? null
    }, [rack],60000)

  if (error) return <div className="text-sm text-red-600">Rack GV error: {String(error)}</div>
  if (!data) return <TableSkeleton cols={4} rows={8} />

  const entries = Object.entries((data?.tests ?? {}))


  return (
    <div className="space-y-3">
      {/* tests table */}
      <div className="overflow-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="bg-black/5 dark:bg:white/5">
              <th className="p-2 text-left whitespace-nowrap">Test</th>
              <th className="p-2 text-left whitespace-nowrap">Phase</th>
              {/* <th className="p-2 text-left whitespace-nowrap">Test</th> */}
              <th className="p-2 text-left whitespace-nowrap">Result</th>
              <th className="p-2 text-left whitespace-nowrap">Started</th>
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 && (
              <tr>
                <td colSpan={4} className="p-3 text-sm opacity-70">
                  {emptyMessage || "No rack-level tests found."}
                </td>
              </tr>
            )}
            
            {entries.flatMap(([testName, obj]) => {
              // Prefer backend-provided runs (one per validator/phase/test)
              const runs = Array.isArray(obj?.runs) && obj.runs.length
                ? obj.runs.map(run => ({
                    ...run,
                    // Ensure started_at is properly extracted
                    started_at: run.started_at || run.start_time || run.started || run.start ||
                               run.extra?.started_at || run.extra?.start_time || run.extra?.started || run.extra?.start ||
                               obj?.extra?.started_at || obj?.extra?.start_time || obj?.extra?.started || obj?.extra?.start || null
                  }))
                : [
                    // Fallback: synthesize a single run from the summary fields
                    {
                      validator: obj?.extra?.validator || "—",
                      phase: obj?.phase ?? "—",
                      result: obj?.results_status ?? obj?.result ?? obj,
                      started_at: obj?.extra?.started_at || obj?.extra?.start_time || obj?.extra?.started || obj?.extra?.start || 
                                 obj?.started_at || obj?.start_time || obj?.started || obj?.start || null,
                      extra: obj?.extra || {}
                    }
                  ];
                
              return runs.map((run, i) => (
                <RackGVRow
                  key={`${testName}-${i}`}
                  // We pass "name" as the Test label, but also attach the per-run data into obj
                  name={testName}
                  isFirstOfTest={i === 0}
                  obj={{
                    results_status: run.result ?? obj?.results_status ?? obj,
                    phase: run.phase,
                    extra: { 
                      validator: run.validator, 
                      ...run.extra, 
                      started_at: run.started_at 
                    }
                  }}
                />
              ));
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ----------------- Crossrack GV table ---------------------- */
function RackStatusChips({ rackMeta }) {
  if (!rackMeta) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs opacity-70">Health:</span>
      <Badge tone={toneFor(rackMeta?.health)}>{rackMeta?.health ?? "—"}</Badge>
      <span className="text-xs opacity-70 ml-2">Node GV:</span>
      <Badge tone={toneFor(rackMeta?.node_status)}>{rackMeta?.node_status ?? "—"}</Badge>
      <span className="text-xs opacity-70 ml-2">Rack GV:</span>
      <Badge tone={toneFor(rackMeta?.rack_status)}>{rackMeta?.rack_status ?? "—"}</Badge>
      <span className="text-xs opacity-70 ml-2">XRK GV:</span>
      <Badge tone={toneFor(rackMeta?.xrk_status)}>{rackMeta?.xrk_status ?? "—"}</Badge>
    </div>
  );
}
  
/* -------------------- data sections -------------------- */
function Nodes({ racks, withCtx }) {
  const { data, error } = usePoll(
    async () => {
      if (!racks.length) return { bundles: [] }
      const u = new URL(withCtx("/api/nodes"))
      racks.forEach(r => u.searchParams.append("racks", r))
      const res = await fetch(u)
      const json = await res.json()
      console.log("NODES_RESPONSE", json)
      return { bundles: json }
    }, [racks], 60000)

  if (error) return <div className="text-sm text-red-600">Nodes error: {String(error)}</div>
  if (!data) return <TableSkeleton cols={6} rows={8} />
  if (!data.bundles.length) return <div className="text-sm opacity-70">No racks selected.</div>

  const first = data.bundles[0] || {}
  const dash = first.dashboard || {}
  const dashKeys = Object.keys(dash)

  if (!data?.bundles) return <TableSkeleton cols={6} rows={8} />

  return (
    <div className="space-y-6">
      <div className="text-xs opacity-60">
        nodes: bundles={data.bundles.length} | dashboard.keys={dashKeys.join(", ")}
      </div>
      {data.bundles.map(b => (
        <div key={b.rack} className="rounded-2xl shadow p-4 border border-neutral-200 dark:border-neutral-700">
          <div className="text-lg font-semibold mb-2">{b.rack}</div>
          <NodesTable bundle={b} />
          {/* Note: PodsList is rendered inside NodesTable in matrix mode */}
        </div>
      ))}
    </div>
  )
}

function extractTicketId(url) {
  if (!url || url === 'N/A') return null;
  const match = url.match(/\/([A-Z]+-\d+)$/);
  return match ? match[1] : null;
}

function FaultsSummary({ data, filter, onFilterChange }) {
  if (!data || !data.rows) return null;
  
  // Count faults by fault type
  const faultTypeCounts = data.rows.reduce((acc, row) => {
    const faultType = row.faultType || 'Unknown';
    acc[faultType] = (acc[faultType] || 0) + 1;
    return acc;
  }, {});

  // Calculate ticket statistics
  const totalTickets = data.rows.filter(row => row.ticketUrl && row.ticketUrl !== 'N/A').length;
  const toDoTickets = data.rows.filter(row => 
    row.ticketUrl && row.ticketUrl !== 'N/A' && 
    row.jiraStatus && row.jiraStatus !== 'N/A' && 
    ['to do'].includes(row.jiraStatus.toLowerCase())
  ).length;
  const inProgressTickets = data.rows.filter(row => 
    row.ticketUrl && row.ticketUrl !== 'N/A' && 
    row.jiraStatus && row.jiraStatus !== 'N/A' && 
    ['in progress'].includes(row.jiraStatus.toLowerCase())
  ).length;
  const doneTickets = data.rows.filter(row => 
    row.ticketUrl && row.ticketUrl !== 'N/A' && 
    row.jiraStatus && row.jiraStatus !== 'N/A' && 
    ['done', 'closed', 'resolved', 'complete', 'completed'].includes(row.jiraStatus.toLowerCase())
  ).length;
  const abandonedTickets = data.rows.filter(row => 
    row.ticketUrl && row.ticketUrl !== 'N/A' && 
    row.jiraStatus && row.jiraStatus !== 'N/A' && 
    ['abandoned'].includes(row.jiraStatus.toLowerCase())
  ).length;
  const onHoldTickets = data.rows.filter(row => 
    row.ticketUrl && row.ticketUrl !== 'N/A' && 
    row.jiraStatus && row.jiraStatus !== 'N/A' && 
    ['on hold', 'hold', 'blocked', 'waiting'].includes(row.jiraStatus.toLowerCase())
  ).length;

  // Sort by count (descending)
  const sortedEntries = Object.entries(faultTypeCounts).sort(([,a], [,b]) => b - a);

  return (
    <div className="grid grid-cols-2 gap-3">
      {/* Total Faults and Tickets */}
      <div className="rounded-2xl shadow p-4 border border-neutral-200 dark:border-neutral-700">
        <div className="space-y-3">
          <button
            className={`w-full text-left p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 ${filter === 'hasTickets' ? 'bg-blue-100 dark:bg-blue-900' : ''}`}
            onClick={() => onFilterChange(filter === 'hasTickets' ? null : 'hasTickets')}
          >
            <div className="text-sm opacity-70">Total Tickets</div>
            <div className="text-xl font-semibold">{totalTickets}</div>
          </button>
          <button
            className={`w-full text-left p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 ${filter === 'toDo' ? 'bg-blue-100 dark:bg-blue-900' : ''}`}
            onClick={() => onFilterChange(filter === 'toDo' ? null : 'toDo')}
          >
            <div className="text-sm opacity-70">To Do Tickets</div>
            <div className="text-xl font-semibold">{toDoTickets}</div>
          </button>
          <button
            className={`w-full text-left p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 ${filter === 'inProgress' ? 'bg-blue-100 dark:bg-blue-900' : ''}`}
            onClick={() => onFilterChange(filter === 'inProgress' ? null : 'inProgress')}
          >
            <div className="text-sm opacity-70">In Progress Tickets</div>
            <div className="text-xl font-semibold">{inProgressTickets}</div>
          </button>
          <button
            className={`w-full text-left p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 ${filter === 'abandoned' ? 'bg-blue-100 dark:bg-blue-900' : ''}`}
            onClick={() => onFilterChange(filter === 'abandoned' ? null : 'abandoned')}
          >
            <div className="text-sm opacity-70">Abandoned Tickets</div>
            <div className="text-xl font-semibold">{abandonedTickets}</div>
          </button>
          <button
            className={`w-full text-left p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 ${filter === 'onHold' ? 'bg-blue-100 dark:bg-blue-900' : ''}`}
            onClick={() => onFilterChange(filter === 'onHold' ? null : 'onHold')}
          >
            <div className="text-sm opacity-70">On Hold Tickets</div>
            <div className="text-xl font-semibold">{onHoldTickets}</div>
          </button>
          <button
            className={`w-full text-left p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 ${filter === 'done' ? 'bg-blue-100 dark:bg-blue-900' : ''}`}
            onClick={() => onFilterChange(filter === 'done' ? null : 'done')}
          >
            <div className="text-sm opacity-70">Done Tickets</div>
            <div className="text-xl font-semibold">{doneTickets}</div>
          </button>
        </div>
      </div>

      {/* Fault Types Breakdown */}
      <div className="rounded-2xl shadow p-4 border border-neutral-200 dark:border-neutral-700">
        <div className="text-sm opacity-70">Fault Types</div>
        <div className="mt-2 space-y-1">
          {sortedEntries.map(([faultType, count]) => (
            <button
              key={faultType}
              className={`w-full flex justify-between items-center text-sm p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 ${filter === `faultType:${faultType}` ? 'bg-blue-100 dark:bg-blue-900' : ''}`}
              onClick={() => onFilterChange(filter === `faultType:${faultType}` ? null : `faultType:${faultType}`)}
            >
              <span>{faultType}</span>
              <span className="font-semibold">{count}</span>
            </button>
          ))}
          <div className="border-t pt-2 mt-2 flex justify-between items-center text-sm font-semibold">
            <span>Total Faults</span>
            <span>{data.count || 0}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function Faults({ selectedRacks, withCtx }) {
  const [filter, setFilter] = useState(null);
  
  const { data, error } = usePoll(
    async () => {
      const u = new URL(withCtx("/api/faults"))
      selectedRacks.forEach(r => u.searchParams.append("racks", r))
      const res = await fetch(u)
      return await res.json()
    }, [selectedRacks, withCtx], 60000)

  if (error) return <div className="text-sm text-red-600">Faults error: {String(error)}</div>
  if (!data) return <TableSkeleton cols={5} rows={8} />

  // Filter the data based on current filter
  const filteredRows = data.rows.filter(row => {
    if (!filter) return true;
    
    if (filter === 'hasTickets') return row.ticketUrl && row.ticketUrl !== 'N/A';
    if (filter === 'toDo') return row.ticketUrl && row.ticketUrl !== 'N/A' && 
      row.jiraStatus && row.jiraStatus !== 'N/A' && 
      ['to do'].includes(row.jiraStatus.toLowerCase());
    if (filter === 'inProgress') return row.ticketUrl && row.ticketUrl !== 'N/A' && 
      row.jiraStatus && row.jiraStatus !== 'N/A' && 
      ['in progress'].includes(row.jiraStatus.toLowerCase());
    if (filter === 'done') return row.ticketUrl && row.ticketUrl !== 'N/A' && 
      row.jiraStatus && row.jiraStatus !== 'N/A' && 
      ['done', 'closed', 'resolved', 'complete', 'completed'].includes(row.jiraStatus.toLowerCase());
    if (filter === 'abandoned') return row.ticketUrl && row.ticketUrl !== 'N/A' && 
      row.jiraStatus && row.jiraStatus !== 'N/A' && 
      ['abandoned'].includes(row.jiraStatus.toLowerCase());
    if (filter === 'onHold') return row.ticketUrl && row.ticketUrl !== 'N/A' && 
      row.jiraStatus && row.jiraStatus !== 'N/A' && 
      ['on hold', 'hold', 'blocked', 'waiting'].includes(row.jiraStatus.toLowerCase());
    if (filter.startsWith('faultType:')) {
      const faultType = filter.replace('faultType:', '');
      return row.faultType === faultType;
    }
    
    return true;
  });

  return (
    <div className="space-y-6">
      <FaultsSummary data={data} filter={filter} onFilterChange={setFilter} />
      {filter && (
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600 dark:text-gray-400">
            Filtered: {filteredRows.length} of {data.rows.length} faults
          </span>
          <button
            onClick={() => setFilter(null)}
            className="text-sm text-blue-600 hover:underline"
          >
            Clear filter
          </button>
        </div>
      )}
      <div className="overflow-auto">
        <table className="min-w-full text-sm text-center border border-neutral-200 dark:border-neutral-700 rounded-xl">
          <thead>
            <tr className="bg-black/5 dark:bg:white/5">
              <th className="text-left p-2">Component</th>
              <th className="p-2">Fault Type</th>
              <th className="p-2">Phase</th>
              <th className="p-2">Ticket Status</th>
              <th className="p-2">Jira Ticket</th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((r,i)=> (
              <tr key={i} className="odd:bg-black/5 dark:odd:bg-white/5">
                <td className="p-2 text-left">{r.component}</td>
                <td className="p-2">{r.faultType}</td>
                <td className="p-2"><Badge tone={toneFor(r.phase)}>{r.phase}</Badge></td>
                <td className="p-2">
                  {r.jiraStatus && r.jiraStatus !== 'N/A' ? <Badge tone={toneFor(r.jiraStatus)}>{r.jiraStatus}</Badge> : "—"}
                </td>
                <td className="p-2">
                  {r.ticketUrl && r.ticketUrl !== 'N/A' ? <a className="underline text-sm" href={r.ticketUrl} target="_blank" rel="noreferrer">{extractTicketId(r.ticketUrl) || "Open"}</a> : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* -------------------- Pre-Validation Page -------------------- */
function PreValidation({ withCtx, isRunningTests, setIsRunningTests, currentContext, setCurrentContext, detailedResults, setDetailedResults, selectedContext, cancellationToken, setCancellationToken, abortController, setAbortController, globalCancelFlag, setGlobalCancelFlag }) {
  const [refresh, setRefresh] = useState(30000);
  const [modalRack, setModalRack] = useState(null);

  const [tooltipModal, setTooltipModal] = useState(null);
  
  // Callback to update cached results when detailed tests complete
  const updateDetailedResult = (rackName, rackData) => {
    setDetailedResults(prev => new Map(prev.set(rackName, rackData)));
  };
  
  // Fetch pre-validation data from API with context
  const { data: preValidationData, error } = usePoll(
    async () => {
      const response = await fetch(withCtx("/api/pre-validation"));
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      return await response.json();
    },
    [withCtx],
    refresh
  );

  if (error) return <div className="text-sm text-red-600">Pre-validation error: {String(error)}</div>;
  if (!preValidationData) return <div className="text-sm opacity-70">Loading pre-validation data…</div>;

  return (
    <div className="space-y-6">
      {/* Pre-Validation Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {(() => {
          const totalRacks = preValidationData.racks?.length || 0;
          const testedRacks = detailedResults.size;
          const readyRacks = Array.from(detailedResults.values()).filter(r => r.overall_status === "ready").length;
          
          // Count BMC fully reachable (all nodes in rack have reachable BMCs)
          const bmcFullyReachable = Array.from(detailedResults.values()).filter(rack => {
            const nodes = rack.nodes || [];
            if (nodes.length === 0) return false;
            const bmcStatuses = nodes.map(node => node.bmc?.status).filter(Boolean);
            return bmcStatuses.length > 0 && bmcStatuses.every(status => status === "reachable");
          }).length;

          return (
            <>
              <div className="rounded-2xl shadow p-4 border border-neutral-200 dark:border-neutral-700 relative">
                <div className="flex items-center gap-2">
                  <div className="text-sm opacity-70">Total Racks</div>
                  <button
                    onClick={() => setTooltipModal({ title: "Total Racks", content: "Total number of racks available for pre-validation testing" })}
                    className="text-blue-500 hover:text-blue-600 text-sm"
                    title="Click for info"
                  >
                    ℹ️
                  </button>
                </div>
                <div className="text-2xl font-semibold">
                  {totalRacks}
                </div>
              </div>
              <div className="rounded-2xl shadow p-4 border border-neutral-200 dark:border-neutral-700 relative">
                <div className="flex items-center gap-2">
                  <div className="text-sm opacity-70">Tested</div>
                  <button
                    onClick={() => setTooltipModal({ title: "Tested", content: "Number of racks that have been tested vs total racks. Click 'Test All' or individual racks to run tests." })}
                    className="text-blue-500 hover:text-blue-600 text-sm"
                    title="Click for info"
                  >
                    ℹ️
                  </button>
                </div>
                <div className="text-2xl font-semibold">
                  {testedRacks} / {totalRacks}
                </div>
              </div>

            </>
          );
        })()}
      </div>

      {/* Pre-Validation Table */}
      <div className="space-y-3">
        {/* Contact Information */}
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-blue-600 dark:text-blue-400">ℹ️</span>
            <span className="font-semibold text-blue-800 dark:text-blue-200">Contact:</span>
            <span className="text-blue-700 dark:text-blue-300">Contact dc-eng for issues</span>
          </div>
        </div>
        
        <div className="flex items-center justify-between">
          <div className="text-lg font-semibold">Pre-Validation Status</div>
          <div className="flex items-center gap-4">
            <button
              type="button"
              onClick={async () => {
                console.log('Running concurrent test all...');
                
                // Get all racks that haven't been tested yet
                const untestedRacks = (preValidationData.racks || []).filter(rack => 
                  !detailedResults.has(rack.rack)
                );
                
                if (untestedRacks.length === 0) {
                  alert('All racks have already been tested!');
                  return;
                }
                
                console.log(`Testing ${untestedRacks.length} racks with max 15 concurrent:`, untestedRacks.map(r => r.rack));
                
                // Process racks in batches of 15
                const batchSize = 15;
                for (let i = 0; i < untestedRacks.length; i += batchSize) {
                  const batch = untestedRacks.slice(i, i + batchSize);
                  console.log(`Processing batch ${Math.floor(i/batchSize) + 1}:`, batch.map(r => r.rack));
                  
                  // Start all racks in this batch concurrently
                  const batchPromises = batch.map(async (rack) => {
                    console.log(`Starting test for ${rack.rack}`);
                    
                    // Show loading state
                    const tempResult = { 
                      rack: rack.rack, 
                      overall_status: "testing...", 
                      network: { dns: "testing..." },
                      bmc: { status: "testing..." },
                      nodes: [{
                        bmc: { auth_success: "testing", version: "testing..." },
                        bios: { version: "testing..." },
                        compute_status: "testing..."
                      }]
                    };
                    updateDetailedResult(rack.rack, tempResult);
                    
                    try {
                      const response = await fetch(withCtx(`/api/pre-validation/${rack.rack}`));
                      const responseData = await response.json();
                      console.log('Test completed for', rack.rack, ':', responseData);
                      
                      // Extract the individual rack data from the racks array
                      const rackData = responseData.racks?.find(r => r.rack === rack.rack);
                      if (rackData) {
                        updateDetailedResult(rack.rack, rackData);
                      } else {
                        console.error('Rack data not found in response for', rack.rack);
                        const errorResult = { 
                          rack: rack.rack, 
                          overall_status: "no data", 
                          network: { dns: "no data" },
                          bmc: { status: "no data" },
                          nodes: []
                        };
                        updateDetailedResult(rack.rack, errorResult);
                      }
                    } catch (error) {
                      console.error('Failed to run test for', rack.rack, ':', error);
                      const errorResult = { 
                        rack: rack.rack, 
                        overall_status: "test failed",
                        network: { dns: "test failed" },
                        nodes: []
                      };
                      updateDetailedResult(rack.rack, errorResult);
                    }
                  });
                  
                  // Wait for this batch to complete before starting the next
                  await Promise.all(batchPromises);
                  console.log(`Batch ${Math.floor(i/batchSize) + 1} completed`);
                }
                
                console.log('All tests completed!');
              }}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors"
              title="Run pre-validation tests on all untested racks with max 15 concurrent"
            >
              🚀 Test All (15 Concurrent)
            </button>
            <div className="text-sm opacity-70">💡 Click rack names to run individual tests</div>
          </div>
        </div>
        <div className="overflow-auto">
          <table className="min-w-full text-sm text-center border border-neutral-200 dark:border-neutral-700 rounded-xl">
            <thead>
              <tr className="bg-black/5 dark:bg:white/5">
                <th className="p-2 text-left">Rack</th>
                <th className="p-2">BMC</th>
                <th className="p-2">BMC Auth</th>
                <th className="p-2">BMC Version</th>
                <th className="p-2">BIOS Version</th>
                <th className="p-2">Compute</th>
              </tr>
            </thead>
            <tbody>
              {(preValidationData.racks || []).map((rack) => {
                // Use cached detailed result if available, otherwise use basic rack data
                const detailedRack = detailedResults.get(rack.rack);
                const displayRack = detailedRack || rack;
                const isTested = !!detailedRack;
                const isTesting = isTested && displayRack.overall_status === "testing...";
                
                return (
                  <tr 
                    key={rack.rack} 
                    className="odd:bg-black/5 dark:odd:bg-white/5 cursor-pointer hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors"
                    onClick={async () => {
                      if (!isTested) {
                        // Run tests for untested racks
                        console.log('Running background tests for rack:', rack.rack);
                        
                        // Show loading state
                        const tempResult = { 
                          rack: rack.rack, 
                          overall_status: "testing...", 
                          network: { dns: "testing..." },
                          bmc: { status: "testing..." },
                          nodes: [{
                            bmc: { auth_success: "testing", version: "testing..." },
                            bios: { version: "testing..." },
                            compute_status: "testing..."
                          }]
                        };
                        updateDetailedResult(rack.rack, tempResult);
                        
                        try {
                          const response = await fetch(withCtx(`/api/pre-validation/${rack.rack}`));
                          const responseData = await response.json();
                          console.log('Background test results for', rack.rack, ':', responseData);
                          
                          // Extract the individual rack data from the racks array
                          const rackData = responseData.racks?.find(r => r.rack === rack.rack);
                          if (rackData) {
                            updateDetailedResult(rack.rack, rackData);
                          } else {
                            console.error('Rack data not found in response for', rack.rack);
                            const errorResult = { 
                              rack: rack.rack, 
                              overall_status: "no data", 
                              network: { dns: "no data" },
                              bmc: { status: "no data" },
                              nodes: []
                            };
                            updateDetailedResult(rack.rack, errorResult);
                          }
                        } catch (error) {
                          console.error('Failed to run background tests for', rack.rack, ':', error);
                          const errorResult = { 
                            rack: rack.rack, 
                            overall_status: "test failed",
                            network: { dns: "test failed" },
                            nodes: []
                          };
                          updateDetailedResult(rack.rack, errorResult);
                        }
                      } else {
                        // Open modal for tested racks
                        console.log('Opening modal for tested rack:', rack.rack);
                        setModalRack(rack);
                      }
                    }}
                    title={!isTested ? `Click to run pre-validation tests for ${rack.rack}` : `Click to view detailed results for ${rack.rack}`}
                  >
                    <td className="p-2 text-left">
                      <span className="font-mono text-blue-600">
                        {rack.rack}
                      </span>
                    </td>
                    {/* BMC Column */}
                    <td className="p-2">
                      {isTesting ? (
                        <Badge tone="amber">testing...</Badge>
                      ) : isTested ? (
                        // Aggregate BMC status from all nodes
                        (() => {
                          const nodes = displayRack.nodes || [];
                          if (nodes.length === 0) return <Badge tone="gray">—</Badge>;
                          
                          const bmcStatuses = nodes.map(node => node.bmc?.status).filter(Boolean);
                          
                          const allReachable = bmcStatuses.every(status => status === "reachable");
                          const anyReachable = bmcStatuses.some(status => status === "reachable");
                          
                          let status = "—";
                          if (allReachable && bmcStatuses.length > 0) status = "reachable";
                          else if (anyReachable) status = "partial";
                          else if (bmcStatuses.length > 0) status = "unreachable";
                          
                          return (
                            <Badge tone={toneFor(status)}>
                              {status}
                            </Badge>
                          );
                        })()
                      ) : (
                        <Badge tone="amber">
                          click to test
                        </Badge>
                      )}
                    </td>
                    
                    {/* BMC Auth Column */}
                    <td className="p-2">
                      {isTesting ? (
                        <Badge tone="amber">testing...</Badge>
                      ) : isTested ? (
                        // Aggregate BMC auth status from all nodes
                        (() => {
                          const nodes = displayRack.nodes || [];
                          if (nodes.length === 0) return <Badge tone="gray">—</Badge>;
                          
                          const authResults = nodes.map(node => node.bmc?.auth_success).filter(auth => auth !== undefined);
                          
                          const allSuccess = authResults.every(auth => auth === true);
                          const anySuccess = authResults.some(auth => auth === true);
                          
                          let status = "—";
                          if (allSuccess && authResults.length > 0) status = "success";
                          else if (anySuccess) status = "partial";
                          else if (authResults.length > 0) status = "failed";
                          
                          return (
                            <Badge tone={toneFor(status)}>
                              {status}
                            </Badge>
                          );
                        })()
                      ) : (
                        <Badge tone="gray">not tested</Badge>
                      )}
                    </td>
                    
                    {/* BMC Version Column */}
                    <td className="p-2 text-xs font-mono">
                      {isTesting ? (
                        <Badge tone="amber">testing...</Badge>
                      ) : isTested ? (
                        (() => {
                          const nodes = displayRack.nodes || [];
                          if (nodes.length === 0) return "—";
                          
                          const versions = nodes
                            .map(node => node.bmc?.version)
                            .filter(Boolean)
                            .filter(v => v !== "unknown");
                            
                          if (versions.length === 0) return "—";
                          
                          // Show most common version or first valid one
                          const uniqueVersions = [...new Set(versions)];
                          return uniqueVersions.length === 1 ? uniqueVersions[0] : `${uniqueVersions.length} versions`;
                        })()
                      ) : (
                        "—"
                      )}
                    </td>
                    
                    {/* BIOS Version Column */}
                    <td className="p-2 text-xs font-mono">
                      {isTesting ? (
                        <Badge tone="amber">testing...</Badge>
                      ) : isTested ? (
                        (() => {
                          const nodes = displayRack.nodes || [];
                          if (nodes.length === 0) return "—";
                          
                          const versions = nodes
                            .map(node => node.bios?.version)
                            .filter(Boolean)
                            .filter(v => v !== "unknown");
                            
                          if (versions.length === 0) return "—";
                          
                          // Show most common version or first valid one
                          const uniqueVersions = [...new Set(versions)];
                          return uniqueVersions.length === 1 ? uniqueVersions[0] : `${uniqueVersions.length} versions`;
                        })()
                      ) : (
                        "—"
                      )}
                    </td>
                    
                    {/* Compute Column */}
                    <td className="p-2">
                      {isTesting ? (
                        <Badge tone="amber">testing...</Badge>
                      ) : isTested ? (
                        // Aggregate compute status from all nodes
                        (() => {
                          const nodes = displayRack.nodes || [];
                          if (nodes.length === 0) return <Badge tone="gray">—</Badge>;
                          
                          const computeStatuses = nodes.map(node => node.compute_status).filter(Boolean);
                          
                          const allReachable = computeStatuses.every(status => status === "reachable");
                          const anyReachable = computeStatuses.some(status => status === "reachable");
                          
                          let status = "—";
                          if (allReachable && computeStatuses.length > 0) status = "reachable";
                          else if (anyReachable) status = "partial";
                          else if (computeStatuses.length > 0) status = "unreachable";
                          
                          return (
                            <Badge tone={toneFor(status)}>
                              {status}
                            </Badge>
                          );
                        })()
                      ) : (
                        <Badge tone="gray">not tested</Badge>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>



      {/* Pre-Validation Modal */}
      {modalRack && (
        <PreValidationModal
          rack={modalRack}
          onClose={() => setModalRack(null)}
          onDetailedDataLoaded={updateDetailedResult}
          cachedData={detailedResults.get(modalRack.rack)}
          withCtx={withCtx}
        />
      )}

      {/* Tooltip Modal */}
      {tooltipModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setTooltipModal(null)}>
          <div className="bg-white dark:bg-neutral-800 rounded-lg p-6 max-w-md mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">{tooltipModal.title}</h3>
              <button
                onClick={() => setTooltipModal(null)}
                className="text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300 text-xl"
              >
                ×
              </button>
            </div>
            <p className="text-neutral-700 dark:text-neutral-300">{tooltipModal.content}</p>
          </div>
        </div>
      )}
    </div>
  );
}

/* -------------------- Pre-Validation Modal -------------------- */
function PreValidationModal({ rack, onClose, onDetailedDataLoaded, cachedData, withCtx }) {
  if (!rack) return null;

  const [detailedData, setDetailedData] = useState(cachedData || null);
  const [loading, setLoading] = useState(!cachedData); // Don't load if we have cached data
  const [error, setError] = useState(null);

  // Function to fetch detailed data
  const fetchDetailedData = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(withCtx(`/api/pre-validation/${rack.rack}`));
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      const data = await response.json();
      if (data.error) {
        throw new Error(data.error);
      }
      // Get the first rack from the response (should only be one)
      const rackData = data.racks?.[0];
      if (rackData) {
        setDetailedData(rackData);
        // Update cached results in parent component
        if (onDetailedDataLoaded) {
          onDetailedDataLoaded(rackData.rack, rackData);
        }
      } else {
        throw new Error("No rack data returned");
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  // Function to retry/refresh tests
  const retryTests = () => {
    fetchDetailedData();
  };

  // Fetch detailed data when modal opens (only if no cached data)
  useEffect(() => {
    if (cachedData) {
      // Use cached data, skip API call
      return;
    }

    fetchDetailedData();
  }, [rack.rack]);

  const nodes = (detailedData?.nodes || []).sort((a, b) => a.node - b.node); // Sort nodes numerically by node number
  const displayRack = detailedData || rack; // Use detailed data if available, fallback to basic rack info
  
  return (
    <div className="fixed inset-0 z-50 flex items-start md:items-center justify-center p-4 bg-black/60" onClick={onClose}>
      <div
        className="w-full max-w-7xl max-h-[90vh] overflow-hidden rounded-2xl bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100 shadow-2xl border border-neutral-200 dark:border-neutral-700"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between gap-3 p-4 border-b border-neutral-200 dark:border-neutral-700 sticky top-0 bg-white dark:bg-neutral-900 z-10">
          <div className="space-y-2">
            <h2 className="text-xl font-semibold">
              Pre-Validation Details: <span className="font-mono">{rack.rack}</span>
            </h2>
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {loading ? (
                <span className="text-blue-600">⏳ Running network tests...</span>
              ) : error ? (
                <span className="text-red-600">❌ Error: {error}</span>
              ) : (
                <>
                  <span className="opacity-70">Overall Status:</span>
                  <Badge tone={toneFor(displayRack.overall_status || "unknown")}>
                    {displayRack.overall_status === "ready" ? "Ready" : displayRack.overall_status === "issues" ? "Issues Found" : displayRack.overall_status}
                  </Badge>
                  
                  <span className="opacity-70 ml-2">BMC:</span>
                  <Badge tone={toneFor(displayRack.bmc?.status || "unknown")}>
                    {displayRack.bmc?.status || "—"}
                  </Badge>
                  
                  <span className="opacity-70 ml-2">Network:</span>
                  <Badge tone={toneFor(displayRack.network?.status || "unknown")}>
                    {displayRack.network?.status || "—"}
                  </Badge>
                  
                  <span className="opacity-70 ml-2">Firmware:</span>
                  <Badge tone={toneFor(displayRack.firmware?.status || "unknown")}>
                    {displayRack.firmware?.status || "—"}
                  </Badge>
                </>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={retryTests}
              disabled={loading}
              className="rounded-md border px-2.5 py-1 text-sm hover:bg-blue-50 dark:hover:bg-blue-900/20 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Re-run pre-validation tests"
            >
              🔄 Retry
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border px-2.5 py-1 text-sm hover:bg-black/5 dark:hover:bg-white/10"
              aria-label="Close"
            >
              ✖
            </button>
          </div>
        </div>

        {/* Scrollable content */}
        <div className="p-4 overflow-y-auto max-h-[calc(90vh-72px)]">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-4"></div>
              <div className="text-lg font-medium mb-2">Running Pre-Validation Tests</div>
              <div className="text-sm opacity-70 text-center">
                Testing BMC connectivity, network reachability, and authentication for {rack.rack}...
                <br />
                This may take 30-60 seconds.
              </div>
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="text-red-600 text-4xl mb-4">❌</div>
              <div className="text-lg font-medium mb-2">Pre-Validation Failed</div>
              <div className="text-sm opacity-70 text-center">
                {error}
                <br />
                <button 
                  className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors"
                  onClick={() => {
                    setError(null);
                    setLoading(true);
                    // Re-trigger the useEffect by updating a dependency or directly call the fetch
                    window.location.reload();
                  }}
                >
                  Retry
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Node-by-node table - nodes across top, tests as rows */}
              <div className="overflow-auto">
                <table className="min-w-full text-sm border border-neutral-200 dark:border-neutral-700 rounded-xl">
                  <thead>
                    <tr className="bg-black/5 dark:bg:white/5">
                      <th className="p-3 text-left sticky left-0 bg-black/5 dark:bg:white/5">Test</th>
                      {nodes.map((node) => (
                        <th key={`${node.rack}-gn${node.node}`} className="p-3 text-center font-mono">
                          gn{node.node}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {/* BMC Row - combines status and IP */}
                    <tr className="odd:bg-black/5 dark:odd:bg-white/5">
                      <td className="p-3 font-semibold text-left sticky left-0 bg-white dark:bg-neutral-900">
                        BMC
                      </td>
                      {nodes.map((node) => (
                        <td key={`${node.rack}-gn${node.node}-bmc`} className="p-3 text-center">
                          <div className="space-y-1">
                            <Badge tone={toneFor(node.bmc?.status || "unknown")}>
                              {node.bmc?.status || "—"}
                            </Badge>
                            <div className="text-xs font-mono opacity-70">
                              {node.bmc?.ip || "—"}
                            </div>
                          </div>
                        </td>
                      ))}
                    </tr>

                    {/* BMC Auth Row */}
                    <tr className="odd:bg-black/5 dark:odd:bg-white/5">
                      <td className="p-3 font-semibold text-left sticky left-0 bg-white dark:bg-neutral-900">
                        BMC Auth
                      </td>
                      {nodes.map((node) => (
                        <td key={`${node.rack}-gn${node.node}-auth`} className="p-3 text-center">
                          <Badge tone={node.bmc?.auth_success ? "green" : "red"}>
                            {node.bmc?.auth_success ? "Success" : "Failed"}
                          </Badge>
                        </td>
                      ))}
                    </tr>

                    {/* BMC Version Row */}
                    <tr className="odd:bg-black/5 dark:odd:bg-white/5">
                      <td className="p-3 font-semibold text-left sticky left-0 bg-white dark:bg-neutral-900">
                        BMC Version
                      </td>
                      {nodes.map((node) => (
                        <td key={`${node.rack}-gn${node.node}-bmc-version`} className="p-3 text-center text-xs font-mono">
                          {node.bmc?.version || "—"}
                        </td>
                      ))}
                    </tr>

                    {/* BIOS Version Row */}
                    <tr className="odd:bg-black/5 dark:odd:bg-white/5">
                      <td className="p-3 font-semibold text-left sticky left-0 bg-white dark:bg-neutral-900">
                        BIOS Version
                      </td>
                      {nodes.map((node) => (
                        <td key={`${node.rack}-gn${node.node}-bios-version`} className="p-3 text-center text-xs font-mono">
                          {node.bios?.version || "—"}
                        </td>
                      ))}
                    </tr>

                    {/* Compute Row - combines status and IP */}
                    <tr className="odd:bg-black/5 dark:odd:bg-white/5">
                      <td className="p-3 font-semibold text-left sticky left-0 bg-white dark:bg-neutral-900">
                        Compute
                      </td>
                      {nodes.map((node) => (
                        <td key={`${node.rack}-gn${node.node}-compute`} className="p-3 text-center">
                          <div className="space-y-1">
                            <Badge tone={toneFor(node.compute_status || "unknown")}>
                              {node.compute_status || "—"}
                            </Badge>
                            <div className="text-xs font-mono opacity-70">
                              {node.compute_ip || "—"}
                            </div>
                          </div>
                        </td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </div>

            {/* Summary by status */}
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-3">
                <h3 className="text-lg font-semibold">Status Summary</h3>
                {(() => {
                  const statusCounts = nodes.reduce((acc, node) => {
                    const status = node.overall_status || "unknown";
                    acc[status] = (acc[status] || 0) + 1;
                    return acc;
                  }, {});
                  
                  return Object.entries(statusCounts).map(([status, count]) => (
                    <div key={status} className="flex justify-between items-center">
                      <span className="capitalize">{status.replace("_", " ")}</span>
                      <Badge tone={toneFor(status)}>
                        {count} node{count !== 1 ? "s" : ""}
                      </Badge>
                    </div>
                  ));
                })()}
              </div>
              
              <div className="space-y-3">
                <h3 className="text-lg font-semibold">Troubleshooting</h3>
                {(() => {
                  const issues = nodes.filter(n => n.overall_status !== "ready");
                  if (issues.length === 0) {
                    return <div className="text-green-600">✅ All nodes are ready for validation</div>;
                  }
                  
                  const recommendations = [];
                  const networkDisconnected = issues.filter(n => n.overall_status === "network_disconnected");
                  const hardwareFailure = issues.filter(n => n.overall_status === "hardware_failure");
                  const bmcAuth = issues.filter(n => n.overall_status === "bmc_auth_failed");
                  
                  if (networkDisconnected.length > 0) {
                    recommendations.push(
                      <div key="network" className="text-sm">
                        <span className="text-orange-600">🌐 Network Issues:</span> {networkDisconnected.length} nodes
                        <div className="ml-4 text-xs opacity-70">Check network cables and switch ports</div>
                      </div>
                    );
                  }
                  
                  if (hardwareFailure.length > 0) {
                    recommendations.push(
                      <div key="hardware" className="text-sm">
                        <span className="text-red-600">🔴 Hardware Issues:</span> {hardwareFailure.length} nodes
                        <div className="ml-4 text-xs opacity-70">Check power and BMC connectivity</div>
                      </div>
                    );
                  }
                  
                  if (bmcAuth.length > 0) {
                    recommendations.push(
                      <div key="bmc" className="text-sm">
                        <span className="text-yellow-600">🔑 BMC Auth Issues:</span> {bmcAuth.length} nodes
                        <div className="ml-4 text-xs opacity-70">Verify BMC credentials</div>
                      </div>
                    );
                  }
                  
                  return recommendations;
                })()}
              </div>
            </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* -------------------- page -------------------- */
function RackDetailsModal({ rack, rackMeta, initialTab = "rack", crossrackId = "", onClose, withCtx }) {
  const [tab, setTab] = useState(initialTab); // 'rack' | 'nodes' | 'crossrack' | 'faults'
  useEffect(() => { setTab(initialTab); }, [initialTab]); // keep tab in sync

  // Resolve the crossrack id with NO manual input:
  const crId = (() => {
    if (isCrossrackId(crossrackId)) return String(crossrackId).trim().toLowerCase();
    if (isCrossrackId(rackMeta?.xrk_name)) return String(rackMeta.xrk_name).trim().toLowerCase();
    return null;
  })();
  const crValid = !!crId;

  // Node matrix data (rack tab)
  const { data: nodesBundle, error: nodesError } = usePoll(
    async () => {
      if (!rack || tab !== "nodes") return null;
      const u = new URL(withCtx("/api/nodes"));
      u.searchParams.append("racks", rack);
      const res = await fetch(u);
      const json = await res.json();
      return Array.isArray(json) ? json[0] : json;
    }, [rack, tab, withCtx], tab === "nodes" ? 60000 : 0);

  // Allow rendering without a rack ONLY on the crossrack tab
  if (!rack && tab !== "crossrack") return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start md:items-center justify-center p-4 bg-black/60" onClick={onClose}>
      <div
        className="w-full max-w-7xl max-h-[90vh] overflow-hidden rounded-2xl bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100 shadow-2xl border border-neutral-200 dark:border-neutral-700"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header (locked) */}
        <div className="flex items-center justify-between gap-3 p-4 border-b border-neutral-200 dark:border-neutral-700 sticky top-0 bg-white dark:bg-neutral-900 z-10">
          <div className="space-y-2">
            <h2 className="text-xl font-semibold">
              {tab === "crossrack"
                ? <>Crossrack: <span className="font-mono">{crValid ? crId : "—"}</span></>
                : <>Rack: <span className="font-mono">{rack}</span></>
              }
            </h2>
            <div className="flex items-center gap-3">
              <Tabs
                value={tab}
                onChange={(v) => {
                  setTab(v);
                  const u = new URL(window.location.href);
                  if (v === "crossrack" && crValid) {
                    u.searchParams.delete("rack");
                    u.searchParams.set("crossrack", crId);
                  } else {
                    if (rack) u.searchParams.set("rack", rack);
                    u.searchParams.delete("crossrack");
                  }
                  window.history.replaceState(null, "", u);
                }}
                options={[
                  { value: "nodes", label: "Node Validation", disabled: !rack },
                  { value: "rack",  label: "Rack Validation",     disabled: !rack },
                  { value: "crossrack", label: "Crossrack Validation" },
                  { value: "faults", label: "Faults & Tickets", disabled: !rack },
                ]}
              />
            </div>
            {/* ✅ Status chips row (only here) */}
            {rackMeta && (
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="opacity-70">Health:</span>
                <Badge tone={toneFor(rackMeta?.health)}>{rackMeta?.health ?? "—"}</Badge>

                <span className="opacity-70 ml-2">Node GV:</span>
                <Badge tone={toneFor(rackMeta?.node_status)}>{rackMeta?.node_status ?? "—"}</Badge>

                <span className="opacity-70 ml-2">Rack GV:</span>
                <Badge tone={toneFor(rackMeta?.rack_status)}>{rackMeta?.rack_status ?? "—"}</Badge>

                <span className="opacity-70 ml-2">XRK GV:</span>
                <Badge tone={toneFor(rackMeta?.xrk_status)}>{rackMeta?.xrk_status ?? "—"}</Badge>
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border px-2.5 py-1 text-sm hover:bg-black/5 dark:hover:bg-white/10"
            aria-label="Close"
          >
            ✖
          </button>
        </div>

        {/* Scrollable body */}
        <div className="p-4 overflow-y-auto max-h-[calc(90vh-72px)]">
          {tab === "rack" && (
            <RackGVTable
              rack={rack}
              rackMeta={rackMeta}
              emptyMessage={`${rack} validations Not Made`}
              withCtx={withCtx}
            />
          )}

          {tab === "nodes" && (
            <>
              {nodesError && (
                <div className="text-sm text-red-600 mb-3">Nodes error: {String(nodesError)}</div>
              )}
              {!nodesBundle ? (
                <TableSkeleton cols={8} rows={8} />
              ) : nodesBundle.dashboard && Object.keys(nodesBundle.dashboard).length > 0 ? (
                <NodesTable bundle={nodesBundle} />
              ) : (
                <div className="text-sm opacity-70">{rack} validations Not Made</div>
              )}
            </>
          )}

          {tab === "crossrack" && (
            <div className="space-y-4">
              {crValid ? (
                <RackGVTable
                  rack={crId}
                  rackMeta={null}
                  emptyMessage={`${crId} validations Not Made`}
                  withCtx={withCtx}
                />
              ) : (
                <div className="text-sm opacity-70">
                  {rack ? `${rack} validations Not Made` : `Crossrack validations Not Made`}
                </div>
              )}
            </div>
          )}

          {tab === "faults" && rack && (
            <div className="space-y-4">
              <Faults selectedRacks={[rack]} withCtx={withCtx} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [selectedRacks, setSelectedRacks] = useState([])
  const [refresh, setRefresh] = useState(60000)
  const { theme, setTheme } = useTheme()
  const [modalRack, setModalRack] = useState(null);
  const [modalTab, setModalTab] = useState("rack"); // 'rack' | 'nodes' | 'crossrack' | 'faults'
  const [modalCrossrackId, setModalCrossrackId] = useState("");
  const [currentPage, setCurrentPage] = useState(() => localStorage.getItem("currentPage") || "dashboard"); // 'site-layout' | 'pre-validation' | 'pdu-conformance' | 'dashboard' | 'faults'
  const [productionTab, setProductionTab] = useState("overview"); // 'overview' | 'node-allocation' | 'faults'
  const [validationTab, setValidationTab] = useState("dashboard"); // 'dashboard' | 'faults'
  const [isRunningTests, setIsRunningTests] = useState(false);
  const [currentContext, setCurrentContext] = useState(null);
  const [detailedResults, setDetailedResults] = useState(new Map()); // Cache detailed results by rack name
  const [cancellationToken, setCancellationToken] = useState(null); // For cancelling running tests
  const [abortController, setAbortController] = useState(null); // Global AbortController for all tests
  const [globalCancelFlag, setGlobalCancelFlag] = useState(false); // Global flag to stop test execution
  
  // Persist current page to localStorage
  useEffect(() => {
    localStorage.setItem("currentPage", currentPage);
  }, [currentPage]);
  
  const same = (a, b) => String(a || "").trim().toLowerCase() === String(b || "").trim().toLowerCase();

  // --- K8s context selection ---
  const [contexts, setContexts] = useState([]);
  const [selectedContext, setSelectedContext] = useState(() => localStorage.getItem("k8sContext") || "");
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(API + "/api/k8s/contexts");
        const json = await res.json();
        setContexts(json.contexts || []);
        if (!localStorage.getItem("k8sContext") && json.current) {
          setSelectedContext(json.current);
          localStorage.setItem("k8sContext", json.current);
        }
      } catch (e) {
        console.error("Failed to load contexts", e);
      }
    })();
  }, []);
  // Append ?context=... to backend paths (stable across renders)
  const withCtx = useCallback((path) => {
    const u = new URL(API + path);
    if (selectedContext) u.searchParams.set("context", selectedContext);
    return u.toString();
  }, [selectedContext]);

  // Cancel tests and clear results if context changes
  useEffect(() => {
    if (selectedContext !== currentContext) {
      // Only clear results if we're actually changing to a different context
      // If currentContext is null but selectedContext is the same, it means we just stopped tests
      if (currentContext === null && selectedContext !== "") {
        // This is just stopping tests, not changing contexts - don't clear results
        console.log('Tests stopped, preserving results');
        return;
      }
      
      console.log('Context changed, cancelling tests and clearing results');
      
      // Abort all ongoing API requests immediately
      if (abortController) {
        console.log('Aborting all ongoing API requests due to context change');
        abortController.abort();
        setAbortController(null);
      }
      
      // Generate new cancellation token to stop all running tests
      setCancellationToken(Date.now());
      setIsRunningTests(false);
      setCurrentContext(null);
      setDetailedResults(new Map()); // Clear all detailed results when context changes
    }
  }, [selectedContext, currentContext, abortController]);

  // Set the browser tab title
  useEffect(() => {
    document.title = "DC Validation Status";
  }, []);

  // cluster fetch (auto-refresh)
  const { data: cluster } = usePoll(
    async () => (await fetch(withCtx("/api/cluster"))).json(),
    [selectedContext],
    refresh
  )

  const bootstrapping = cluster == null;

  // inference-engine pods fetch
  const { data: inferencePods } = usePoll(
    async () => (await fetch(withCtx("/api/inference-pods"))).json(),
    [selectedContext],
    refresh
  )

  // derive pod prefixes from the cluster response
  const podPrefixes = useMemo(() => {
    const set = new Set()
    for (const r of (cluster?.racks || [])) Object.keys(r.pod_health || {}).forEach(p => set.add(p))
    return Array.from(set)
  }, [cluster])


  // persist rack selection locally (used by the Nodes section below)
  useEffect(() => {
    try { setSelectedRacks(JSON.parse(localStorage.getItem("racks") || "[]")) } catch {}
  }, [])
  useEffect(() => {
    localStorage.setItem("racks", JSON.stringify(selectedRacks))
  }, [selectedRacks])
  // Open modals based on URL (e.g., ?rack=c0r3 or ?crossrack=c0r3-c0r4)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const cr = params.get("crossrack");
    const r  = params.get("rack");
    if (cr && isCrossrackId(cr)) {
      setModalRack({ rack: null });
      setModalTab("crossrack");
      setModalCrossrackId(cr);
    } else if (r) {
      setModalRack({ rack: r });
      setModalTab("nodes");
    }
  }, []);
  // When viewing a crossrack and we don't yet have a rack, attach it once cluster data arrives
  useEffect(() => {
    if (modalTab !== "crossrack") return;
    if (!isCrossrackId(modalCrossrackId)) return;
    if (modalRack?.rack) return; // already have a rack
    const ownerRow = (cluster?.racks || []).find(
      r => String(r?.xrk_name || "").trim().toLowerCase() === modalCrossrackId
    );
    if (ownerRow) setModalRack(ownerRow);
  }, [modalTab, modalCrossrackId, modalRack?.rack, cluster]);

  // In App.jsx, inside App()
  useEffect(() => {
    // Ensure a single, managed favicon link exists
    let link = document.querySelector('link#app-favicon');
    if (!link) {
      link = document.createElement('link');
      link.id = 'app-favicon';
      link.rel = 'icon';
      link.type = 'image/svg+xml'; // change to 'image/png' if you use PNGs
      document.head.appendChild(link);
    }
    // Point to the right icon for the current theme
    link.href = theme === 'dark' ? '/groq-logo-white.svg' : '/groq-logo-black.svg';
  }, [theme]);


  // Open modal directly to the Crossrack tab with a specific ID (no search)
  const openCrossrack = (cr) => {
    // Try to find the rack row whose xrk_name matches this crossrack
    const ownerRow = (cluster?.racks || []).find(r => same(r?.xrk_name, cr)) || null;
    // Keep a rack in state so switching to "nodes" / "rack" tabs works
    setModalRack(ownerRow || { rack: null });
    setModalTab("crossrack");
    setModalCrossrackId(cr);
    const u = new URL(window.location.href);
    u.searchParams.delete("rack");
    u.searchParams.set("crossrack", cr);
    window.history.replaceState(null, "", u);
  };

  const closeRack = () => {
    setModalRack(null);
    setModalTab("rack");          // ensure modal no longer renders in crossrack mode
    setModalCrossrackId("");      // clear any selected crossrack
    const u = new URL(window.location.href);
    u.searchParams.delete("rack");
    u.searchParams.delete("crossrack");
    window.history.replaceState(null, "", u);
  };
  
  return (
    <div className="min-h-screen bg-white text-neutral-900 dark:bg-neutral-900 dark:text-neutral-100">
              <PageLoader show={bootstrapping && (currentPage === "dashboard" || currentPage === "production-status")} label="Fetching cluster status…" />
      <div className="max-w-7xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between gap-3">
          {/* Left side: logo + title */}
          <div className="flex items-center gap-2">
            {/* Light theme logo */}
            <img
             src={logoLight}
             alt="DC Validation Status – logo"
             className="h-20 w-30 object-contain block dark:hidden"
             loading="eager"
             decoding="async"
            />
            {/* Dark theme logo */}
            <img
             src={logoDark}
             alt="DC Validation Status – logo"
             className="h-20 w-30 object-contain hidden dark:block"
             loading="eager"
             decoding="async"
            />
            <h1 className="text-2xl font-bold">DC Validation Status</h1>
          </div>
          {/* Right side: auto-refresh + theme toggle */}
          <div className="flex items-center gap-3">
            <label className="text-sm">Auto-refresh</label>
            <select
              className="border rounded-xl px-2 py-1 bg-white dark:bg-neutral-800 dark:border-neutral-700"
              value={refresh}
              onChange={e => setRefresh(parseInt(e.target.value))}
            >
              <option value={0}>Off</option>
              <option value={60000}>60s</option>
            </select>
            {/* Context selector */}
            <select
              className="dropdown-down border rounded-xl px-2 py-1 bg-white dark:bg-neutral-800 dark:border-neutral-700"
              value={selectedContext}
              onChange={(e) => {
                const v = e.target.value;
                console.log('Context selector changed to:', v);
                
                // Immediately cancel any running tests and clear results
                if (isRunningTests) {
                  console.log('Cancelling running tests due to context change');
                  
                  // Abort all ongoing API requests immediately
                  if (abortController) {
                    console.log('Aborting all ongoing API requests due to context selector change');
                    abortController.abort();
                    setAbortController(null);
                  }
                  
                  setCancellationToken(Date.now()); // Generate new cancellation token
                  setIsRunningTests(false);
                  setCurrentContext(null);
                }
                
                // Clear all detailed results for the new context (since it's a different cluster)
                setDetailedResults(new Map());
                
                // Update the selected context
                setSelectedContext(v);
                localStorage.setItem("k8sContext", v);
              }}
              title="Kubernetes context"
            >
              {contexts.length === 0 ? (
                <option value="">(loading contexts...)</option>
              ) : (
                contexts.map((c) => <option key={c} value={c}>{c}</option>)
              )}
            </select>
            <ThemeToggle theme={theme} setTheme={setTheme} />
            <HamburgerMenu currentPage={currentPage} setCurrentPage={setCurrentPage} />
          </div>
        </div>


        {currentPage === "site-layout" && (
          <div className="space-y-3">
            <div className="text-lg font-semibold">Site layout</div>
            <div className="text-sm opacity-70">Coming soon...</div>
          </div>
        )}

        {currentPage === "pdu-conformance" && (
          <div className="space-y-3">
            <div className="text-lg font-semibold">PDU Conformance</div>
            <div className="text-sm opacity-70">Coming soon...</div>
          </div>
        )}

        {currentPage === "dashboard" && (
          <div className="space-y-3">
            <div className="text-lg font-semibold">Validation Status</div>
            
            {/* Tab Navigation */}
            <div className="border-b border-neutral-200 dark:border-neutral-700">
              <nav className="-mb-px flex space-x-8">
                <button
                  onClick={() => setValidationTab("dashboard")}
                  className={`py-2 px-1 border-b-2 font-medium text-sm ${
                    validationTab === "dashboard"
                      ? "border-blue-500 text-blue-600 dark:text-blue-400"
                      : "border-transparent text-neutral-500 hover:text-neutral-700 hover:border-neutral-300 dark:text-neutral-400 dark:hover:text-neutral-200"
                  }`}
                >
                  Overview
                </button>
                <button
                  onClick={() => setValidationTab("faults")}
                  className={`py-2 px-1 border-b-2 font-medium text-sm ${
                    validationTab === "faults"
                      ? "border-blue-500 text-blue-600 dark:text-blue-400"
                      : "border-transparent text-neutral-500 hover:text-neutral-700 hover:border-neutral-300 dark:text-neutral-400 dark:hover:text-neutral-200"
                  }`}
                >
                  Faults & Tickets
                </button>
              </nav>
            </div>

            {/* Tab Content */}
            {validationTab === "dashboard" && (
              <>
                {/* Summary */}
                <Summary summary={cluster?.summary} />

                {/* Cluster table (click Rack or Node GV to open modal) */}
                <div className="space-y-3">
                  <div className="text-lg font-semibold">Cluster</div>
                  <ClusterTable
                    racks={cluster?.racks || []}
                    podPrefixes={podPrefixes}
                    // Clicking the rack name → open modal on Node Matrix (as you already have)
                    onSelectRack={(row, tab = "nodes") => {
                      setModalRack(row);
                      setModalTab(tab); // set to specified tab, default to nodes
                      const u = new URL(window.location.href);
                      u.searchParams.set("rack", row.rack);
                      u.searchParams.delete("crossrack");
                      window.history.replaceState(null, "", u);
                    }}
                    // Clicking the XRK hostname (e.g., c0r3-c0r4) → open Crossrack tab for that ID
                    onOpenCrossrack={openCrossrack}
                  />
                </div>
              </>
            )}

            {validationTab === "faults" && (
              <Faults selectedRacks={selectedRacks} withCtx={withCtx} />
            )}
          </div>
        )}

        {currentPage === "pre-validation" && <PreValidation withCtx={withCtx} isRunningTests={isRunningTests} setIsRunningTests={setIsRunningTests} currentContext={currentContext} setCurrentContext={setCurrentContext} detailedResults={detailedResults} setDetailedResults={setDetailedResults} selectedContext={selectedContext} cancellationToken={cancellationToken} setCancellationToken={setCancellationToken} abortController={abortController} setAbortController={setAbortController} globalCancelFlag={globalCancelFlag} setGlobalCancelFlag={setGlobalCancelFlag} />}


        {currentPage === "production-status" && (
          <div className="space-y-3">
            <div className="text-lg font-semibold">Production Status</div>
            
            {/* Tab Navigation */}
            <div className="border-b border-neutral-200 dark:border-neutral-700">
              <nav className="-mb-px flex space-x-8">
                <button
                  onClick={() => setProductionTab("overview")}
                  className={`py-2 px-1 border-b-2 font-medium text-sm ${
                    productionTab === "overview"
                      ? "border-blue-500 text-blue-600 dark:text-blue-400"
                      : "border-transparent text-neutral-500 hover:text-neutral-700 hover:border-neutral-300 dark:text-neutral-400 dark:hover:text-neutral-200"
                  }`}
                >
                  Overview
                </button>
                <button
                  onClick={() => setProductionTab("node-allocation")}
                  className={`py-2 px-1 border-b-2 font-medium text-sm ${
                    productionTab === "node-allocation"
                      ? "border-blue-500 text-blue-600 dark:text-blue-400"
                      : "border-transparent text-neutral-500 hover:text-neutral-700 hover:border-neutral-300 dark:text-neutral-400 dark:hover:text-neutral-200"
                  }`}
                >
                  Node Allocation
                </button>
                <button
                  onClick={() => setProductionTab("faults")}
                  className={`py-2 px-1 border-b-2 font-medium text-sm ${
                    productionTab === "faults"
                      ? "border-blue-500 text-blue-600 dark:text-blue-400"
                      : "border-transparent text-neutral-500 hover:text-neutral-700 hover:border-neutral-300 dark:text-neutral-400 dark:hover:text-neutral-200"
                  }`}
                >
                  Faults & Tickets
                </button>
              </nav>
            </div>

            {/* Tab Content */}
            {productionTab === "overview" && (
              <>
                {/* Summary */}
                <ProductionSummary summary={cluster?.summary} racks={cluster?.racks || []} inferencePods={inferencePods} />

                {/* Production table (simplified cluster table without validation columns) */}
                <ProductionTable
                  racks={cluster?.racks || []}
                  podPrefixes={podPrefixes}
                  inferencePods={inferencePods}
                  onSelectRack={(row) => {
                    setModalRack(row);
                    setModalTab("nodes");
                    const u = new URL(window.location.href);
                    u.searchParams.set("rack", row.rack);
                    u.searchParams.delete("crossrack");
                    window.history.replaceState(null, "", u);
                  }}
                />
              </>
            )}

            {productionTab === "node-allocation" && (
              <NodeAllocation
                racks={cluster?.racks || []}
                inferencePods={inferencePods}
              />
            )}

            {productionTab === "faults" && (
              <Faults selectedRacks={selectedRacks} withCtx={withCtx} />
            )}
          </div>
        )}
      </div>

      {/* Modal overlay with node validation table for the clicked rack */}
      {(
        (modalRack?.rack) ||
        (modalTab === "crossrack" && isCrossrackId(modalCrossrackId))
      ) && (
        <RackDetailsModal
          rack={modalRack?.rack || null}
          rackMeta={modalRack || null}
          initialTab={modalTab}
          crossrackId={modalCrossrackId}
          onClose={closeRack}
          withCtx={withCtx}
        />
      )}
    </div>
  )
}
