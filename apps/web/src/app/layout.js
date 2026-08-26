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
          <strong>SOAIACORE P0</strong>
          <span>MOCK · SYNTHETIC DATA ONLY</span>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}

