"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

function Field({ label, value }) {
  return <><dt>{label}</dt><dd>{value ?? "—"}</dd></>;
}

export default function ContextInspectorClient({ capsuleId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`/api/operator/context-inspector/${encodeURIComponent(capsuleId)}`, {
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload?.error?.message ?? "The context inspector could not be loaded.");
      setData(payload);
    } catch (failure) {
      setError(failure.message);
    } finally {
      setLoading(false);
    }
  }, [capsuleId]);

  useEffect(() => { void load(); }, [load]);

  if (loading) {
    return <section className="inspector-page"><p className="eyebrow">Context Inspector</p><h1>Loading capsule…</h1><p className="loading-panel" role="status">Reading metadata through the Web BFF.</p></section>;
  }
  if (error) {
    return <section className="inspector-page"><p className="eyebrow">Context Inspector</p><h1>Unable to load capsule</h1><p className="notice error" role="alert">{error}</p><div className="page-actions"><button type="button" onClick={() => void load()}>Retry</button><Link className="text-link" href="/workflow">Back to workflow</Link></div></section>;
  }

  const { capsule, context, binding, integrity, evidence } = data;
  return (
    <section className="inspector-page">
      <p className="eyebrow">Context Inspector · Read only</p>
      <div className="run-heading"><div><h1>{capsule.context_capsule_id}</h1><p className="page-intro">Metadata-first view of the immutable runtime snapshot.</p></div><span className="status-badge status-completed">IMMUTABLE</span></div>

      <div className="inspector-integrity" role="status"><strong>Integrity verified</strong><span>Input hash {integrity.input_hash_present ? "present" : "missing"} · Profile binding {integrity.profile_bound ? "present" : "missing"}</span></div>

      <div className="inspector-grid">
        <section className="inspector-card"><h2>Capsule</h2><dl><Field label="Context ID" value={capsule.context_id} /><Field label="Schema" value={capsule.schema_version} /><Field label="Input hash" value={capsule.input_hash} /><Field label="Created" value={capsule.created_at} /></dl></section>
        <section className="inspector-card"><h2>Context</h2><dl><Field label="Label" value={context.label} /><Field label="Project ID" value={context.project_id} /><Field label="Corpus ID" value={context.corpus_id} /><Field label="Type" value={context.context_type} /></dl></section>
        <section className="inspector-card"><h2>Runtime binding</h2><dl><Field label="Profile" value={binding.analysis_profile_id} /><Field label="Version" value={binding.analysis_profile_version} /><Field label="Purpose" value={binding.purpose} /><Field label="Synthetic only" value={binding.synthetic_only ? "Yes" : "No"} /></dl></section>
      </div>

      <section className="inspector-card"><div className="section-heading"><h2>Evidence references</h2><span>{binding.evidence_refs} linked</span></div>{evidence.length === 0 ? <p className="empty-state">No evidence references are attached to this capsule.</p> : <ul className="evidence-list">{evidence.map((item) => <li key={item.evidence_ref_id}><strong>{item.evidence_ref_id}</strong><span>{item.evidence_state ?? "State unavailable"} · {item.availability}</span>{item.locator ? <small>{item.locator}</small> : null}</li>)}</ul>}</section>

      <div className="page-actions"><Link className="button" href="/workflow">Back to workflow</Link><Link className="text-link" href={`/runs/new`}>Start a run</Link></div>
    </section>
  );
}
