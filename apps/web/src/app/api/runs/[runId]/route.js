import { NextResponse } from "next/server";
import { coreRequest } from "../../../../server/core-client.mjs";

export const dynamic = "force-dynamic";

export async function GET(_request, { params }) {
  const { runId } = await params;
  try {
    const run = await coreRequest(`/v1/runs/${encodeURIComponent(runId)}`);
    return NextResponse.json(run, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { error: { code: "RUN_STATUS_UNAVAILABLE", message: "Unable to load run status." } },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
