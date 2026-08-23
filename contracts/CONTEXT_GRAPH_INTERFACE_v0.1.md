# ContextGraph Interface v0.1

Logical operations:
- add_edge
- supersede_edge
- neighbors
- traverse
- temporal_neighbors
- path
- relation_history

P0 reference storage: PostgreSQL `soa_core.context_graph_edges`.

The interface is canonical; the storage engine is not.
A dedicated graph engine is benchmark-gated for P1.
