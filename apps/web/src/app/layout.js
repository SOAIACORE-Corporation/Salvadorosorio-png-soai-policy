import Link from "next/link";
import "./styles.css";

export const metadata = {
  title: "SOAIACORE P0",
  description: "Synthetic-only SOAIACORE P0 runtime pilot",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="header-inner">
            <Link className="brand" href="/">SOAIACORE P0</Link>
            <nav aria-label="Primary navigation">
              <Link href="/">Portal</Link>
              <Link href="/workflow">Operator workflow</Link>
            </nav>
            <span className="environment-badge">MOCK · SYNTHETIC DATA ONLY</span>
          </div>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}

