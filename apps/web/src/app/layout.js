import Link from "next/link";
import { cookies } from "next/headers";
import { SESSION_COOKIE, sessionById } from "../server/auth.mjs";
import "./styles.css";

export const metadata = {
  title: "SOAIACORE P0",
  description: "Synthetic-only SOAIACORE P0 runtime pilot",
};

export default async function RootLayout({ children }) {
  const cookieStore = await cookies();
  const session = sessionById(cookieStore.get(SESSION_COOKIE)?.value);
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="header-inner">
            <Link className="brand" href="/">SOAIACORE P0</Link>
            <nav aria-label="Primary navigation">
              <Link href="/">Portal</Link>
              <Link href="/workflow">Operator workflow</Link>
              <Link href="/runs">Runs history</Link>
            </nav>
            {session ? (
              <div className="operator-session">
                <span>{session.role} · {session.operatorId}</span>
                <form action="/api/auth/logout" method="post">
                  <button type="submit" className="text-button">Sign out</button>
                </form>
              </div>
            ) : null}
            <span className="environment-badge">MOCK · SYNTHETIC DATA ONLY</span>
          </div>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}

