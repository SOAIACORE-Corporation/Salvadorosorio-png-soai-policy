# SCN-038 · Stale / Contradictory Snapshot

**Class:** MOCATRIZ trusted recovery / temporal lineage integrity  
**Status:** ACTIVE / TESTABLE  
**Created:** 2026-10-24

## Problem

Several Trusted Memory Snapshots can be individually valid, correctly hashed and
plausible while representing different moments or incompatible lineage branches.

Choosing by newest timestamp, highest version number or apparent completeness can
silently turn stale or contradictory state into current authority.

## Test

1. Supply two valid snapshots in one immutable lineage.
2. At an `as_of` before the successor becomes valid, require selection of the predecessor.
3. At a current `as_of`, require selection of the lineage head.
4. Create two valid children of the same predecessor.
5. Require fail-closed rejection of the lineage fork.
6. Create a candidate whose trusted-memory predecessor is missing.
7. Require fail-closed rejection of the lineage gap.
8. Never rank snapshots by field count, narrative completeness or timestamp alone.

## PASS

- historical selection is temporal and deterministic;
- current selection follows the unique trusted lineage head;
- forks are rejected;
- trusted-memory lineage gaps are rejected;
- completeness is not an authority signal.

## Canonical rule

> La versión más nueva o más completa no es necesariamente la autoridad vigente; la autoridad exige lineage temporal no ambiguo.
