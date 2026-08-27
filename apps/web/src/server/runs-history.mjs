import { CoreApiError, coreRequest } from "./core-client.mjs";

const STATUS_VALUES = new Set([
  "QUEUED", "RUNNING", "COMPLETED", "REVIEW_REQUIRED", "DENIED",
  "FAILED_PRECHECK", "FAILED_EXECUTION", "FAILED_VALIDATION", "FAILED_RECEIPT",
]);
const MAX_LIMIT = 25;

export class RunsHistoryValidationError extends Error {
  constructor(message = "The run history filter is invalid.") {
    super(message);
    this.name = "RunsHistoryValidationError";
    this.code = "RUN_HISTORY_FILTER_INVALID";
    this.status = 400;
  }
}

function safeText(value) { return typeof value === "string" ? value : null; }
function safeId(value) {
  const text = String(value ?? "").trim();
  if (!text || text.length > 200 || !/^[A-Za-z0-9_.:-]+$/.test(text)) throw new RunsHistoryValidationError();
  return text;
}
function isTerminal(status) { return ["COMPLETED", "REVIEW_REQUIRED", "DENIED", "FAILED_PRECHECK", "FAILED_EXECUTION", "FAILED_VALIDATION", "FAILED_RECEIPT"].includes(status); }

export async function loadRunsHistory(
  { status = "", projectId = "", profileId = "", limit = 25 } = {},
  { coreRequestImpl = coreRequest } = {},
) {
  const normalizedStatus = String(status ?? "").trim();
  if (normalizedStatus && !STATUS_VALUES.has(normalizedStatus)) throw new RunsHistoryValidationError("The run status filter is invalid.");
  const normalizedProject = projectId ? safeId(projectId) : "";
  const normalizedProfile = profileId ? safeId(profileId) : "";
  const boundedLimit = Math.min(Math.max(Number.parseInt(limit, 10) || MAX_LIMIT, 1), MAX_LIMIT);
  const query = new URLSearchParams({ limit: String(boundedLimit) });
  if (normalizedStatus) query.set("status", normalizedStatus);
  if (normalizedProject) query.set("project_id", normalizedProject);

  const [runs, projects, profiles] = await Promise.all([
    coreRequestImpl(`/v1/runs?${query}`),
    coreRequestImpl("/v1/projects?limit=100"),
    coreRequestImpl("/v1/analysis-profiles?limit=100"),
  ]);
  const filteredRuns = normalizedProfile
    ? runs.filter((run) => run.analysis_profile_id === normalizedProfile)
    : runs;
  const enriched = await Promise.all(filteredRuns.map(async (run) => {
    const detail = await coreRequestImpl(`/v1/runs/${encodeURIComponent(run.run_id)}`);
    let receipt = null;
    if (isTerminal(detail.status)) {
      try { receipt = await coreRequestImpl(`/v1/runs/${encodeURIComponent(run.run_id)}/receipt`); } catch (error) { if (!(error instanceof CoreApiError)) throw error; }
    }
    return {
      run_id: safeText(detail.run_id ?? run.run_id),
      status: safeText(detail.status ?? run.status),
      job_status: safeText(detail.job_status),
      project_id: safeText(detail.project_id ?? run.project_id),
      context_capsule_id: safeText(detail.context_capsule_id ?? run.context_capsule_id),
      analysis_profile_id: safeText(detail.analysis_profile_id ?? run.analysis_profile_id),
      analysis_profile_version: safeText(detail.analysis_profile_version ?? run.analysis_profile_version),
      mode: safeText(detail.mode ?? run.mode),
      started_at: safeText(detail.started_at ?? run.started_at),
      completed_at: safeText(detail.completed_at ?? run.completed_at),
      attempts: typeof detail.attempts === "number" ? detail.attempts : null,
      output_status: safeText(receipt?.output_status),
      review_mode: safeText(receipt?.review_mode),
    };
  }));
  return {
    runs: enriched,
    filters: {
      projects: projects.map((item) => ({ project_id: safeText(item.project_id), name: safeText(item.name) })),
      profiles: profiles.map((item) => ({ analysis_profile_id: safeText(item.analysis_profile_id), version: safeText(item.version), name: safeText(item.name) })),
    },
  };
}

export function publicRunsHistoryError(error) {
  if (error instanceof RunsHistoryValidationError) return { status: error.status, error: { code: error.code, message: error.message } };
  if (error instanceof CoreApiError) {
    const status = error.status >= 400 && error.status < 500 ? error.status : 502;
    return { status, error: { code: status === 502 ? "RUN_HISTORY_UNAVAILABLE" : error.code, message: status === 502 ? "The Core service is temporarily unavailable." : error.message } };
  }
  return { status: 500, error: { code: "RUN_HISTORY_FAILED", message: "The run history could not be loaded." } };
}
