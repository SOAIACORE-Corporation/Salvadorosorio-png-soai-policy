import "./styles.css";

export const metadata = {
  title: "SOAIACORE Operator",
  description: "Synthetic-only SOAIACORE internal operator workflow",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <header>
          <strong>SOAIACORE</strong>
          <span>MOCK · SYNTHETIC DATA ONLY</span>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}

