import { coreRequest } from "../../../server/core-client.mjs";
import RunStatusClient from "./run-status-client";

export const dynamic = "force-dynamic";

export default async function RunPage({ params }) {
  const { runId } = await params;
  const run = await coreRequest(`/v1/runs/${encodeURIComponent(runId)}`);
  return <RunStatusClient runId={runId} initialRun={run} />;
}
