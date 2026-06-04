# Locus Image Catalog (working list)

> Candidate "capability images" to build and publish to Locus Hub. Each image contains
> LOGIC (parser + extractor + validator + emitter + pinned config); the USER brings their
> own data. Default engine = deterministic Python; LLM engine activates only when the user
> supplies a key (see architecture-notes.md). Every image inherits the cell-level
> provenance + faithfulness grounding contract from the Layer-1 engine.
>
> Status legend: [ ] not started | [~] in progress | [x] shipped
> This catalog will likely move into the sibling `data-image-runtime` spec.

## Guiding principle
- ~80% of enterprise data is unstructured; extraction (not the model) is the bottleneck.
- Highest recurring-spend jobs: invoices, receipts, bank statements, contracts, reports.
- DO NOT build breadth-first. Ship one fully-grounded image at a time.
- "Solve ALL data problems" is rejected as a goal — this list is the SUPERSET of what's
  possible; discipline = ship incrementally starting with `doc-to-tables`.

---

## Tier 1 — Document -> Structured (highest, proven demand)
1. [ ] `doc-to-tables` — tables from PDF/scan/Word -> rows. FIRST image to build.
2. [ ] `invoice-extractor` — invoices -> fields + line items.
3. [ ] `receipt-extractor` — receipts -> expense records.
4. [ ] `bank-statement-extractor` — statements -> transaction tables.
5. [ ] `resume-parser` — CVs -> candidate schema.
6. [ ] `contract-extractor` — clauses, parties, dates, obligations, renewal terms.
7. [ ] `form-extractor` — tax/customs/medical/court forms -> fields.
8. [ ] `report-extractor` — annual/financial reports -> tables + KPIs.
9. [ ] `scanned-ocr-to-table` — OCR-first for image-only scans (no text layer).

## Tier 2 — Format Conversion & Reshaping (broad everyday demand)
10. [ ] `any-to-json` — any source -> clean schema-stable JSON (dominant AI-ready format).
11. [ ] `any-to-csv` / `any-to-parquet` — tabular export for analytics.
12. [ ] `any-to-yaml` — config-shaped output.
13. [ ] `any-to-markdown` — doc/web -> clean Markdown (standard RAG ingestion format).
14. [ ] `json-reshaper` — JSON -> JSON remap/flatten/nest.
15. [ ] `schema-mapper` — map source schema -> target schema (rename, type-align).

## Tier 3 — Cleaning, Quality & Identity (the "data is messy" problems)
16. [ ] `data-cleaner` — type coercion, normalization, missing-value handling.
17. [ ] `deduplicator` / `entity-resolver` — match + merge same-real-world-entity records.
18. [ ] `data-validator` — assert dataset vs rules/constraints, report violations.
19. [ ] `data-enricher` — augment records with derived/looked-up fields.
20. [ ] `normalizer` — standardize units, currencies, dates, addresses, phone numbers.

## Tier 4 — RAG / AI-Prep (serves the "feed the LLM" goal directly)
21. [ ] `chunker` — layout-aware chunking (make-or-break RAG step).
22. [ ] `embedder` — chunk -> vector, output to Parquet / vector DB.
23. [ ] `knowledge-graph-builder` — text -> entities + relationships (triples) for GraphRAG.
24. [ ] `metadata-enricher` — LLM-generated metadata to improve retrieval.
25. [ ] `qa-pair-generator` — corpus -> synthetic Q&A pairs for fine-tune/eval.

## Tier 5 — Multimodal (next frontier; less crowded)
26. [ ] `audio-to-table` — transcription + diarization -> structured transcript/records.
27. [ ] `video-to-table` — frames + ASR -> structured events/timestamps.
28. [ ] `image-to-data` — charts/diagrams/photos -> structured values.
29. [ ] `email-extractor` — emails/threads -> structured fields.
30. [ ] `log-parser` — app/system logs -> structured events.

## Tier 6 — Unique / hard-problem images (Locus differentiation; lean on grounding engine)
31. [ ] `pii-redactor` — detect + mask PII in structured + unstructured data.
32. [ ] `provenance-tracker` — emit data with full cell-level lineage as the headline output.
33. [ ] `fact-grounder` — score faithfulness of every cell in an EXISTING table vs sources
       (validation-as-a-service). Flagship/marketing wedge.
