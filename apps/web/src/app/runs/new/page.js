import { randomUUID } from "node:crypto";
import { coreRequest } from "../../../server/core-client.mjs";
import { profileFromCapsule, workflowPath } from "../../../server/operator-workflow.mjs";
import {
  createCapsule,
  createContext,
  createCorpus,
  createProject,
  createSyntheticRun,
} from "./actions";
import { SubmitButton } from "./submit-button";

export const dynamic = "force-dynamic";

const notices = {
  PROJECT_READY: "Project ready. Continue with a corpus.",
  CORPUS_READY: "Corpus ready. Continue with a context.",
  CONTEXT_READY: "Context ready. Create or select an immutable capsule.",
  CAPSULE_READY: "Capsule snapshot ready. You can now queue a MOCK run.",
};

const errors = {
  INVALID_PROJECT_NAME: "Enter a valid project name.",
  INVALID_CORPUS_NAME: "Enter a valid corpus name.",
  INVALID_CONTEXT_LABEL: "Enter a valid context label.",
  INVALID_CAPSULE_LABEL: "Enter a valid capsule label.",
  INVALID_REQUEST_TOKEN: "The form expired. Reload and try again.",
  CAPSULE_PROFILE_UNAVAILABLE: "The selected capsule has no usable analysis profile.",
  CORE_API_NOT_CONFIGURED: "Core is not configured for this Web environment.",
  CORE_REQUEST_FAILED: "Core could not complete the request.",
  REQUEST_FAILED: "The request could not be completed safely.",
};

function one(value) {
  return Array.isArray(value) ? value[0] : value;
}

function selected(items, field, requested) {
  return items.find((item) => item[field] === requested) ?? null;
}

function TechnicalId({ value }) {
  return <small className="technical">ID: {value}</small>;
}

function SelectionForm({ name, items, valueField, label, selectedValue, hidden = {} }) {
  return (
    <form className="compact-form" method="get">
      {Object.entries(hidden).map(([key, value]) => (
        <input key={key} type="hidden" name={key} value={value} />
      ))}
      <label>
        {label}
        <select name={name} defaultValue={selectedValue ?? ""} required>
          <option value="" disabled>Select an existing resource</option>
          {items.map((item) => (
            <option key={item[valueField]} value={item[valueField]}>
              {item.name ?? item.dimensions?.label ?? item.context_type ?? "Immutable snapshot"} — {item[valueField]}
            </option>
          ))}
        </select>
      </label>
      <SubmitButton pendingLabel="Selecting…">Use selection</SubmitButton>
    </form>
  );
}

function HiddenSelection({ values }) {
  return Object.entries(values).map(([name, value]) => (
    <input key={name} type="hidden" name={name} value={value} />
  ));
}

