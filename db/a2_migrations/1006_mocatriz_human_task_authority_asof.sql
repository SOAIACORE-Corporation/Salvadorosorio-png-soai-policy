BEGIN;

-- SCN-034 / MOCATRIZ: bitemporal authority resolution.
-- A response may have been considered authoritative before later evidence revealed
-- that the Human Task had already been revoked/superseded/expired at response time.

CREATE OR REPLACE FUNCTION soa_memory.human_task_response_authority(
    p_project_scope text,
    p_human_task_id text,
    p_recorded_at timestamptz
)
RETURNS TABLE (
    response_id text,
    objective_id text,
    execution_id text,
    human_task_id text,
    correlation_id text,
    answer jsonb,
    received_time timestamptz,
    response_recorded_time timestamptz,
    authoritative boolean,
    invalidating_lifecycle_event_id text,
    invalidating_lifecycle_state text,
    invalidating_effective_time timestamptz,
    invalidating_recorded_time timestamptz
)
LANGUAGE sql
STABLE
AS $$
WITH response AS (
    SELECT r.*
    FROM soa_memory.human_task_responses r
    WHERE r.project_scope = p_project_scope
      AND r.human_task_id = p_human_task_id
      AND r.recorded_time <= p_recorded_at
    ORDER BY r.received_time DESC, r.recorded_time DESC
    LIMIT 1
)
SELECT
    r.response_id,
    r.objective_id,
    r.execution_id,
    r.human_task_id,
    r.correlation_id,
    r.answer,
    r.received_time,
    r.recorded_time AS response_recorded_time,
    (i.lifecycle_event_id IS NULL) AS authoritative,
    i.lifecycle_event_id AS invalidating_lifecycle_event_id,
    i.lifecycle_state AS invalidating_lifecycle_state,
    i.effective_time AS invalidating_effective_time,
    i.recorded_time AS invalidating_recorded_time
FROM response r
LEFT JOIN LATERAL (
    SELECT h.lifecycle_event_id, h.lifecycle_state, h.effective_time, h.recorded_time
    FROM soa_memory.human_task_lifecycle h
    WHERE h.project_scope = r.project_scope
      AND h.objective_id = r.objective_id
      AND h.execution_id = r.execution_id
      AND h.human_task_id = r.human_task_id
      AND h.correlation_id = r.correlation_id
      AND h.recorded_time <= p_recorded_at
      AND h.effective_time <= r.received_time
    ORDER BY h.recorded_time DESC, h.effective_time DESC
    LIMIT 1
) i ON TRUE;
$$;

COMMIT;
