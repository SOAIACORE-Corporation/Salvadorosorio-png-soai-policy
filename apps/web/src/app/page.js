import Link from "next/link";

export default function HomePage() {
  return (
    <section>
      <p className="eyebrow">Architecture v0.6 · Internal operator · MOCK</p>
      <h1>SOAIACORE operator workflow</h1>
      <p>
        Prepare projects, corpora, contexts, immutable capsules, and synthetic runs through
        the server-side Web BFF. The browser never connects directly to Core, PostgreSQL,
        Blob Storage, or a model provider.
      </p>
      <Link className="button" href="/runs/new">Prepare a synthetic run</Link>
    </section>
  );
}

