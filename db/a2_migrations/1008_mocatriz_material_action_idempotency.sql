BEGIN;

-- SCN-050 / MOCATRIZ: durable material-action identity and replay protection.
-- The ledger records intent and outcomes without performing any external mutation.

CREATE TABLE soa_ops.material_actions (
    action_id text PRIMARY KEY,
    project_scope text NOT NULL CHECK (btrim(project_scope) <> ''),
    objective_id text NOT NULL,
    execution_id text NOT NULL,
    idempotency_key text NOT NULL CHECK (btrim(idempotency_key) <> ''),
    action_type text NOT NULL CHECK (btrim(action_type) <> ''),
    target_ref text NOT NULL CHECK (btrim(target_ref) <> ''),
    payload_sha256 text NOT NULL CHECK (btrim(payload_sha256) <> ''),
    observed_time timestamptz NOT NULL,
    recorded_time timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_scope, idempotency_key),
    UNIQUE (action_id, project_scope)
);

CREATE TABLE soa_ops.material_action_events (
    event_id text PRIMARY KEY,
    action_id text NOT NULL,
    project_scope text NOT NULL CHECK (btrim(project_scope) <> ''),
    event_seq integer NOT NULL CHECK (event_seq > 0),
    state text NOT NULL CHECK (state IN (
      'INTENDED','DISPATCHED','SUCCEEDED','FAILED','INDETERMINATE'
    )),
    receipt_ref text,
    retryable boolean,
    observed_time timestamptz NOT NULL,
    recorded_time timestamptz NOT NULL DEFAULT now(),
    previous_event_id text REFERENCES soa_ops.material_action_events(event_id),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (action_id, event_seq),
    FOREIGN KEY (action_id, project_scope)
      REFERENCES soa_ops.material_actions(action_id, project_scope),
    CHECK (state <> 'SUCCEEDED' OR receipt_ref IS NOT NULL)
);

CREATE OR REPLACE FUNCTION soa_ops.enforce_material_action_transition()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    previous soa_ops.material_action_events%ROWTYPE;
BEGIN
    IF NEW.event_seq = 1 THEN
        IF NEW.previous_event_id IS NOT NULL OR NEW.state <> 'INTENDED' THEN
            RAISE EXCEPTION 'Material action first event must be INTENDED with no previous event';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.previous_event_id IS NULL THEN
        RAISE EXCEPTION 'Material action event_seq > 1 requires previous_event_id';
    END IF;

    SELECT * INTO previous
    FROM soa_ops.material_action_events
    WHERE event_id = NEW.previous_event_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Material action previous event does not exist';
    END IF;
    IF previous.action_id <> NEW.action_id OR previous.project_scope <> NEW.project_scope THEN
        RAISE EXCEPTION 'Material action transition cannot cross action or project scope';
    END IF;
    IF NEW.event_seq <> previous.event_seq + 1 THEN
        RAISE EXCEPTION 'Material action event sequence must be contiguous';
    END IF;

    IF previous.state = 'INTENDED' AND NEW.state <> 'DISPATCHED' THEN
        RAISE EXCEPTION 'INTENDED may transition only to DISPATCHED';
    ELSIF previous.state = 'DISPATCHED' AND NEW.state NOT IN ('SUCCEEDED','FAILED','INDETERMINATE') THEN
        RAISE EXCEPTION 'DISPATCHED may transition only to SUCCEEDED, FAILED or INDETERMINATE';
    ELSIF previous.state = 'INDETERMINATE' AND NEW.state NOT IN ('SUCCEEDED','FAILED') THEN
        RAISE EXCEPTION 'INDETERMINATE requires reconciliation to SUCCEEDED or FAILED';
    ELSIF previous.state = 'FAILED' AND NOT (previous.retryable IS TRUE AND NEW.state = 'DISPATCHED') THEN
        RAISE EXCEPTION 'FAILED may retry only when previous event is explicitly retryable';
    ELSIF previous.state = 'SUCCEEDED' THEN
        RAISE EXCEPTION 'SUCCEEDED material action is terminal';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_a2_material_action_transition
    BEFORE INSERT ON soa_ops.material_action_events
    FOR EACH ROW EXECUTE FUNCTION soa_ops.enforce_material_action_transition();

CREATE TRIGGER trg_a2_material_actions_append_only
    BEFORE UPDATE OR DELETE ON soa_ops.material_actions
    FOR EACH ROW EXECUTE FUNCTION soa_memory.reject_history_mutation();

CREATE TRIGGER trg_a2_material_action_events_append_only
    BEFORE UPDATE OR DELETE ON soa_ops.material_action_events
    FOR EACH ROW EXECUTE FUNCTION soa_memory.reject_history_mutation();

COMMIT;
