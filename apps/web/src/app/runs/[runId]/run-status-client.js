"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

const TERMINAL_STATUSES = new Set([
  "COMPLETED",
  "REVIEW_REQUIRED",
  "DENIED",
  "FAILED_PRECHECK",
  "FAILED_EXECUTION",
  "FAILED_VALIDATION",
  "FAILED_RECEIPT",
]);

const LIFECYCLE_STAGES = [
  "CONTEXT",
  "SYNC",
  "PRECHECK",
  "EXECUTION",
  "AUTOMATED_VALIDATION",
  "REVIEW_POLICY",
  "RECEIPT",
];

const MAX_AUTO_REFRESHES = 12;
const BASE_REFRESH_DELAY_MS = 3000;
const MAX_REFRESH_DELAY_MS = 15000;

function safeFailure(error, fallback = "The Core service is temporarily unavailable.") {
  const failure = error?.failure ?? {};
  return {
    message: typeof failure.message === "string" ? failure.message : fallback,
    code: typeof failure.code === "string" ? failure.code : "RUN_STATUS_UNAVAILABLE",
    stage: typeof failure.stage === "string" ? failure.stage : "RUN_STATUS",
    retryable: failure.retryable !== false,
    correlationId: typeof failure.correlation_id === "string" ? failure.correlation_id : null,
  };
}

function terminalError(run) {
  const lifecycle = run?.metadata?.lifecycle ?? {};
  const stageResults = run?.metadata?.stage_results ?? {};
  const failedStage = LIFECYCLE_STAGES.find((stage) => ["FAIL", "FAILED"].includes(lifecycle[stage]));
  const details = failedStage ? stageResults[failedStage] ?? {} : {};
  if (!failedStage && !run?.error && !String(run?.status ?? "").startsWith("FAILED")) return null;
  const code = run?.error?.code ?? details.code;
  const stage = run?.error?.stage ?? failedStage;
  return {
    code: typeof code === "string" ? code : run?.status ?? "RUN_TERMINAL_FAILURE",
    stage: typeof stage === "string" ? stage : "RUN_STATUS",
    retryable: run?.error?.retryable === true || details.retryable === true,
    correlationId: typeof run?.error?.correlation_id === "string" ? run.error.correlation_id : null,
  };
}

function currentStage(run) {
  const lifecycle = run?.metadata?.lifecycle ?? {};
  const failed = LIFECYCLE_STAGES.find((stage) => ["FAIL", "FAILED"].includes(lifecycle[stage]));
  if (failed) return failed;
  const active = LIFECYCLE_STAGES.find((stage) => lifecycle[stage] !== "PASS");
  return active ?? (run?.status === "COMPLETED" ? "RECEIPT" : "RUN_STATUS");
}

function stageClass(value) {
  if (["PASS", "COMPLETED"].includes(value)) return "lifecycle-pass";
  if (["FAIL", "FAILED"].includes(value)) return "lifecycle-fail";
  return "lifecycle-pending";
}

