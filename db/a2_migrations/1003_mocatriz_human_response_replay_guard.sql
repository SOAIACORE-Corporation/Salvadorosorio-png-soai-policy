BEGIN;

-- SCN-031 / MOCATRIZ: prevent replay or conflicting authoritative responses.
-- A Human Task is immutable and accepts exactly one authoritative response.
-- A changed human decision must be represented by a new task/decision event,
-- never by silently replacing the response used for resume.

CREATE UNIQUE INDEX uq_a2_human_task_single_authoritative_response
    ON soa_memory.human_task_responses(
      objective_id,
      execution_id,
      human_task_id,
      correlation_id
    );

COMMIT;
