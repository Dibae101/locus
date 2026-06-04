# Architecture & Vision Notes — Layer 2 (locus-image-runtime)

> The canonical, cross-layer decision log lives in the sibling spec:
> `.kiro/specs/unstructured-to-tabular-etl/architecture-notes.md`
> Read that file for the full decision trail (project name, runtime model, key handling,
> LiteLLM, composition solutions, Hub/Harbor, privacy model, etc.). It spans BOTH layers.
> This file only records what is specific to Layer 2 navigation.

## What this spec owns (Layer 2 = packaging / distribution / runtime)
- Client install + invocation (single CLI, local-process default, Docker optional backend).
- Image pull + local cache; version resolution.
- Locusfile run-configuration surface (source, volumes, ports, schema ref, llm, export,
  review) — minimal required fields = source + image.
- Local LLM credential handling (.env primary; env var / keyring fallbacks; raw-key
  prohibition + gitignore guardrails).
- Multi-image composition = pipeline DAG (NOT docker-compose semantics; compose-FAMILIAR
  syntax only). `needs:`-style dependency edges, parallel branches, cycle detection,
  stage output caching.
- Stage interchange contract: single versioned `Locus_Artifact` envelope, fixed
  Artifact_Type set, Arrow/Parquet payloads, static pre-run type check (fail fast).
- Cross-stage provenance propagation: framework-managed (SDK) lineage, run-scoped
  append-only Lineage_Store, conformance certification, strict/permissive non-conformant.
- Result serving / preview UI / export (local, on mapped port).
- Image authoring + building (Image_Manifest, dependency pinning, conformance cert).
- Publishing to Locus Hub: public + private (Harbor), namespaces, RBAC, self-host path.
- Image discovery; runtime privacy disclosure / consent.

## What the SIBLING spec (`unstructured-to-tabular-etl`, Layer 1) owns
- The processing engine an Image embeds: connectors, parser routing, IR, schema-driven
  extraction, cleaning, dedup, the cell-level grounding/faithfulness contract, HITL review,
  plugin architecture, observability, dual-engine (deterministic default + LLM opt-in),
  LLM guardrails. Req 1-15 there.

## Key cross-references
- Layer 2 Req 6 (interchange) + Req 7 (cross-stage provenance) depend on Layer 1 Req 3 (IR)
  and Req 8 (emission/provenance) being the STABLE VERSIONED contract.
- `image-catalog.md` (this folder) = 65 candidate images / 9 tiers / locked build order.
