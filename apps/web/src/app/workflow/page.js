import OperatorWorkflow from "./workflow-client";
import { loadOperatorWorkflow } from "../../server/operator-workflow.mjs";

export const dynamic = "force-dynamic";

export default async function OperatorWorkflowPage() {
  const initialData = await loadOperatorWorkflow();
  return (
    <section className="workflow-shell">
      <div className="workflow-hero">
        <div>
          <p className="eyebrow">Internal operator · MOCK only</p>
          <h1>Build a synthetic analysis run</h1>
          <p>
            Select or create each resource in order. Technical identifiers remain visible for
            traceability, but the workflow never asks you to copy or type them.
          </p>
        </div>
        <div className="mode-badge" aria-label="Provider mode MOCK">
          <span>Provider mode</span>
          <strong>MOCK</strong>
        </div>
      </div>
      <OperatorWorkflow initialData={initialData} />
    </section>
  );
}
