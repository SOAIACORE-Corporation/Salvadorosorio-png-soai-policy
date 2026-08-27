import EvidenceExplorerClient from "./evidence-explorer-client";

export default async function EvidenceExplorerPage({ params, searchParams }) {
  const { evidenceRefId } = await params;
  const query = await searchParams;
  return <EvidenceExplorerClient evidenceRefId={evidenceRefId} claimId={query?.claim_id ?? ""} />;
}