export default async function NewRunPage({ searchParams }) {
  const query = await searchParams;
  const requested = {
    project_id: one(query?.project_id),
    corpus_id: one(query?.corpus_id),
    context_id: one(query?.context_id),
    capsule_id: one(query?.capsule_id),
  };

  const [projects, profiles] = await Promise.all([
    coreRequest("/v1/projects?limit=100"),
    coreRequest("/v1/analysis-profiles?limit=100"),
  ]);
  const project = selected(projects, "project_id", requested.project_id);
  const corpora = project
    ? await coreRequest(`/v1/projects/${encodeURIComponent(project.project_id)}/corpora?limit=100`)
    : [];
  const corpus = selected(corpora, "corpus_id", requested.corpus_id);
  const contexts = corpus
    ? await coreRequest(
        `/v1/contexts?${new URLSearchParams({
          project_id: project.project_id,
          corpus_id: corpus.corpus_id,
          limit: "100",
        })}`,
      )
    : [];
  const context = selected(contexts, "context_id", requested.context_id);
  const capsules = context
    ? await coreRequest(
        `/v1/context-capsules?${new URLSearchParams({
          context_id: context.context_id,
          limit: "100",
        })}`,
      )
    : [];
  const capsule = selected(capsules, "context_capsule_id", requested.capsule_id);
  const capsuleDetail = capsule
    ? await coreRequest(`/v1/context-capsules/${encodeURIComponent(capsule.context_capsule_id)}`)
    : null;
  const capsuleProfile = profileFromCapsule(capsuleDetail);
  const activeSelection = {
    ...(project && { project_id: project.project_id }),
    ...(corpus && { corpus_id: corpus.corpus_id }),
    ...(context && { context_id: context.context_id }),
    ...(capsule && { capsule_id: capsule.context_capsule_id }),
  };
  const notice = notices[one(query?.notice)];
  const errorCode = one(query?.error);
  const error = errors[errorCode] ?? (errorCode ? errors.REQUEST_FAILED : null);

  return (
    <section>
      <p className="eyebrow">Internal operator · MOCK only · synthetic data</p>
      <h1>Prepare a run</h1>
      <p className="lede">
        Select existing resources or create synthetic ones. Technical identifiers remain
        visible for traceability, but you never need to copy or type them.
      </p>

      {notice && <p className="notice" role="status">{notice}</p>}
      {error && <p className="error" role="alert">{error}</p>}

      <ol className="workflow">
        <li className={project ? "complete" : "active"}>
          <div className="step-heading"><span>1</span><h2>Project</h2></div>
          {projects.length ? (
            <SelectionForm
              name="project_id"
              items={projects}
              valueField="project_id"
              label="Existing project"
              selectedValue={project?.project_id}
            />
          ) : <p className="empty">No projects yet. Create the first synthetic project.</p>}
          <details open={!projects.length}>
            <summary>Create project</summary>
            <form action={createProject}>
              <input type="hidden" name="request_token" value={randomUUID()} />
              <label>Project name<input name="name" maxLength={200} required /></label>
              <SubmitButton pendingLabel="Creating project…">Create project</SubmitButton>
            </form>
          </details>
          {project && <p className="selection">Selected: <strong>{project.name}</strong><TechnicalId value={project.project_id} /></p>}
        </li>

        <li className={corpus ? "complete" : project ? "active" : "locked"}>
          <div className="step-heading"><span>2</span><h2>Corpus</h2></div>
          {!project ? <p className="empty">Select a project to continue.</p> : (
            <>
              {corpora.length ? (
                <SelectionForm
                  name="corpus_id"
                  items={corpora}
                  valueField="corpus_id"
                  label="Existing corpus"
                  selectedValue={corpus?.corpus_id}
                  hidden={{ project_id: project.project_id }}
                />
              ) : <p className="empty">This project has no corpora yet.</p>}
              <details open={!corpora.length}>
                <summary>Create corpus</summary>
                <form action={createCorpus}>
                  <HiddenSelection values={{ project_id: project.project_id }} />
                  <input type="hidden" name="request_token" value={randomUUID()} />
                  <label>Corpus name<input name="name" maxLength={200} required /></label>
                  <SubmitButton pendingLabel="Creating corpus…">Create corpus</SubmitButton>
                </form>
              </details>
            </>
          )}
          {corpus && <p className="selection">Selected: <strong>{corpus.name}</strong><TechnicalId value={corpus.corpus_id} /></p>}
        </li>

        <li className={context ? "complete" : corpus ? "active" : "locked"}>
          <div className="step-heading"><span>3</span><h2>Context</h2></div>
          {!corpus ? <p className="empty">Select a corpus to continue.</p> : (
            <>
              {contexts.length ? (
                <SelectionForm
                  name="context_id"
                  items={contexts}
                  valueField="context_id"
                  label="Existing context"
                  selectedValue={context?.context_id}
                  hidden={{ project_id: project.project_id, corpus_id: corpus.corpus_id }}
                />
              ) : <p className="empty">This corpus has no contexts yet.</p>}
              <details open={!contexts.length}>
                <summary>Create context</summary>
                <form action={createContext}>
                  <HiddenSelection values={{ project_id: project.project_id, corpus_id: corpus.corpus_id }} />
                  <input type="hidden" name="request_token" value={randomUUID()} />
                  <label>Context label<input name="label" maxLength={200} required /></label>
                  <SubmitButton pendingLabel="Creating context…">Create context</SubmitButton>
                </form>
              </details>
            </>
          )}
          {context && <p className="selection">Selected: <strong>{context.dimensions?.label ?? context.context_type}</strong><TechnicalId value={context.context_id} /></p>}
        </li>

        <li className={capsule ? "complete" : context ? "active" : "locked"}>
          <div className="step-heading"><span>4</span><h2>Context capsule</h2></div>
          {!context ? <p className="empty">Select a context to continue.</p> : (
            <>
              {capsules.length ? (
                <SelectionForm
                  name="capsule_id"
                  items={capsules}
                  valueField="context_capsule_id"
                  label="Existing immutable snapshot"
                  selectedValue={capsule?.context_capsule_id}
                  hidden={{
                    project_id: project.project_id,
                    corpus_id: corpus.corpus_id,
                    context_id: context.context_id,
                  }}
                />
              ) : <p className="empty">This context has no capsule snapshots yet.</p>}
              <details open={!capsules.length}>
                <summary>Create immutable capsule</summary>
                {profiles.length ? (
                  <form action={createCapsule}>
                    <HiddenSelection values={{
                      project_id: project.project_id,
                      corpus_id: corpus.corpus_id,
                      context_id: context.context_id,
                    }} />
                    <input type="hidden" name="request_token" value={randomUUID()} />
                    <label>Snapshot label<input name="label" maxLength={200} required /></label>
                    <label>
                      Analysis profile
                      <select name="analysis_profile" required>
                        {profiles.map((profile) => (
                          <option
                            key={`${profile.analysis_profile_id}:${profile.version}`}
                            value={`${profile.analysis_profile_id}@${profile.version}`}
                          >
                            {profile.name ?? "Analysis profile"} — {profile.analysis_profile_id} v{profile.version}
                          </option>
                        ))}
                      </select>
                    </label>
                    <p className="hint">Creates synthetic identity and evidence references required by the runtime. The snapshot is immutable.</p>
                    <SubmitButton pendingLabel="Creating capsule…">Create capsule</SubmitButton>
                  </form>
                ) : <p className="error">No analysis profiles are available. Seed one through the approved Core workflow.</p>}
              </details>
            </>
          )}
          {capsule && <p className="selection">Selected immutable snapshot<TechnicalId value={capsule.context_capsule_id} /></p>}
        </li>

        <li className={capsule ? "active" : "locked"}>
          <div className="step-heading"><span>5</span><h2>Queue run</h2></div>
          {!capsule ? <p className="empty">Select a capsule to continue.</p> : capsuleProfile ? (
            <form action={createSyntheticRun}>
              <HiddenSelection values={activeSelection} />
              <input type="hidden" name="request_token" value={randomUUID()} />
              <p className="selection">
                Profile: <strong>{capsuleProfile.analysis_profile_id} v{capsuleProfile.analysis_profile_version}</strong>
              </p>
              <label>Purpose<input name="purpose" defaultValue="P1_INTERNAL_OPERATOR" maxLength={200} required /></label>
              <SubmitButton pendingLabel="Queueing run…">Queue MOCK run</SubmitButton>
            </form>
          ) : <p className="error">This capsule cannot be queued because its profile metadata is unavailable.</p>}
        </li>
      </ol>
      <p className="reset"><a href={workflowPath()}>Start over</a></p>
    </section>
  );
}
