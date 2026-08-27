import {
  loadContextInspector,
  publicContextInspectorError,
} from "../../../../../server/context-inspector.mjs";

export const dynamic = "force-dynamic";

export async function GET(_request, { params }) {
  try {
    const { capsuleId } = await params;
    const data = await loadContextInspector(capsuleId);
    return Response.json(data, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    const failure = publicContextInspectorError(error);
    return Response.json({ error: failure.error }, { status: failure.status });
  }
}
