"use client";

import { useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

const EMPTY_SELECTION = {
  projectId: "",
  corpusId: "",
  contextId: "",
  capsuleId: "",
};

function requestId() {
  return globalThis.crypto?.randomUUID?.() ?? `request-${Date.now()}`;
}

function selectedProfileKey(profile) {
  return profile ? `${profile.analysis_profile_id}::${profile.version}` : "";
}

function technicalId(label, value) {
  if (!value) return null;
  return <small className="technical-id">{label}: <code>{value}</code></small>;
}

export default function OperatorWorkflow({ initialData }) {
  const router = useRouter();
  const [data, setData] = useState(initialData);
  const [selection, setSelection] = useState(EMPTY_SELECTION);
  const [profileKey, setProfileKey] = useState(selectedProfileKey(initialData.profiles[0]));
  const [purpose, setPurpose] = useState("P1_SYNTHETIC_WEB");
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState(null);
  const operationKeys = useRef(new Map());

  const project = data.projects.find((item) => item.project_id === selection.projectId);
  const corpus = data.corpora.find((item) => item.corpus_id === selection.corpusId);
  const context = data.contexts.find((item) => item.context_id === selection.contextId);
  const capsule = data.capsules.find(
    (item) => item.context_capsule_id === selection.capsuleId,
  );
  const profile = useMemo(
    () => data.profiles.find((item) => selectedProfileKey(item) === profileKey),
    [data.profiles, profileKey],
  );

  async function readSnapshot(nextSelection) {
    setBusy("loading");
    setNotice(null);
    const query = new URLSearchParams();
    if (nextSelection.projectId) query.set("project_id", nextSelection.projectId);
    if (nextSelection.corpusId) query.set("corpus_id", nextSelection.corpusId);
    if (nextSelection.contextId) query.set("context_id", nextSelection.contextId);
    if (nextSelection.capsuleId) {
      query.set("context_capsule_id", nextSelection.capsuleId);
    }
    try {
      const response = await fetch(`/api/operator/workflow?${query}`, {
        cache: "no-store",
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.error?.message ?? "Unable to load workflow.");
      setData(payload);
      setSelection(nextSelection);
      const capsuleProfile = payload.selectedCapsule?.payload;
      if (capsuleProfile?.analysis_profile_id && capsuleProfile?.analysis_profile_version) {
        setProfileKey(
          `${capsuleProfile.analysis_profile_id}::${capsuleProfile.analysis_profile_version}`,
        );
      }
      return payload;
    } catch (error) {
      setNotice({ type: "error", text: error.message });
      return null;
    } finally {
      setBusy("");
    }
  }

  async function submitAction(action, values) {
    const fingerprint = JSON.stringify(values);
    const existing = operationKeys.current.get(action);
    const key = existing?.fingerprint === fingerprint ? existing.key : requestId();
    operationKeys.current.set(action, { fingerprint, key });
    setBusy(action);
    setNotice(null);
    try {
      const response = await fetch("/api/operator/workflow", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, request_id: key, values }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.error?.message ?? "The operation failed.");
      operationKeys.current.delete(action);
      const replayed = payload.idempotencyReplayed ? " Replayed safely." : "";
      const successNotice = { type: "success", text: `Saved successfully.${replayed}` };
      const resource = payload.resource;
      if (action === "create_run") {
        router.push(`/runs/${encodeURIComponent(resource.run_id)}`);
        return;
      }
      const nextSelection = { ...selection };
      if (action === "create_project") {
        Object.assign(nextSelection, {
          projectId: resource.project_id,
          corpusId: "",
          contextId: "",
          capsuleId: "",
        });
      } else if (action === "create_corpus") {
        Object.assign(nextSelection, {
          corpusId: resource.corpus_id,
          contextId: "",
          capsuleId: "",
        });
      } else if (action === "create_context") {
        Object.assign(nextSelection, {
          contextId: resource.context_id,
          capsuleId: "",
        });
      } else if (action === "create_capsule") {
        nextSelection.capsuleId = resource.context_capsule_id;
      }
      const refreshed = await readSnapshot(nextSelection);
      if (refreshed) setNotice(successNotice);
    } catch (error) {
      setNotice({ type: "error", text: error.message });
    } finally {
      setBusy("");
    }
  }

  const disabled = Boolean(busy);
  const profileParts = profileKey.split("::");

  return (
    <div className="operator-workflow" aria-busy={disabled}>
      {notice ? <div className={`notice ${notice.type}`} role={notice.type === "error" ? "alert" : "status"}>{notice.text}</div> : null}

      <ol className="workflow-steps">
        <li className="workflow-card">
          <div className="step-heading"><span>1</span><div><h2>Project</h2><p>Choose an existing project or create a synthetic one.</p></div></div>
          <label>
            Existing project
            <select
              value={selection.projectId}
              disabled={disabled}
              onChange={(event) => readSnapshot({
                projectId: event.target.value,
                corpusId: "",
                contextId: "",
                capsuleId: "",
              })}
            >
              <option value="">Select a project</option>
              {data.projects.map((item) => <option key={item.project_id} value={item.project_id}>{item.name}</option>)}
            </select>
          </label>
          {technicalId("Project ID", project?.project_id)}
          {data.projects.length === 0 ? <p className="empty-state">No projects exist yet. Create the first synthetic project.</p> : null}
          <form onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); submitAction("create_project", { name: form.get("name") }); }}>
            <label>New project name<input name="name" maxLength={200} required disabled={disabled} /></label>
            <button type="submit" disabled={disabled}>{busy === "create_project" ? "Creating…" : "Create project"}</button>
          </form>
        </li>

        <li className="workflow-card">
          <div className="step-heading"><span>2</span><div><h2>Corpus</h2><p>Scope the synthetic material inside the selected project.</p></div></div>
          <label>
            Existing corpus
            <select
              value={selection.corpusId}
              disabled={disabled || !selection.projectId}
              onChange={(event) => readSnapshot({ ...selection, corpusId: event.target.value, contextId: "", capsuleId: "" })}
            >
              <option value="">Select a corpus</option>
              {data.corpora.map((item) => <option key={item.corpus_id} value={item.corpus_id}>{item.name}</option>)}
            </select>
          </label>
          {technicalId("Corpus ID", corpus?.corpus_id)}
          {selection.projectId && data.corpora.length === 0 ? <p className="empty-state">This project has no corpora yet.</p> : null}
          <form onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); submitAction("create_corpus", { project_id: selection.projectId, name: form.get("name") }); }}>
            <label>New corpus name<input name="name" maxLength={200} required disabled={disabled || !selection.projectId} /></label>
            <button type="submit" disabled={disabled || !selection.projectId}>{busy === "create_corpus" ? "Creating…" : "Create corpus"}</button>
          </form>
        </li>

        <li className="workflow-card">
          <div className="step-heading"><span>3</span><div><h2>Context</h2><p>Describe the bounded synthetic context for this corpus.</p></div></div>
          <label>
            Existing context
            <select
              value={selection.contextId}
              disabled={disabled || !selection.corpusId}
              onChange={(event) => readSnapshot({ ...selection, contextId: event.target.value, capsuleId: "" })}
            >
              <option value="">Select a context</option>
              {data.contexts.map((item) => <option key={item.context_id} value={item.context_id}>{item.dimensions?.label ?? item.context_type}</option>)}
            </select>
          </label>
          {technicalId("Context ID", context?.context_id)}
          {selection.corpusId && data.contexts.length === 0 ? <p className="empty-state">This corpus has no contexts yet.</p> : null}
          <form onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); submitAction("create_context", { project_id: selection.projectId, corpus_id: selection.corpusId, label: form.get("label") }); }}>
            <label>New context label<input name="label" maxLength={200} required disabled={disabled || !selection.corpusId} /></label>
            <button type="submit" disabled={disabled || !selection.corpusId}>{busy === "create_context" ? "Creating…" : "Create context"}</button>
          </form>
        </li>

        <li className="workflow-card">
          <div className="step-heading"><span>4</span><div><h2>Context capsule</h2><p>Select an immutable snapshot or create a new one.</p></div></div>
          <div className="immutability-note"><strong>Immutable snapshot</strong><span>Changing context or profile data creates a new capsule; existing capsules are never edited.</span></div>
          <label>
            Existing capsule
            <select
              value={selection.capsuleId}
              disabled={disabled || !selection.contextId}
              onChange={(event) => readSnapshot({ ...selection, capsuleId: event.target.value })}
            >
              <option value="">Select a capsule</option>
              {data.capsules.map((item) => <option key={item.context_capsule_id} value={item.context_capsule_id}>Snapshot · {item.created_at ?? item.schema_version}</option>)}
            </select>
          </label>
          {technicalId("Capsule ID", capsule?.context_capsule_id)}
          {capsule ? technicalId("Input hash", capsule.input_hash) : null}
          {profile ? <small className="technical-id">New snapshots bind the profile <strong>{profile.name ?? profile.analysis_profile_id}</strong> selected in step 5.</small> : null}
          {selection.contextId && data.capsules.length === 0 ? <p className="empty-state">No snapshots exist for this context.</p> : null}
          <button
            type="button"
            disabled={disabled || !selection.contextId || !profile}
            onClick={() => submitAction("create_capsule", {
              project_id: selection.projectId,
              corpus_id: selection.corpusId,
              context_id: selection.contextId,
              analysis_profile_id: profile?.analysis_profile_id,
              analysis_profile_version: profile?.version,
              purpose,
            })}
          >
            {busy === "create_capsule" ? "Creating snapshot…" : "Create new immutable capsule"}
          </button>
        </li>

        <li className="workflow-card">
          <div className="step-heading"><span>5</span><div><h2>Analysis profile</h2><p>Choose the approved profile bound to this run.</p></div></div>
          <label>
            Analysis profile
            <select value={profileKey} disabled={disabled || data.profiles.length === 0} onChange={(event) => setProfileKey(event.target.value)}>
              {data.profiles.length === 0 ? <option value="">No profiles available</option> : null}
              {data.profiles.map((item) => <option key={selectedProfileKey(item)} value={selectedProfileKey(item)}>{item.name ?? item.analysis_profile_id} · {item.version}</option>)}
            </select>
          </label>
          {profile ? technicalId("Profile ID", `${profile.analysis_profile_id} · ${profile.version}`) : null}
          {data.profiles.length === 0 ? <p className="empty-state">An approved AnalysisProfile must exist before a capsule or run can be created.</p> : null}
          {data.selectedCapsule && profile && (
            data.selectedCapsule.payload?.analysis_profile_id !== profile.analysis_profile_id ||
            data.selectedCapsule.payload?.analysis_profile_version !== profile.version
          ) ? <p className="validation-state">This profile differs from the immutable capsule. Create a new capsule before running.</p> : null}
        </li>

        <li className="workflow-card final-step">
          <div className="step-heading"><span>6</span><div><h2>Run</h2><p>Queue the selected snapshot through the deterministic MOCK fixture.</p></div></div>
          <label>Purpose<input value={purpose} maxLength={200} required disabled={disabled} onChange={(event) => setPurpose(event.target.value)} /></label>
          <dl className="run-summary">
            <dt>Project</dt><dd>{project?.name ?? "Not selected"}</dd>
            <dt>Corpus</dt><dd>{corpus?.name ?? "Not selected"}</dd>
            <dt>Context</dt><dd>{context?.dimensions?.label ?? "Not selected"}</dd>
            <dt>Capsule</dt><dd>{capsule ? "Immutable snapshot selected" : "Not selected"}</dd>
            <dt>Profile</dt><dd>{profile?.name ?? "Not selected"}</dd>
            <dt>Mode</dt><dd>MOCK · documented-observation</dd>
          </dl>
          <button
            className="primary-action"
            type="button"
            disabled={disabled || !capsule || !profile || !purpose.trim()}
            onClick={() => submitAction("create_run", {
              context_capsule_id: selection.capsuleId,
              analysis_profile_id: profileParts[0],
              analysis_profile_version: profileParts[1],
              purpose,
            })}
          >
            {busy === "create_run" ? "Queuing…" : "Queue MOCK run"}
          </button>
        </li>
      </ol>
    </div>
  );
}
