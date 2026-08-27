"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

const STATUS_OPTIONS = ["", "QUEUED", "RUNNING", "REVIEW_REQUIRED", "COMPLETED", "DENIED", "FAILED_PRECHECK", "FAILED_EXECUTION", "FAILED_VALIDATION", "FAILED_RECEIPT"];
const TERMINAL = new Set(STATUS_OPTIONS.slice(3));

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function statusClass(status) { return `status-badge status-${String(status ?? "unknown").toLowerCase().replaceAll("_", "-")}`; }

export default function RunsHistoryClient() {
  const [filters, setFilters] = useState({ status: "", project_id: "", profile_id: "" });
  const [options, setOptions] = useState({ projects: [], profiles: [] });
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (nextFilters = filters) => {
    setLoading(true); setError("");
    try {
      const query = new URLSearchParams({ ...nextFilters, limit: "25" });
      const response = await fetch(`/api/operator/runs?${query}`, { cache: "no-store", headers: { Accept: "application/json" } });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload?.error?.message ?? "The run history could not be loaded.");
      setRuns(Array.isArray(payload.runs) ? payload.runs : []);
      setOptions(payload.filters ?? { projects: [], profiles: [] });
    } catch (failure) { setError(failure.message); } finally { setLoading(false); }
  }, [filters]);

  useEffect(() => { void load(); }, [load]);

  function applyFilters(event) { event.preventDefault(); void load(filters); }

  return <section className="history-page">
    <div className="workflow-hero"><div><p className="eyebrow">Operator audit · Read only</p><h1>Runs history</h1><p>Locate prior synthetic runs without copying technical identifiers. Results are bounded to the 25 most recent records.</p></div><div className="mode-badge" aria-label="Provider mode MOCK"><span>Provider mode</span><strong>MOCK</strong></div></div>
    <form className="history-filters" onSubmit={applyFilters} aria-label="Run history filters">
      <label>Status<select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}>{STATUS_OPTIONS.map((value) => <option key={value} value={value}>{value || "All statuses"}</option>)}</select></label>
      <label>Project<select value={filters.project_id} onChange={(event) => setFilters({ ...filters, project_id: event.target.value })}><option value="">All projects</option>{options.projects.map((item) => <option key={item.project_id} value={item.project_id}>{item.name ?? item.project_id}</option>)}</select></label>
      <label>Profile<select value={filters.profile_id} onChange={(event) => setFilters({ ...filters, profile_id: event.target.value })}><option value="">All profiles</option>{options.profiles.map((item) => <option key={`${item.analysis_profile_id}::${item.version}`} value={item.analysis_profile_id}>{item.name ?? item.analysis_profile_id} · {item.version}</option>)}</select></label>
      <button type="submit" disabled={loading}>{loading ? "Loading…" : "Apply filters"}</button>
    </form>
    {error ? <div className="notice error" role="alert">{error}<button type="button" onClick={() => void load()}>Retry</button></div> : null}
    {loading && !runs.length ? <p className="loading-panel" role="status">Loading recent runs through the Web BFF.</p> : null}
    {!loading && !error && !runs.length ? <p className="empty-state">No runs match these filters.</p> : null}
    {runs.length ? <div className="run-history-list" aria-live="polite">{runs.map((run) => <article className={`history-card ${TERMINAL.has(run.status) ? "terminal" : "active"}`} key={run.run_id}>
      <div className="history-card-heading"><div><span className="history-state">{TERMINAL.has(run.status) ? "Terminal" : "Active"}</span><h2>{run.run_id}</h2></div><span className={statusClass(run.status)}>{run.status}</span></div>
      <dl><dt>Job</dt><dd>{run.job_status ?? "—"}</dd><dt>Project</dt><dd>{run.project_id ?? "—"}</dd><dt>Profile</dt><dd>{run.analysis_profile_id ?? "—"} · {run.analysis_profile_version ?? "—"}</dd><dt>Attempts</dt><dd>{run.attempts ?? "—"}</dd><dt>Started</dt><dd>{formatDate(run.started_at)}</dd><dt>Completed</dt><dd>{formatDate(run.completed_at)}</dd><dt>Output</dt><dd>{run.output_status ?? (run.status === "REVIEW_REQUIRED" ? "REVIEW_REQUIRED" : "—")}</dd><dt>Review</dt><dd>{run.review_mode ?? "—"}</dd></dl>
      <div className="page-actions"><Link className="button" href={`/runs/${encodeURIComponent(run.run_id)}`}>View status</Link>{run.context_capsule_id ? <Link className="text-link" href={`/context-inspector/${encodeURIComponent(run.context_capsule_id)}`}>Inspect capsule</Link> : null}{TERMINAL.has(run.status) ? <Link className="text-link" href={`/receipts/${encodeURIComponent(run.run_id)}`}>View receipt</Link> : null}</div>
    </article>)}</div> : null}
  </section>;
}