34. [ ] `synthetic-data-generator` — schema -> realistic synthetic rows, referential
       integrity across multi-table schemas.
35. [ ] `cross-doc-reconciler` — reconcile conflicting values across multiple docs, surface
       the conflict with provenance.
36. [ ] `table-joiner` — semantic/fuzzy join of tables lacking shared keys.
37. [ ] `time-series-structurer` — messy event text -> clean time series (no peak flatten).
38. [ ] `taxonomy-classifier` — auto-classify records into a user-defined taxonomy tree.
39. [ ] `change-diff` — diff two versions of a doc/dataset -> structured changeset.
40. [ ] `anomaly-flagger` — flag outlier/suspect rows with reasons (quality + fraud signal).

## Tier 7 — Domain-specific verticals (additional; high willingness-to-pay)
41. [ ] `medical-record-extractor` — clinical notes/EHR text -> structured codes (ICD/SNOMED-style).
42. [ ] `legal-doc-extractor` — case law / filings -> citations, holdings, parties.
43. [ ] `scientific-paper-extractor` — papers -> structured methods/results tables, citations.
44. [ ] `financial-filing-extractor` — 10-K/earnings -> normalized financial line items.
45. [ ] `real-estate-doc-extractor` — leases/deeds -> property + terms schema.
46. [ ] `insurance-claim-extractor` — claims/policies -> structured claim records.
47. [ ] `shipping-logistics-extractor` — BOL / customs / manifests -> structured shipment data.
48. [ ] `survey-response-structurer` — free-text survey answers -> coded categorical data.
49. [ ] `product-catalog-extractor` — supplier sheets/specs -> normalized product attributes.
50. [ ] `menu-extractor` — restaurant menus (img/PDF) -> items + prices + modifiers.

## Tier 8 — Web & API sources (additional)
51. [ ] `web-to-table` — web pages/listings -> structured rows (price/spec scraping).
52. [ ] `api-to-table` — paginated REST/GraphQL responses -> flattened tables.
53. [ ] `sitemap-crawler-to-corpus` — crawl a site -> clean corpus for downstream images.
54. [ ] `social-feed-structurer` — posts/threads -> structured engagement/content records.
55. [ ] `spreadsheet-normalizer` — messy human Excel (merged cells, multi-header) -> tidy table.

## Tier 9 — Operational / pipeline-utility images (additional; glue + governance)
56. [ ] `schema-inferer` — sample data -> proposed Pydantic schema (bootstraps other images).
57. [ ] `data-profiler` — dataset -> stats/quality report (nulls, cardinality, distributions).
58. [ ] `data-masker` / `anonymizer` — reversible/irreversible masking beyond PII (k-anon).
59. [ ] `format-detector` — sniff + classify unknown file/content types for routing.
60. [ ] `language-detector-translator` — detect language, optionally normalize to one language.
61. [ ] `unit-test-data-extractor` — code repos -> structured fixtures/test data.
62. [ ] `csv-repair` — fix broken/ragged CSVs (bad quoting, mixed delimiters, encoding).
63. [ ] `encoding-normalizer` — normalize text encodings / mojibake repair.
64. [ ] `dataset-merger` — union/merge heterogeneous datasets into one schema.
65. [ ] `incremental-sync` — detect new/changed source records since last run (CDC-style).

## Build-order recommendation (LOCKED priority)
1. `doc-to-tables` (Tier 1 #1) — proves full engine end-to-end; everything reuses its plumbing.
2. Tier-1 specializations `invoice-extractor`, `receipt-extractor` — base + baked-in schema; highest revenue.
3. 2-3 conversion images `any-to-json`, `any-to-markdown` — high pull volume, low build cost, drives adoption.
4. One flagship unique image `fact-grounder` (or `provenance-tracker`) — the marketing wedge competitors lack.
5. Tiers 4-9 follow once base engine + packaging are battle-tested.

## Notes / open
- Several Tier 6 images (fact-grounder, provenance-tracker, cross-doc-reconciler) are the
  defensible differentiation — they ARE the grounding engine, packaged.
- Each image should advertise: engine mode support (deterministic / LLM / hybrid),
  privacy class (local-only vs calls-external-LLM), and required vs inferred schema.
- Verticals (Tier 7) are mostly Tier-1 base + a baked-in domain schema + tuned prompts;
  cheap to produce once base exists, high willingness-to-pay.
