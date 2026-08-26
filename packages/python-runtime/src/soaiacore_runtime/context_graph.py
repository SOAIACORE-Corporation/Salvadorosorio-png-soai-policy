from __future__ import annotations

from datetime import datetime
from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb

from .errors import contract_error
from .operations import utc_iso
from .schemas import validate_payload


def edge_to_schema(row: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "edge_id": row["edge_id"],
        "from_ref": row["from_ref"],
        "to_ref": row["to_ref"],
        "relation_type": row["relation_type"],
        "directed": row["directed"],
        "valid_from": utc_iso(row["valid_from"]) if row["valid_from"] else None,
        "valid_until": utc_iso(row["valid_until"]) if row["valid_until"] else None,
        "weight": row["weight"],
        "evidence_ref": row["evidence_ref_id"],
        "metadata": row["metadata"],
        "created_at": utc_iso(row["created_at"]),
    }
    validate_payload("context-graph-edge-v0.1.schema.json", payload, stage="CONTEXT_GRAPH")
    return payload


def insert_edge(
    connection: Connection,
    payload: dict[str, Any],
    *,
    supersedes_edge_id: str | None = None,
) -> dict[str, Any]:
    validate_payload("context-graph-edge-v0.1.schema.json", payload, stage="CONTEXT_GRAPH")
    connection.execute(
        """
        INSERT INTO soa_core.context_graph_edges(
          edge_id,from_ref,to_ref,relation_type,directed,valid_from,valid_until,
          weight,evidence_ref_id,supersedes_edge_id,metadata,created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            payload["edge_id"],
            payload["from_ref"],
            payload["to_ref"],
            payload["relation_type"],
            payload["directed"],
            payload["valid_from"],
            payload.get("valid_until"),
            payload.get("weight"),
            payload.get("evidence_ref"),
            supersedes_edge_id,
            Jsonb(payload.get("metadata", {})),
            payload["created_at"],
        ),
    )
    row = connection.execute(
        "SELECT * FROM soa_core.context_graph_edges WHERE edge_id=%s", (payload["edge_id"],)
    ).fetchone()
    return edge_to_schema(row)


def supersede_edge(
    connection: Connection, old_edge_id: str, replacement: dict[str, Any]
) -> dict[str, Any]:
    existing = connection.execute(
        "SELECT edge_id FROM soa_core.context_graph_edges WHERE edge_id=%s", (old_edge_id,)
    ).fetchone()
    if not existing:
        raise contract_error(
            "RESOURCE_NOT_FOUND", "ContextGraph edge does not exist", "CONTEXT_GRAPH", status_code=404
        )
    if replacement["edge_id"] == old_edge_id:
        raise contract_error(
            "INVALID_STATE_TRANSITION",
            "A superseding edge requires a new edge_id",
            "CONTEXT_GRAPH",
            status_code=409,
        )
    return insert_edge(connection, replacement, supersedes_edge_id=old_edge_id)


def neighbors(
    connection: Connection,
    *,
    reference: str,
    direction: str = "BOTH",
    at: datetime | None = None,
) -> list[dict[str, Any]]:
    if direction not in {"OUT", "IN", "BOTH"}:
        raise contract_error(
            "SCHEMA_VALIDATION_FAILED", "direction must be OUT, IN, or BOTH", "CONTEXT_GRAPH"
        )
    condition = {
        "OUT": "from_ref=%s",
        "IN": "to_ref=%s",
        "BOTH": "(from_ref=%s OR to_ref=%s)",
    }[direction]
    params: list[Any] = [reference] if direction != "BOTH" else [reference, reference]
    temporal = ""
    if at:
        temporal = " AND (valid_from IS NULL OR valid_from<=%s) AND (valid_until IS NULL OR valid_until>%s)"
        params.extend([at, at])
    rows = connection.execute(
        f"SELECT * FROM soa_core.context_graph_edges WHERE {condition}{temporal} ORDER BY edge_id",
        params,
    ).fetchall()
    return [edge_to_schema(row) for row in rows]


def traverse(
    connection: Connection, *, start_ref: str, max_depth: int
) -> list[dict[str, Any]]:
    if max_depth < 1 or max_depth > 10:
        raise contract_error(
            "SCHEMA_VALIDATION_FAILED", "max_depth must be between 1 and 10", "CONTEXT_GRAPH"
        )
    return list(
        connection.execute(
            """
            WITH RECURSIVE graph_walk AS (
              SELECT e.edge_id,e.from_ref,e.to_ref,e.relation_type,1 AS depth,
                     ARRAY[e.from_ref,e.to_ref]::text[] AS path
              FROM soa_core.context_graph_edges e WHERE e.from_ref=%s
              UNION ALL
              SELECT e.edge_id,e.from_ref,e.to_ref,e.relation_type,gw.depth+1,
                     gw.path || e.to_ref
              FROM graph_walk gw
              JOIN soa_core.context_graph_edges e ON e.from_ref=gw.to_ref
              WHERE gw.depth<%s AND NOT e.to_ref=ANY(gw.path)
            )
            SELECT * FROM graph_walk ORDER BY depth,edge_id
            """,
            (start_ref, max_depth),
        ).fetchall()
    )


def path_between(
    connection: Connection, *, from_ref: str, to_ref: str, max_depth: int
) -> list[str] | None:
    rows = traverse(connection, start_ref=from_ref, max_depth=max_depth)
    candidates = [row for row in rows if row["to_ref"] == to_ref]
    if not candidates:
        return None
    chosen = sorted(candidates, key=lambda item: (item["depth"], item["edge_id"]))[0]
    return list(chosen["path"])


def relation_history(connection: Connection, edge_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        WITH RECURSIVE ancestors AS (
          SELECT * FROM soa_core.context_graph_edges WHERE edge_id=%s
          UNION ALL
          SELECT parent.*
          FROM soa_core.context_graph_edges parent
          JOIN ancestors child ON child.supersedes_edge_id=parent.edge_id
        ), descendants AS (
          SELECT * FROM soa_core.context_graph_edges WHERE edge_id=%s
          UNION ALL
          SELECT child.*
          FROM soa_core.context_graph_edges child
          JOIN descendants parent ON child.supersedes_edge_id=parent.edge_id
        )
        SELECT DISTINCT * FROM (
          SELECT * FROM ancestors UNION ALL SELECT * FROM descendants
        ) all_edges
        ORDER BY created_at,edge_id
        """,
        (edge_id, edge_id),
    ).fetchall()
    if not rows:
        raise contract_error(
            "RESOURCE_NOT_FOUND", "ContextGraph edge does not exist", "CONTEXT_GRAPH", status_code=404
        )
    return [edge_to_schema(row) for row in rows]
