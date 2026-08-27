import { authErrorResponse, completeOidcLogin } from "../../../../server/auth.mjs";

export const dynamic = "force-dynamic";

export async function GET(request) {
  try {
    return await completeOidcLogin(request);
  } catch (error) {
    return authErrorResponse(error);
  }
}
