"use client";

export default function WorkflowError({ reset }) {
  return (
    <section className="workflow-shell">
      <p className="eyebrow">Operator workflow unavailable</p>
      <h1>We could not load the workflow.</h1>
      <p>The Core service may be temporarily unavailable. No data was submitted.</p>
      <button type="button" onClick={() => reset()}>Try again</button>
    </section>
  );
}
