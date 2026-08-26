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
        <header>
          <Link className="brand" href="/">SOAIACORE P0</Link>
          <span>MOCK · SYNTHETIC DATA ONLY</span>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}

