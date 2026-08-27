import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import {
  AuthError,
  SESSION_COOKIE,
  authErrorResponse,
  requireRole,
  requireSession,
  sessionById,
} from "./auth.mjs";
import { withOperatorContext } from "./operator-context.mjs";

export async function requirePageSession(returnTo = "/", requiredRole = "OPERATOR") {
  const store = await cookies();
  const session = sessionById(store.get(SESSION_COOKIE)?.value);
  if (!session) redirect(`/login?return_to=${encodeURIComponent(returnTo)}`);
  try {
    return requireRole(session, requiredRole);
  } catch (error) {
    if (error instanceof AuthError) redirect("/forbidden");
    throw error;
  }
}

export async function authenticatedApi(request, callback, requiredRole = "OPERATOR") {
  try {
    const session = requireSession(request, requiredRole);
    return await withOperatorContext(session, () => callback(session));
  } catch (error) {
    return authErrorResponse(error);
  }
}
