# SCN-036 · Human Response Provenance Gate

**Class:** MOCATRIZ authority integrity / provenance  
**Status:** ACTIVE / TESTABLE  
**Created:** 2026-10-24

## Problem

Correlation proves which Human Task a response targets. It does not prove who supplied
the answer or what authentication/authority evidence supports it.

A durable response without actor provenance is evidence of text, not durable evidence
of human authority.

## Test

1. Persist a legitimate WAITING_HUMAN task.
2. Submit a perfectly correlated answer with no responder identity, authority level or
   authentication reference.
3. Require fail-closed rejection.
4. Submit a response with responder_ref, authority_level and authentication_ref.
5. Recover the Human Task bundle.

## PASS

- unprovenanced response is rejected;
- provenanced response is accepted;
- provenance survives durable recovery;
- correlation controls remain active;
- test does not claim that the database itself authenticated the human.

## Boundary

`authentication_ref` is a durable pointer to upstream authentication evidence. This
scenario does **not** prove cryptographic human authentication end-to-end; that requires
an identity-provider integration test.

## Canonical rule

> Una respuesta correlacionada no es autoridad durable si no conserva quién respondió y qué evidencia autentica esa autoridad.
