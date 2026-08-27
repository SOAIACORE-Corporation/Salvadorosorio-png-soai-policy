import { coreRequest } from "../../../server/core-client.mjs";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function ReceiptPage({ params }) {
  const { runId } = await params;
  const receipt = await coreRequest(`/v1/runs/${encodeURIComponent(runId)}/receipt`);
  return (
    <section className="receipt-page">
      <p className="eyebrow">ContextReceipt</p>
      <h1>{receipt.context_receipt_id}</h1>
      <p className="page-intro">Immutable terminal evidence for this synthetic run.</p>
      <dl>
        <dt>Output</dt><dd>{receipt.output_status}</dd>
        <dt>Review policy</dt><dd>{receipt.review_mode ?? "NONE"}</dd>
        <dt>Precheck</dt><dd>{receipt.precheck_status}</dd>
      </dl>
      <h2>Claims</h2>
      <pre>{JSON.stringify(receipt.claims_created, null, 2)}</pre>
      <h2>Limitations</h2>
      <pre>{JSON.stringify(receipt.limitations, null, 2)}</pre>
      <div className="page-actions">
        <Link className="button" href={`/runs/${encodeURIComponent(runId)}`}>Back to run status</Link>
        <Link className="text-link" href="/workflow">Start another run</Link>
      </div>
    </section>
  );
}
