# SCN-043 · Evidence Tampering / Hash Mismatch

**Class:** MOCATRIZ trusted recovery / physical integrity  
**Status:** PASS / CONTROLLED  
**Created:** 2026-10-24

## Problem

Snapshot and manifest integrity are hashed, but a fidelity receipt can still be treated as
confirmed evidence without a self-hash and without a manifest-level expected receipt hash.
A modified receipt could therefore preserve the hashes it quotes while changing its own
decision, limitations or recovery conclusion.

## Test

1. Build a valid sealed snapshot, manifest, evidence inventory and fidelity receipt.
2. Bind the receipt in the manifest by receipt ID + expected hash.
3. Require trusted reconstruction to validate all four artifacts.
4. Modify the snapshot without resealing → reject.
5. Modify the manifest without resealing → reject.
6. Modify the receipt without resealing → reject.
7. Supply a different valid receipt whose hash does not match the manifest binding → reject.
8. Preserve compatibility for legacy manifests that never claimed receipt hash binding.

## PASS

- snapshot tampering invalidates recovery;
- manifest tampering invalidates recovery;
- receipt tampering invalidates recovery when the manifest declares a sealed receipt;
- a valid-but-different receipt cannot substitute for the bound receipt;
- legacy artifacts are not silently upgraded to a stronger guarantee.

## Canonical rule

> La integridad de la evidencia certificadora debe ser verificable por contenido, no sólo por el nombre del archivo o por los hashes que el propio receipt declara.
