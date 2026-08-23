BEGIN;

CREATE TABLE soa_core.context_graph_edges (
    edge_id text PRIMARY KEY,
    from_ref text NOT NULL,
    to_ref text NOT NULL,
    relation_type text NOT NULL,
    directed boolean NOT NULL DEFAULT true,
    valid_from timestamptz,
    valid_until timestamptz,
    weight double precision,
    evidence_ref_id text REFERENCES soa_evidence.evidence_references(evidence_ref_id),
    supersedes_edge_id text REFERENCES soa_core.context_graph_edges(edge_id),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (from_ref <> to_ref OR relation_type IS NOT NULL)
);

CREATE INDEX idx_context_graph_from ON soa_core.context_graph_edges(from_ref);
CREATE INDEX idx_context_graph_to ON soa_core.context_graph_edges(to_ref);
CREATE INDEX idx_context_graph_relation ON soa_core.context_graph_edges(relation_type);
CREATE INDEX idx_context_graph_validity ON soa_core.context_graph_edges(valid_from, valid_until);

COMMIT;
