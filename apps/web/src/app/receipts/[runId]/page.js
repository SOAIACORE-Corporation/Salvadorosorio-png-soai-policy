import { coreRequest } from "../../../server/core-client.mjs";

export const dynamic = "force-dynamic";

export default async function ReceiptPage({ params }) {
  const { runId } = await params;
  const receipt = await coreRequest(`/v1/runs/${encodeURIComponent(runId)}/receipt`);
  return (
    <section>
      <p className="eyebrow">ContextReceipt</p>
      <h1>{receipt.context_receipt_id}</h1>
      <dl>
        <dt>Output</dt><dd>{receipt.output_status}</dd>
        <dt>Review policy</dt><dd>{receipt.review_mode ?? "NONE"}</dd>
        <dt>Precheck</dt><dd>{receipt.precheck_status}</dd>
      </dl>
      <h2>Claims</h2>
      <pre>{JSON.stringify(receipt.claims_created, null, 2)}</pre>
      <h2>Limitations</h2>
      <pre>{JSON.stringify(receipt.limitations, null, 2)}</pre>
    </section>
  );
}

