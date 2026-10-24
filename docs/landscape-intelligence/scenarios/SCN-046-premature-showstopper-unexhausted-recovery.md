# SCN-046 · Premature SHOWSTOPPER / Unexhausted Recovery

**Class:** MOCATRIZ self-regulation / stop-decision integrity  
**Status:** ACTIVE / TESTABLE  
**Created:** 2026-10-24

## Problem

MOCATRIZ defines SHOWSTOPPER as an operational conclusion reached after reasonable
recovery attempts and alternatives are exhausted. The execution primitive previously
accepted `showstopper=True` as a caller assertion without requiring evidence that
stopping was justified.

That allows a formally valid terminal state to hide premature abandonment.

## Test

1. Claim SHOWSTOPPER without a stop assessment → reject.
2. Fail one recovery route while a viable untried alternative remains → CONTINUE.
3. Encounter a human-resolvable dependency with an available human authority → WAITING_HUMAN.
4. Present a material blocker without evidence that alternatives were exhausted → BLOCKED.
5. Present failed/partial recovery evidence, all known alternatives FAILED/BLOCKED,
   no available human resolution, and a material irreducible blocker → SHOWSTOPPER.

## PASS

- caller assertion alone cannot produce SHOWSTOPPER;
- viable alternatives prevent terminal stopping;
- available human authority produces WAITING_HUMAN, not SHOWSTOPPER;
- blocker without exhaustion evidence is BLOCKED;
- SHOWSTOPPER requires evidence-backed exhaustion and irreducible blocking.

## Nullifiers

- any caller can set showstopper=True without evidence;
- an untried viable alternative coexists with SHOWSTOPPER;
- an available authority-bound human dependency is classified SHOWSTOPPER;
- the control requires an arbitrary fixed number of retries rather than evidence.

## Canonical rule

> Detenerse también requiere evidencia: SHOWSTOPPER no es una bandera, es una conclusión.
