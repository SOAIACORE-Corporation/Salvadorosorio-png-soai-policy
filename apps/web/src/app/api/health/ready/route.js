import { coreRequest } from "../../../../server/core-client.mjs";

export async function GET() {
  try {
    const core = await coreRequest("/health/ready");
    return Response.json({ status: "READY", service: "soaiacore-web", core });
  } catch (error) {
    return Response.json(
      { status: "NOT_READY", service: "soaiacore-web", blocker: error.code },
      { status: 503 },
    );
  }
}

