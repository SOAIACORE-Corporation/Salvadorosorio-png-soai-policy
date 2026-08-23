import { createSyntheticRun } from "./actions";

export default function NewRunPage() {
  return (
    <section>
      <p className="eyebrow">Synthetic input only</p>
      <h1>Create run</h1>
      <form action={createSyntheticRun}>
        <label>
          Context Capsule ID
          <input name="context_capsule_id" required pattern="cap_[A-Za-z0-9_-]+" />
        </label>
        <label>
          Analysis Profile ID
          <input name="analysis_profile_id" required pattern="AP-[0-9]{3}" />
        </label>
        <label>
          Analysis Profile version
          <input name="analysis_profile_version" required />
        </label>
        <label>
          Purpose
          <input name="purpose" defaultValue="P0_SYNTHETIC_WEB" required />
        </label>
        <button type="submit">Queue MOCK run</button>
      </form>
    </section>
  );
}

