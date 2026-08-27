"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

const TERMINAL_STATUSES = new Set([
  "COMPLETED",
  "REVIEW_REQUIRED",
  "DENIED",
  "FAILED_PRECHECK",
  "FAILED_EXECUTION",
  "FAILED_VALIDATION",
]);

export default function RunStatusClient({ runId, initialRun }) {
  const [run, setRun] = useState(initialRun);
  const [refreshError, setRefreshError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const terminal = useMemo(() => TERMINAL_STATUSES.has(run?.status), [run?.status]);

  useEffect(() => {
    if (terminal) return undefined;

    let cancelled = false;
    const refresh = async () => {
      setRefreshing(true);
      try {
        const response = await fetch(`/api/runs/${encodeURIComponent(runId)}`, {
          cache: "no-store",
          headers: { Accept: "application/json" },
        });
        if (!response.ok) throw new Error("Unable to refresh run status.");
        const nextRun = await response.json();
        if (!cancelled) {
          setRun(nextRun);
          setRefreshError("");
        }
      } catch (error) {
        if (!cancelled) setRefreshError(error.message);
      } finally {
        if (!cancelled) setRefreshing(false);
      }
    };

    const interval = window.setInterval(refresh, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [runId, terminal]);

  const status = run?.status ?? "UNKNOWN";
  const statusClass = `status-badge status-${status.toLowerCase().replaceAll("_", "-")}`;

  return (
    <section className="run-page">
      <p className="eyebrow">Run status</p>
      <div className="run-heading">
        <div>
          <h1>{run?.run_id ?? runId}</h1>
          <p className="page-intro">The portal refreshes active runs automatically.</p>
        </div>
        <span className={statusClass} aria-live="polite">{status}</span>
      </div>
      <dl className="run-summary">
        <dt>Job</dt><dd>{run?.job_status ?? "UNAVAILABLE"}</dd>
        <dt>Mode</dt><dd>{run?.mode ?? "MOCK"}</dd>
        <dt>Refresh</dt><dd>{terminal ? "Complete" : refreshing ? "Checking…" : "Every 3 seconds"}</dd>
      </dl>
      {refreshError ? <p className="notice error" role="status">{refreshError} We will retry automatically.</p> : null}
      {terminal ? (
        <div className="page-actions">
          <Link className="button" href={`/receipts/${encodeURIComponent(run.run_id)}`}>
            View ContextReceipt
          </Link>
          <Link className="text-link" href="/workflow">Start another run</Link>
        </div>
      ) : (
        <p className="loading-panel" role="status">The worker is processing this run. Keep this page open to follow the transition.</p>
      )}
    </section>
  );
}
