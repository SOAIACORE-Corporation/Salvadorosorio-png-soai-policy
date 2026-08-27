import { authErrorResponse, beginOidcLogin } from "../../../../server/auth.mjs";

export const dynamic = "force-dynamic";

export async function GET(request) {
  try {
    return await beginOidcLogin(request);
  } catch (error) {
    return authErrorResponse(error);
  }
}
