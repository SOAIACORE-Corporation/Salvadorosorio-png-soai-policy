export async function GET() {
  return Response.json({ status: "LIVE", service: "soaiacore-web", version: "0.1.0" });
}

