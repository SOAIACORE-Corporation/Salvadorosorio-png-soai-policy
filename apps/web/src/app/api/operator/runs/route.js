import { loadRunsHistory, publicRunsHistoryError } from "../../../../server/runs-history.mjs";
import { authenticatedApi } from "../../../../server/auth-next.js";

export const dynamic = "force-dynamic";

export async function GET(request) {
  return authenticatedApi(request, async () => {
    const url = new URL(request.url);
    try {
      const data = await loadRunsHistory({
        status: url.searchParams.get("status") ?? "",
        projectId: url.searchParams.get("project_id") ?? "",
        profileId: url.searchParams.get("profile_id") ?? "",
        limit: url.searchParams.get("limit") ?? "25",
      });
      return Response.json(data, { headers: { "Cache-Control": "no-store" } });
    } catch (error) {
      const failure = publicRunsHistoryError(error);
      return Response.json({ error: failure.error }, { status: failure.status });
    }
  });
}
