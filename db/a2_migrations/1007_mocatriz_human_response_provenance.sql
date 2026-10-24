BEGIN;

-- SCN-036 / MOCATRIZ: durable human authority requires provenance.
-- This does not authenticate the person by itself; authentication_ref must point to
-- upstream authentication evidence. Persistence rejects responses without provenance.

ALTER TABLE soa_memory.human_task_responses
    ADD COLUMN responder_ref text,
    ADD COLUMN authority_level text,
    ADD COLUMN authentication_ref text;

ALTER TABLE soa_memory.human_task_responses
    ADD CONSTRAINT chk_a2_human_response_authority_level
    CHECK (authority_level IS NULL OR authority_level IN ('R1','R2','R3'));

CREATE OR REPLACE FUNCTION soa_memory.require_human_response_provenance()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.responder_ref IS NULL OR btrim(NEW.responder_ref) = '' THEN
        RAISE EXCEPTION 'HUMAN_RESPONSE_PROVENANCE_REQUIRED: responder_ref';
    END IF;
    IF NEW.authority_level IS NULL OR NEW.authority_level NOT IN ('R1','R2','R3') THEN
        RAISE EXCEPTION 'HUMAN_RESPONSE_PROVENANCE_REQUIRED: authority_level';
    END IF;
    IF NEW.authentication_ref IS NULL OR btrim(NEW.authentication_ref) = '' THEN
        RAISE EXCEPTION 'HUMAN_RESPONSE_PROVENANCE_REQUIRED: authentication_ref';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_a2_require_human_response_provenance
    BEFORE INSERT ON soa_memory.human_task_responses
    FOR EACH ROW EXECUTE FUNCTION soa_memory.require_human_response_provenance();

COMMIT;
