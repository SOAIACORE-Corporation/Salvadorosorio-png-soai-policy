import EvidenceExplorerClient from "./evidence-explorer-client";
import { requirePageSession } from "../../../server/auth-next.js";

export default async function EvidenceExplorerPage({ params, searchParams }) {
  const { evidenceRefId } = await params;
  const query = await searchParams;
  await requirePageSession(`/evidence-explorer/${encodeURIComponent(evidenceRefId)}`);
  return <EvidenceExplorerClient evidenceRefId={evidenceRefId} claimId={query?.claim_id ?? ""} />;
}
