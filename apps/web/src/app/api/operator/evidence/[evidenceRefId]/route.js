import {
  loadEvidenceExplorer,
  publicEvidenceExplorerError,
} from "../../../../../server/evidence-explorer.mjs";

export const dynamic = "force-dynamic";

export async function GET(request, { params }) {
  try {
    const { evidenceRefId } = await params;
    const claimId = new URL(request.url).searchParams.get("claim_id") ?? "";
    const data = await loadEvidenceExplorer(evidenceRefId, { claimId });
    return Response.json(data, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    const failure = publicEvidenceExplorerError(error);
    return Response.json({ error: failure.error }, { status: failure.status });
  }
}
