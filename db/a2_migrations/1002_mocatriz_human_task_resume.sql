BEGIN;

-- MOCATRIZ durable Human Task persistence.
-- Append-only overlay; intended for dedicated A2 databases and ephemeral CI validation.

CREATE TABLE soa_memory.human_tasks (
    human_task_id text PRIMARY KEY,
    objective_id text NOT NULL CHECK (btrim(objective_id) <> ''),
    execution_id text NOT NULL CHECK (btrim(execution_id) <> ''),
    correlation_id text NOT NULL CHECK (btrim(correlation_id) <> ''),
    project_scope text NOT NULL CHECK (btrim(project_scope) <> ''),
    status text NOT NULL DEFAULT 'WAITING_HUMAN' CHECK (status = 'WAITING_HUMAN'),
    reason text NOT NULL CHECK (btrim(reason) <> ''),
    question text NOT NULL CHECK (btrim(question) <> ''),
    evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    resume_from text NOT NULL CHECK (btrim(resume_from) <> ''),
    observed_time timestamptz NOT NULL,
    recorded_time timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (objective_id, execution_id, human_task_id, correlation_id)
);

CREATE TABLE soa_memory.human_task_responses (
    response_id text PRIMARY KEY,
    objective_id text NOT NULL,
    execution_id text NOT NULL,
    human_task_id text NOT NULL,
    correlation_id text NOT NULL,
    project_scope text NOT NULL CHECK (btrim(project_scope) <> ''),
    answer jsonb NOT NULL,
    received_time timestamptz NOT NULL,
    recorded_time timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    FOREIGN KEY (objective_id, execution_id, human_task_id, correlation_id)
      REFERENCES soa_memory.human_tasks(objective_id, execution_id, human_task_id, correlation_id)
);

CREATE INDEX idx_a2_human_tasks_scope
    ON soa_memory.human_tasks(project_scope, objective_id, execution_id, human_task_id);

CREATE INDEX idx_a2_human_task_responses_scope
    ON soa_memory.human_task_responses(project_scope, human_task_id, received_time DESC);

CREATE TRIGGER trg_a2_human_tasks_append_only
    BEFORE UPDATE OR DELETE ON soa_memory.human_tasks
    FOR EACH ROW EXECUTE FUNCTION soa_memory.reject_history_mutation();

CREATE TRIGGER trg_a2_human_task_responses_append_only
    BEFORE UPDATE OR DELETE ON soa_memory.human_task_responses
    FOR EACH ROW EXECUTE FUNCTION soa_memory.reject_history_mutation();

COMMIT;
