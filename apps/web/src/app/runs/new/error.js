"use client";

export default function NewRunError({ reset }) {
  return (
    <section>
      <p className="eyebrow">Internal operator</p>
      <h1>Workflow unavailable</h1>
      <p className="error" role="alert">
        The workflow could not load safely. No credentials or internal response details were exposed.
      </p>
      <button onClick={() => reset()}>Try again</button>
    </section>
  );
}
