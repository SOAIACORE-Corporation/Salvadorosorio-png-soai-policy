import Link from "next/link";

export default function HomePage() {
  return (
    <section className="portal-home">
      <div className="portal-hero">
        <div>
          <p className="eyebrow">Architecture v0.6 · Operator portal</p>
          <h1>Run a bounded synthetic analysis.</h1>
          <p className="hero-copy">
            Prepare the approved context, validate the run, and inspect its receipt from one
            guided workflow. Every action stays inside the server-side Web BFF.
          </p>
          <div className="hero-actions">
            <Link className="button primary-action" href="/workflow">Open operator workflow</Link>
            <Link className="text-link" href="/workflow#workflow-steps">See the three-stage flow</Link>
          </div>
        </div>
        <aside className="portal-status-card" aria-label="Runtime status">
          <p className="eyebrow">Runtime status</p>
          <strong>READY · MOCK</strong>
          <dl>
            <dt>Data</dt><dd>Synthetic only</dd>
            <dt>Provider</dt><dd>Server-side BFF</dd>
            <dt>Cloud writes</dt><dd>Disabled</dd>
          </dl>
        </aside>
      </div>

      <div className="portal-grid" aria-label="Operator workflow overview">
        <article className="portal-card">
          <span className="card-number">01</span>
          <h2>Prepare</h2>
          <p>Select the project, corpus, context and immutable capsule for the run.</p>
        </article>
        <article className="portal-card">
          <span className="card-number">02</span>
          <h2>Validate</h2>
          <p>Choose the approved analysis profile and confirm the pre-run guardrails.</p>
        </article>
        <article className="portal-card">
          <span className="card-number">03</span>
          <h2>Inspect</h2>
          <p>Follow status updates and open the terminal ContextReceipt when ready.</p>
        </article>
      </div>

      <div className="guardrail-banner" role="note">
        <strong>Safe by design.</strong> This pilot does not connect to production data, Azure,
        Blob Storage, or an external model provider.
      </div>
    </section>
  );
}

