BEGIN;

-- SCN-032 / MOCATRIZ: correlation correctness is not enough if authority is stale.
-- Human Task lifecycle is append-only. Terminal lifecycle events invalidate later
-- responses without rewriting the original WAITING_HUMAN task.

CREATE TABLE soa_memory.human_task_lifecycle (
    lifecycle_event_id text PRIMARY KEY,
    objective_id text NOT NULL,
    execution_id text NOT NULL,
    human_task_id text NOT NULL,
    correlation_id text NOT NULL,
    project_scope text NOT NULL CHECK (btrim(project_scope) <> ''),
    lifecycle_state text NOT NULL CHECK (lifecycle_state IN ('REVOKED','SUPERSEDED','EXPIRED')),
    effective_time timestamptz NOT NULL,
    recorded_time timestamptz NOT NULL DEFAULT now(),
    reason text NOT NULL CHECK (btrim(reason) <> ''),
    FOREIGN KEY (objective_id, execution_id, human_task_id, correlation_id)
      REFERENCES soa_memory.human_tasks(objective_id, execution_id, human_task_id, correlation_id)
);

CREATE INDEX idx_a2_human_task_lifecycle_scope
    ON soa_memory.human_task_lifecycle(
      project_scope, human_task_id, effective_time DESC, recorded_time DESC
    );

CREATE TRIGGER trg_a2_human_task_lifecycle_append_only
    BEFORE UPDATE OR DELETE ON soa_memory.human_task_lifecycle
    FOR EACH ROW EXECUTE FUNCTION soa_memory.reject_history_mutation();

CREATE OR REPLACE FUNCTION soa_memory.reject_stale_human_response()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM soa_memory.human_task_lifecycle htl
        WHERE htl.project_scope = NEW.project_scope
          AND htl.objective_id = NEW.objective_id
          AND htl.execution_id = NEW.execution_id
          AND htl.human_task_id = NEW.human_task_id
          AND htl.correlation_id = NEW.correlation_id
          AND htl.lifecycle_state IN ('REVOKED','SUPERSEDED','EXPIRED')
          AND htl.effective_time <= NEW.received_time
    ) THEN
        RAISE EXCEPTION 'STALE_HUMAN_AUTHORITY: Human Task is no longer active at response time';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_a2_reject_stale_human_response
    BEFORE INSERT ON soa_memory.human_task_responses
    FOR EACH ROW EXECUTE FUNCTION soa_memory.reject_stale_human_response();

COMMIT;
