"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

function Field({ label, value }) { return <><dt>{label}</dt><dd>{value ?? "—"}</dd></>; }

export default function EvidenceExplorerClient({ evidenceRefId, claimId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const query = claimId ? `?claim_id=${encodeURIComponent(claimId)}` : "";
      const response = await fetch(`/api/operator/evidence/${encodeURIComponent(evidenceRefId)}${query}`, { cache: "no-store", headers: { Accept: "application/json" } });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload?.error?.message ?? "The evidence explorer could not be loaded.");
      setData(payload);
    } catch (failure) { setError(failure.message); } finally { setLoading(false); }
  }, [claimId, evidenceRefId]);
  useEffect(() => { void load(); }, [load]);

  if (loading) return <section className="inspector-page"><p className="eyebrow">Evidence Explorer</p><h1>Loading evidence…</h1><p className="loading-panel" role="status">Reading canonical metadata through the Web BFF.</p></section>;
  if (error) return <section className="inspector-page"><p className="eyebrow">Evidence Explorer</p><h1>Unable to load evidence</h1><p className="notice error" role="alert">{error}</p><div className="page-actions"><button type="button" onClick={() => void load()}>Retry</button><Link className="text-link" href="/workflow">Back to workflow</Link></div></section>;

  const { evidence_reference: reference, evidence_object: object, source_artifact: source, content, claim } = data;
  return <section className="inspector-page evidence-page">
    <p className="eyebrow">Evidence Explorer · Metadata first</p>
    <div className="run-heading"><div><h1>{reference.evidence_ref_id}</h1><p className="page-intro">Canonical evidence lineage without raw Blob content.</p></div><span className="status-badge status-completed">{object.evidence_state ?? "STATE UNKNOWN"}</span></div>
    <div className="inspector-integrity"><strong>Fixity and admissibility</strong><span>Content availability: {content.availability} · Raw Blob access: {content.raw_blob_access}</span></div>
    <div className="inspector-grid evidence-grid">
      <section className="inspector-card"><h2>EvidenceReference</h2><dl><Field label="Locator" value={reference.locator} /><Field label="Support" value={reference.support_type} /><Field label="Relationship" value={reference.relationship} /><Field label="State snapshot" value={reference.evidence_state_snapshot} /><Field label="Admissibility" value={reference.admissibility_scope} /><Field label="Excerpt hash" value={reference.excerpt_hash} /><Field label="Provenance" value={reference.provenance_chain_ref} /></dl></section>
      <section className="inspector-card"><h2>EvidenceObject</h2><dl><Field label="Object ID" value={object.evidence_id} /><Field label="State" value={object.evidence_state} /><Field label="Modality" value={object.modality} /><Field label="Content SHA-256" value={object.content_sha256} /><Field label="Object locator" value={object.object_locator} /></dl></section>
      <section className="inspector-card"><h2>SourceArtifact</h2><dl><Field label="Source ID" value={source.source_id} /><Field label="Type" value={source.source_type} /><Field label="Locator" value={source.source_locator} /><Field label="Corpus ID" value={source.corpus_id} /><Field label="Bytes" value={source.byte_size} /></dl></section>
    </div>
    <section className="inspector-card"><div className="section-heading"><h2>Claim linkage</h2><span>{claim ? claim.role : "Not supplied"}</span></div>{claim ? <dl><Field label="Claim ID" value={claim.claim_id} /><Field label="Statement" value={claim.statement} /><Field label="Kind" value={claim.claim_kind} /><Field label="Epistemic class" value={claim.epistemic_class} /><Field label="Status" value={claim.status} /></dl> : <p className="empty-state">No claim was supplied for this navigation. Open this view from a claim to verify supporting or contradicting linkage.</p>}</section>
    <div className="page-actions"><Link className="button" href="/workflow">Back to workflow</Link></div>
    <p className="guardrail-banner"><strong>P0 physical reality:</strong> the currently evidenced Blob footprint is one evidence container; AI Workspace separation remains logical.</p>
  </section>;
}