export default function RunStatusClient({ runId, initialRun }) {
  const [run, setRun] = useState(initialRun);
  const [refreshFailure, setRefreshFailure] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [autoRefreshes, setAutoRefreshes] = useState(0);
  const [pollingEnabled, setPollingEnabled] = useState(true);
  const terminal = useMemo(() => TERMINAL_STATUSES.has(run?.status), [run?.status]);
  const exhausted = !terminal && autoRefreshes >= MAX_AUTO_REFRESHES;

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const response = await fetch(`/api/runs/${encodeURIComponent(runId)}`, {
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const error = new Error(payload?.error?.message);
        error.failure = payload?.error;
        throw error;
      }
      setRun(payload);
      setRefreshFailure(null);
      setAutoRefreshes((count) => count + 1);
    } catch (error) {
      setRefreshFailure(safeFailure(error));
      setAutoRefreshes((count) => count + 1);
    } finally {
      setRefreshing(false);
    }
  }, [runId]);

  useEffect(() => {
    if (terminal || !pollingEnabled || exhausted) return undefined;
    const delay = Math.min(BASE_REFRESH_DELAY_MS * 2 ** Math.min(autoRefreshes, 3), MAX_REFRESH_DELAY_MS);
    const timeout = window.setTimeout(refresh, delay);
    return () => window.clearTimeout(timeout);
  }, [autoRefreshes, exhausted, pollingEnabled, refresh, terminal]);

  const retryStatus = () => {
    setRefreshFailure(null);
    setAutoRefreshes(0);
    setPollingEnabled(true);
    void refresh();
  };

  const status = run?.status ?? "UNKNOWN";
  const statusClass = `status-badge status-${status.toLowerCase().replaceAll("_", "-")}`;
  const lifecycle = run?.metadata?.lifecycle ?? {};
  const runError = terminal ? terminalError(run) : null;

  return (
    <section className="run-page">
      <p className="eyebrow">Run status</p>
      <div className="run-heading">
        <div>
          <h1>{run?.run_id ?? runId}</h1>
          <p className="page-intro">Active runs refresh with bounded backoff through the Web BFF.</p>
        </div>
        <span className={statusClass} aria-live="polite">{status}</span>
      </div>

      <dl className="run-summary">
        <dt>Job</dt><dd>{run?.job_status ?? "UNAVAILABLE"}</dd>
        <dt>Mode</dt><dd>{run?.mode ?? "MOCK"}</dd>
        <dt>Attempts</dt><dd>{run?.attempts ?? "UNAVAILABLE"}</dd>
        <dt>Stage</dt><dd>{currentStage(run)}</dd>
        <dt>Refresh</dt><dd>{terminal ? "Complete" : exhausted ? "Paused · retry available" : refreshing ? "Checking…" : "Bounded backoff"}</dd>
      </dl>

      <section className="lifecycle-panel" aria-labelledby="lifecycle-heading">
        <div className="section-heading">
          <h2 id="lifecycle-heading">Lifecycle</h2>
          <span>{run?.job_status ?? status}</span>
        </div>
        <ol className="lifecycle-map">
          {LIFECYCLE_STAGES.map((stage) => {
            const value = lifecycle[stage] ?? "PENDING";
            return <li key={stage} className={stageClass(value)}><span>{stage.replaceAll("_", " ")}</span><strong>{value}</strong></li>;
          })}
        </ol>
      </section>

      {refreshFailure ? (
        <div className="notice error error-details" role="status">
          <strong>{refreshFailure.message}</strong>
          <span>Code: {refreshFailure.code} · Stage: {refreshFailure.stage} · Retryable: {refreshFailure.retryable ? "yes" : "no"}</span>
          {refreshFailure.correlationId ? <span>Correlation: {refreshFailure.correlationId}</span> : null}
          <button type="button" onClick={retryStatus}>Retry status check</button>
        </div>
      ) : null}

      {runError ? (
        <div className={`notice ${runError.retryable ? "error" : "warning"}`} role="status">
          <strong>{status === "REVIEW_REQUIRED" ? "Review required by policy." : "Run reached a terminal state."}</strong>
          <span>Code: {runError.code} · Stage: {runError.stage} · Retryable: {runError.retryable ? "yes" : "no"}</span>
        </div>
      ) : null}

      {terminal ? (
        <div className="page-actions">
          <Link className="button" href={`/receipts/${encodeURIComponent(run.run_id)}`}>
            View ContextReceipt
          </Link>
          <Link className="text-link" href="/workflow">Start another run</Link>
        </div>
      ) : (
        <div className="loading-panel" role="status">
          <span>{exhausted ? "Automatic checks are paused after the bounded retry window." : "The worker is processing this run; the page will continue checking."}</span>
          <button type="button" onClick={retryStatus}>Refresh status</button>
        </div>
      )}
    </section>
  );
}
