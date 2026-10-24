BEGIN;

-- SCN-033 / MOCATRIZ: project_scope is part of authority correlation.
-- Four-part task identity is insufficient if a response or lifecycle event can
-- claim another project scope.

CREATE UNIQUE INDEX uq_a2_human_task_project_scope_correlation
    ON soa_memory.human_tasks(
      project_scope,
      objective_id,
      execution_id,
      human_task_id,
      correlation_id
    );

ALTER TABLE soa_memory.human_task_responses
    ADD CONSTRAINT fk_a2_human_response_project_scope
    FOREIGN KEY (
      project_scope,
      objective_id,
      execution_id,
      human_task_id,
      correlation_id
    )
    REFERENCES soa_memory.human_tasks(
      project_scope,
      objective_id,
      execution_id,
      human_task_id,
      correlation_id
    );

ALTER TABLE soa_memory.human_task_lifecycle
    ADD CONSTRAINT fk_a2_human_lifecycle_project_scope
    FOREIGN KEY (
      project_scope,
      objective_id,
      execution_id,
      human_task_id,
      correlation_id
    )
    REFERENCES soa_memory.human_tasks(
      project_scope,
      objective_id,
      execution_id,
      human_task_id,
      correlation_id
    );

COMMIT;
