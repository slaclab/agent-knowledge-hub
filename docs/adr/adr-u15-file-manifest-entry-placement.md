# ADR-U15: FileManifestEntry placement

**Status:** Accepted
**Date:** 2026-06-03
**Context:** todo/028-skill-file-manifest.md

## Context

`FileManifestEntry` is used in three layers: `RawScanResult` (scanner layer), `Skill` (model layer), and API schemas. A shared definition is needed to avoid circular imports.

## Options

| Option | Pros | Cons |
|---|---|---|
| Define in `scanner.py` | Close to first use; scanner already imports Pydantic | `models/skill.py` imports from a service module |
| Define in `models/skill.py` | Lives with the persistent model | `scanner.py` would import from models — layering violation |
| New `app/types.py` | Clean shared types module, no circular deps | One more file |

## Decision

Define `FileManifestEntry` in `scanner.py` alongside `RawScanResult`. `models/skill.py` imports it from there.

`scanner.py` is a leaf utility module with no upward dependencies — it imports only from the standard library and Pydantic. Importing from it in `models/skill.py` does not create a circular dependency and does not violate layering: the import direction is `models → services/scanner`, not the reverse.

## Consequences

- `models/skill.py` has one import from `app.services.scanner` — this is acceptable.
- All three layers share a single canonical definition; no duplication.
- Adding fields to `FileManifestEntry` only requires changing `scanner.py`.
