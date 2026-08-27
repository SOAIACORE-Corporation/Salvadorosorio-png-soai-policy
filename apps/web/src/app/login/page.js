import Link from "next/link";

import { safeReturnTo } from "../../server/auth.mjs";

export default async function LoginPage({ searchParams }) {
  const query = await searchParams;
  const returnTo = safeReturnTo(query?.return_to);
  return (
    <section className="auth-page">
      <p className="eyebrow">Controlled pilot access</p>
      <h1>Sign in as an authorized operator</h1>
      <p>
        SOAIACORE uses the approved organization identity provider. Anonymous access and
        self-service registration are disabled.
      </p>
      <Link
        className="button primary-action"
        href={`/api/auth/login?return_to=${encodeURIComponent(returnTo)}`}
      >
        Continue with organization sign-in
      </Link>
    </section>
  );
}
