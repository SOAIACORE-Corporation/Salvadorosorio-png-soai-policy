-- P0 ContextGraph reference traversal.
-- Application supplies :start_ref and :max_depth.

WITH RECURSIVE graph_walk AS (
    SELECT
        e.edge_id,
        e.from_ref,
        e.to_ref,
        e.relation_type,
        1 AS depth,
        ARRAY[e.from_ref, e.to_ref]::text[] AS path
    FROM soa_core.context_graph_edges e
    WHERE e.from_ref = :start_ref

    UNION ALL

    SELECT
        e.edge_id,
        e.from_ref,
        e.to_ref,
        e.relation_type,
        gw.depth + 1,
        gw.path || e.to_ref
    FROM graph_walk gw
    JOIN soa_core.context_graph_edges e
      ON e.from_ref = gw.to_ref
    WHERE gw.depth < :max_depth
      AND NOT e.to_ref = ANY(gw.path)
)
SELECT * FROM graph_walk;
