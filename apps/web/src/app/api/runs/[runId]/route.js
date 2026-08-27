import { NextResponse } from "next/server";
import { coreRequest } from "../../../../server/core-client.mjs";
import { authenticatedApi } from "../../../../server/auth-next.js";

export const dynamic = "force-dynamic";

export async function GET(request, { params }) {
  return authenticatedApi(request, async () => {
    const { runId } = await params;
    try {
      const run = await coreRequest(`/v1/runs/${encodeURIComponent(runId)}`);
      return NextResponse.json(run, {
        headers: { "Cache-Control": "no-store" },
      });
    } catch {
      return NextResponse.json(
        {
          error: {
            code: "RUN_STATUS_UNAVAILABLE",
            message: "The Core service is temporarily unavailable.",
            stage: "RUN_STATUS",
            retryable: true,
            correlation_id: null,
          },
        },
        { status: 502, headers: { "Cache-Control": "no-store" } },
      );
    }
  });
}
