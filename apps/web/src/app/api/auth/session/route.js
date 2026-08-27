import { authErrorResponse, requireSession, safeSession } from "../../../../server/auth.mjs";

export const dynamic = "force-dynamic";

export async function GET(request) {
  try {
    return Response.json(safeSession(requireSession(request)), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    return authErrorResponse(error);
  }
}
