import Link from "next/link";
import { coreRequest } from "../../../server/core-client.mjs";

export const dynamic = "force-dynamic";

export default async function RunPage({ params }) {
  const { runId } = await params;
  const run = await coreRequest(`/v1/runs/${encodeURIComponent(runId)}`);
  const terminal = [
    "COMPLETED",
    "REVIEW_REQUIRED",
    "DENIED",
    "FAILED_PRECHECK",
    "FAILED_EXECUTION",
    "FAILED_VALIDATION",
  ].includes(run.status);
  return (
    <section>
      <p className="eyebrow">Run</p>
      <h1>{run.run_id}</h1>
      <dl>
        <dt>Status</dt><dd>{run.status}</dd>
        <dt>Job</dt><dd>{run.job_status ?? "UNAVAILABLE"}</dd>
        <dt>Mode</dt><dd>{run.mode}</dd>
      </dl>
      {terminal ? (
        <Link className="button" href={`/receipts/${encodeURIComponent(run.run_id)}`}>
          View ContextReceipt
        </Link>
      ) : (
        <p>The manually triggered Worker has not produced a terminal receipt yet.</p>
      )}
    </section>
  );
}

