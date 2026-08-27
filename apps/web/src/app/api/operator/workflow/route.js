import {
  loadOperatorWorkflow,
  performOperatorAction,
  publicOperatorError,
} from "../../../../server/operator-workflow.mjs";
import { authenticatedApi } from "../../../../server/auth-next.js";

export const dynamic = "force-dynamic";

function errorResponse(error) {
  const failure = publicOperatorError(error);
  return Response.json({ error: failure.error }, { status: failure.status });
}

export async function GET(request) {
  return authenticatedApi(request, async () => {
    const url = new URL(request.url);
    try {
      const snapshot = await loadOperatorWorkflow({
        projectId: url.searchParams.get("project_id"),
        corpusId: url.searchParams.get("corpus_id"),
        contextId: url.searchParams.get("context_id"),
        capsuleId: url.searchParams.get("context_capsule_id"),
      });
      return Response.json(snapshot, { headers: { "Cache-Control": "no-store" } });
    } catch (error) {
      return errorResponse(error);
    }
  });
}

export async function POST(request) {
  return authenticatedApi(request, async () => {
    let input;
    try {
      input = await request.json();
    } catch {
      return Response.json(
        { error: { code: "OPERATOR_JSON_INVALID", message: "The request body is invalid." } },
        { status: 400 },
      );
    }
    try {
      return Response.json(await performOperatorAction(input), {
        headers: { "Cache-Control": "no-store" },
      });
    } catch (error) {
      return errorResponse(error);
    }
  });
}
