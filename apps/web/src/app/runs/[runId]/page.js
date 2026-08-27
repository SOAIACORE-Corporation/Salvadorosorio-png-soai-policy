import { coreRequest } from "../../../server/core-client.mjs";
import { requirePageSession } from "../../../server/auth-next.js";
import { withOperatorContext } from "../../../server/operator-context.mjs";
import RunStatusClient from "./run-status-client";

export const dynamic = "force-dynamic";

export default async function RunPage({ params }) {
  const { runId } = await params;
  const returnTo = `/runs/${encodeURIComponent(runId)}`;
  const session = await requirePageSession(returnTo);
  const run = await withOperatorContext(session, () =>
    coreRequest(`/v1/runs/${encodeURIComponent(runId)}`),
  );
  return <RunStatusClient runId={runId} initialRun={run} />;
}
