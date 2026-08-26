export default function WorkflowLoading() {
  return (
    <section className="workflow-shell" aria-busy="true">
      <p className="eyebrow">Internal operator · MOCK only</p>
      <h1>Loading workflow…</h1>
      <div className="loading-panel">Reading available projects and analysis profiles.</div>
    </section>
  );
}
