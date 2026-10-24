# SCN-044 · Authority Spoofing

**Class:** MOCATRIZ authority integrity / exception authorization  
**Status:** ACTIVE / TESTABLE  
**Created:** 2026-10-24

## Problem

A canonical authority name or alias is an identifier, not proof of authority.

The current exception gate accepts the declared string `SOA` or
`Salvador Osorio Ayala` and can return `AUTHORIZED_EXCEPTION` without requiring any
authentication/provenance reference. A caller that knows the alias can therefore spoof
the declared authority.

## Test

1. Present a valid exception reason with authority=`SOA`, but no authority/authentication provenance.
2. Require fail-closed rejection.
3. Present the canonical full name without provenance.
4. Require fail-closed rejection.
5. Present a noncanonical actor with apparently valid provenance.
6. Require rejection.
7. Present canonical/alias identity plus canonical authority_ref and authentication_ref.
8. Require authorization and normalized canonical authority.
9. Keep authentication verification itself outside this module; it must point to upstream identity evidence.

## PASS

- name/alias alone never grants an exception;
- wrong actor never grants an exception;
- provenance is mandatory;
- authorized output normalizes to canonical identity and preserves authentication evidence.

## Canonical rule

> Conocer el nombre de la autoridad no concede autoridad; una excepción exige identidad canónica más evidencia durable de autenticación.
