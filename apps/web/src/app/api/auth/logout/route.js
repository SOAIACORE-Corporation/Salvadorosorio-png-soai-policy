import { logout } from "../../../../server/auth.mjs";

export const dynamic = "force-dynamic";

export async function POST(request) {
  return logout(request);
}
