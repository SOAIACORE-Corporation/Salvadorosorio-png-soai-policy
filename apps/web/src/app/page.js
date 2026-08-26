import Link from "next/link";

export default function HomePage() {
  return (
    <section>
      <p className="eyebrow">Architecture v0.6 · Provider mode MOCK</p>
      <h1>Application runtime pilot</h1>
      <p>
        This interface submits synthetic runs through the server-side Web BFF. It never
        connects to PostgreSQL, Blob Storage, or a model provider.
      </p>
      <Link className="button" href="/runs/new">Create a synthetic run</Link>
    </section>
  );
}

