# Requirements Document

## Introduction

This feature defines an open-source, self-hosted Python framework (pip-installable, in the spirit of Instructor, Docling, and RAGAS) that owns the full data pipeline from a mixed, unstructured corpus to validated, source-grounded tabular data ready to feed a Large Language Model (LLM). The framework ingests documents (PDFs, scans, invoices, contracts), web pages, APIs, and databases; routes each source to a best-in-class parser; normalizes content into a common intermediate representation that preserves layout, tables, and source coordinates; extracts rows against a user-declared schema with auto-retry validation; cleans and deduplicates the data; and validates each output cell against its source using a Retrieval-Augmented Generation (RAG) groundedness check.

The framework runs as two cooperating engines within a single Pipeline: a deterministic-Python engine (the default, requiring no LLM and keeping data local) and an optional LLM-backed engine that activates only when the user supplies an LLM API key. When the LLM engine is active, it operates as a bounded, guardrailed component in a hybrid arrangement: deterministic Python performs the structural heavy lifting (parsing, layout detection, table detection, type coercion, deduplication) and the LLM is restricted to the fuzzy task of mapping ambiguous content to schema fields. The LLM is never permitted to make unconstrained decisions, and every LLM-produced value remains subject to schema validation and the grounding contract.

The core differentiator is a cell-level source-grounding contract: every emitted cell carries provenance (its source location) and a faithfulness score, and the Pipeline can flag or reject rows that fall below a configurable grounding threshold. A human-in-the-loop review workflow lets reviewers correct flagged rows, and those corrections feed back into the schema and extraction prompts. The framework is built around a plugin architecture so that connectors, parsers, extractors, validators, and emitters can be extended by third parties.

LLM provider credentials are handled at run time on the user's machine only; the framework never transmits credentials or user data to any hosted service. Data privacy is therefore engine-dependent: deterministic and local-model engines keep all data on the user's machine, whereas a hosted-API LLM engine sends data to the configured third-party provider. The framework discloses this and obtains user consent before any data leaves the user's environment.

This document specifies the requirements for Layer 1, the processing engine. The packaging, distribution, command-line interface, multi-image composition, and registry (Locus Hub) concerns that build on top of this engine are specified separately in the companion `locus-image-runtime` spec.

## Glossary

- **Framework**: The complete open-source Python library being specified, encompassing all components below.
- **Pipeline**: The orchestrating component that executes the ordered phases (Ingest, Parse, Extract, Clean, Validate, Emit, Review) and manages data flow between them.
- **Source**: A single unit of input data to be processed (one file, one URL, one API response, or one database query result set).
- **Corpus**: A collection of one or more Sources submitted together for processing.
- **Connector**: A plugin component that reads raw bytes or records from an input location (file system, URL, API, or database) and yields Sources.
- **Parser**: A plugin component that converts a Source's raw content into the Intermediate Representation.
- **Parser_Router**: The component that selects the appropriate Parser for a given Source based on Source type and configuration.
- **Intermediate_Representation** (IR): A common, parser-agnostic data structure that holds normalized content, preserving text, layout, tables, and Source Location metadata.
- **Source_Location**: Structured provenance metadata that identifies where a piece of content originated, including Source identifier, page or record index, and bounding-box coordinates or character offsets when available.
- **Extractor**: The component that fills rows of a Target Schema from the Intermediate Representation. The Extractor operates using either the Deterministic Engine or, when activated, the LLM Engine.
- **Deterministic_Engine**: The default extraction engine that derives Rows using deterministic Python libraries and rules only, without invoking any LLM. It requires no LLM API key and keeps all data on the user's machine.
- **LLM_Engine**: The optional extraction engine that uses an LLM, accessed through the Provider Router, to perform fuzzy mapping of content to schema fields. It activates only when an LLM Credential is available and operates under the LLM Guardrails.
- **Provider_Router**: The bundled LiteLLM-based component that presents a single in-process interface to multiple LLM providers; the provider and model are selected through the Pipeline Configuration.
- **LLM_Guardrails**: The constraints applied to the LLM Engine: outputs are constrained to the Target Schema with auto-retry on violation, deterministic results take precedence, the LLM is restricted to fuzzy field-mapping, and the LLM cannot override a deterministic result without the affected Row being flagged.
- **LLM_Credential**: An LLM provider API key supplied by the user at run time through local means only (an environment file referenced by the Locusfile, an environment variable, or the local OS keyring). It is never stored by any hosted Locus service and never written literally into the Locusfile.
- **Target_Schema**: The definition of the columns, types, and constraints of the desired tabular output. It is optional and supports three modes: Infer Mode, Hint Mode, and Strict Mode.
- **Infer_Mode**: A Target Schema mode in which the Extractor infers the columns and types from the data, requiring no schema declaration from the user.
- **Hint_Mode**: A Target Schema mode in which the user supplies loose column hints (names, types, required flags) in the Locusfile to steer extraction without enforcing full validation.
- **Strict_Mode**: A Target Schema mode in which the user references a Pydantic model that enforces full field types, constraints, and custom validators.
- **Locusfile**: A declarative YAML run-configuration file that supplies the data source, optional schema, LLM settings, and output settings for a Pipeline run. Its full surface, including multi-image composition, is specified in the companion `locus-image-runtime` spec.
- **Row**: A single record produced by the Extractor that conforms to the Target Schema.
- **Cell**: A single field value within a Row, corresponding to one column of the Target Schema.
- **Cleaner**: The component that performs type coercion, normalization, and entity resolution on extracted Rows.
- **Deduplicator**: The component that identifies and resolves duplicate Rows.
- **Validator**: The component that performs a groundedness check, computing a Faithfulness Score for each Cell against its Source content. It operates in Full Grounding Mode when an LLM is available and in Degraded Grounding Mode otherwise.
- **Full_Grounding_Mode**: A Validator mode that uses an LLM-as-judge to compute Faithfulness Scores; available only when the LLM Engine is active.
- **Degraded_Grounding_Mode**: A Validator mode that computes Faithfulness Scores using embedding or string similarity without an LLM; used when no LLM Credential is available.
- **Faithfulness_Score**: A numeric value in the range 0.0 to 1.0 indicating how well a Cell's value is supported by the cited Source content, where 1.0 is fully supported.
- **Grounding_Threshold**: A configurable numeric value in the range 0.0 to 1.0; Rows containing Cells with a Faithfulness Score below this value are flagged.
- **Provenance**: The combination of Source Location and Faithfulness Score attached to a Cell.
- **Emitter**: The component that writes validated Rows to a tabular output format (DataFrame, Parquet, or SQL).
- **Lineage_Column**: A reserved column in the emitted output that carries the Provenance for each Row or Cell.
- **Reviewer**: A human user who inspects and corrects flagged Rows.
- **Review_Queue**: The ordered set of flagged Rows presented to a Reviewer.
- **Correction**: A Reviewer-supplied change to a Cell value or schema, recorded for feedback.
- **Plugin**: Any Connector, Parser, Extractor, Validator, or Emitter registered with the Framework through its extension interface.
- **Pipeline_Configuration**: The user-supplied settings that control Pipeline behavior, including Grounding Threshold, retry limits, model selection, and plugin selection.
- **Observability_Event**: A structured record emitted by the Framework describing a processing step, its inputs, outputs, timing, and outcome.

## Requirements

### Requirement 1: Corpus Ingestion via Pluggable Connectors

**User Story:** As a data engineer, I want to ingest a mixed corpus of files, URLs, APIs, and databases through pluggable connectors, so that I can process heterogeneous sources through one pipeline.

#### Acceptance Criteria

1. WHEN a Corpus containing one or more Sources is submitted to the Pipeline, THE Pipeline SHALL route each Source to a registered Connector that declares support for that Source type.
2. THE Framework SHALL provide built-in Connectors for local file system paths, HTTP and HTTPS URLs, REST APIs, and SQL databases.
3. WHEN a Connector reads a Source, THE Connector SHALL produce raw content together with a unique Source identifier.
4. IF no registered Connector declares support for a submitted Source type, THEN THE Pipeline SHALL record an unsupported-source error containing the Source identifier and continue processing the remaining Sources.
5. IF a Connector fails to read a Source, THEN THE Pipeline SHALL record a read error containing the Source identifier and the failure reason and continue processing the remaining Sources.
6. WHERE a Connector requires authentication credentials, THE Connector SHALL accept those credentials through the Pipeline Configuration.

### Requirement 2: Parser Routing

**User Story:** As a data engineer, I want each source automatically routed to the best parser for its type, so that I get high-quality extraction without manually selecting parsers.

#### Acceptance Criteria

1. WHEN a Source is ingested, THE Parser_Router SHALL select a registered Parser based on the Source's detected content type.
2. THE Framework SHALL provide built-in Parser integrations for PDF documents, scanned images requiring optical character recognition, HTML web pages, and structured records from APIs and databases.
3. WHERE the Pipeline Configuration specifies a Parser for a given content type, THE Parser_Router SHALL select the specified Parser instead of the default Parser for that content type.
4. IF the Parser specified in the Pipeline Configuration is unavailable at runtime, THEN THE Pipeline SHALL halt the Corpus run and raise a parser-unavailable error identifying the specified Parser.
5. IF the Parser_Router cannot determine a content type for a Source, THEN THE Parser_Router SHALL record a routing error containing the Source identifier, skip that Source, and continue processing the remaining Sources.
6. IF no registered Parser declares support for a Source's content type, THEN THE Parser_Router SHALL record an unsupported-content-type error containing the Source identifier and content type, skip that Source, and continue processing the remaining Sources.

### Requirement 3: Parse and Normalize to Intermediate Representation

**User Story:** As a framework developer, I want all parsers to emit a common intermediate representation that preserves layout, tables, and source coordinates, so that downstream phases work uniformly regardless of input type.

#### Acceptance Criteria

1. WHEN a Parser processes a Source, THE Parser SHALL produce an Intermediate_Representation that contains the extracted text content.
2. THE Intermediate_Representation SHALL preserve table structures detected in the Source as row-and-column data.
3. WHEN a Parser extracts a content element, THE Parser SHALL attach a Source_Location to that element identifying the Source identifier and the page or record index.
4. WHERE a Parser provides positional information, THE Parser SHALL include bounding-box coordinates or character offsets in the Source_Location.
5. IF a Parser fails to process a Source, THEN THE Pipeline SHALL record a parse error containing the Source identifier and the failure reason and continue processing the remaining Sources.

### Requirement 4: Schema-Driven Extraction with Auto-Retry Validation

**User Story:** As a data analyst, I want to optionally declare a target schema and have the pipeline fill rows that are automatically validated, so that I receive structured data conforming to my needs with as little configuration as possible.

#### Acceptance Criteria

1. THE Extractor SHALL support a Target_Schema in Infer_Mode, Hint_Mode, and Strict_Mode.
2. WHERE no Target_Schema is supplied in the Pipeline Configuration, THE Extractor SHALL operate in Infer_Mode and infer the columns and types from the Intermediate_Representation.
3. WHERE a Target_Schema is supplied in Hint_Mode, THE Extractor SHALL use the supplied column hints to steer extraction without enforcing full validation.
4. WHERE a Target_Schema is supplied in Strict_Mode as a Pydantic model, THE Extractor SHALL produce Rows whose Cells conform to the field types, constraints, and custom validators defined in that model.
5. IF an extracted Row fails Strict_Mode Target_Schema validation, THEN THE Extractor SHALL retry extraction for that Row, where the retry limit defined in the Pipeline Configuration specifies the number of additional attempts beyond the first attempt.
6. IF an extracted Row fails Strict_Mode Target_Schema validation after reaching the retry limit, THEN THE Extractor SHALL record a validation-failure error containing the Source identifier and the validation messages.
7. WHEN the Extractor produces a Cell, THE Extractor SHALL associate that Cell with the Source_Location of the Intermediate_Representation content used to derive the Cell value.

### Requirement 5: Cleaning, Type Coercion, and Normalization

**User Story:** As a data analyst, I want extracted values cleaned and normalized, so that the output table has consistent types and formats.

#### Acceptance Criteria

1. WHEN the Cleaner processes a Row, THE Cleaner SHALL coerce each Cell value to the data type declared for its column in the Target_Schema.
2. WHERE a normalization rule is defined in the Pipeline Configuration for a column, THE Cleaner SHALL apply that normalization rule to each Cell in that column.
3. IF a Cell value cannot be coerced to its declared column type, THEN THE Cleaner SHALL flag the Row and record a coercion error containing the Source identifier and the column name.
4. WHEN the Cleaner modifies a Cell value, THE Cleaner SHALL preserve the Source_Location associated with that Cell.

### Requirement 6: Deduplication and Entity Resolution

**User Story:** As a data analyst, I want duplicate rows identified and resolved, so that my output table contains one record per real-world entity.

#### Acceptance Criteria

1. WHERE deduplication is enabled in the Pipeline Configuration, THE Deduplicator SHALL identify Rows that match according to the configured matching keys.
2. WHEN the Deduplicator identifies a set of matching Rows, THE Deduplicator SHALL merge that set into one Row according to the configured merge strategy.
3. WHEN the Deduplicator merges a set of matching Rows into one Row, THE Deduplicator SHALL retain the Source_Location of each contributing Cell in the merged Row.
4. WHERE deduplication is disabled in the Pipeline Configuration, THE Deduplicator SHALL pass all Rows through unchanged.

### Requirement 7: Cell-Level Source Grounding and Validation Contract

**User Story:** As a compliance-conscious user, I want every output cell scored for how well it is supported by its source and low-confidence rows flagged, so that I can trust the structured data and reject ungrounded values.

#### Acceptance Criteria

1. WHEN the Validator processes a Cell, THE Validator SHALL compute a Faithfulness_Score for that Cell by comparing the Cell value against the Source content referenced by the Cell's Source_Location.
2. THE Validator SHALL record the Faithfulness_Score in the range 0.0 to 1.0 for each Cell.
3. WHERE the LLM_Engine is active, THE Validator SHALL operate in Full_Grounding_Mode using an LLM-as-judge to compute the Faithfulness_Score.
4. WHERE no LLM_Credential is available, THE Validator SHALL operate in Degraded_Grounding_Mode using embedding or string similarity to compute the Faithfulness_Score.
5. WHEN the Validator records a Faithfulness_Score, THE Validator SHALL record which grounding mode produced it.
6. IF a Row contains a Cell whose Faithfulness_Score is below the Grounding_Threshold, THEN THE Validator SHALL flag that Row.
7. WHERE the Pipeline Configuration sets the rejection mode to reject, THE Validator SHALL exclude flagged Rows from the emitted output and record each excluded Row with its Source identifier.
8. WHERE the Pipeline Configuration sets the rejection mode to retain, THE Validator SHALL include flagged Rows in the emitted output with a flag indicator.
9. THE Validator SHALL accept the Grounding_Threshold as a value in the range 0.0 to 1.0 through the Pipeline Configuration.
10. WHEN the Validator computes a Faithfulness_Score for a Cell, THE Validator SHALL attach the Source_Location used in the comparison to that Cell as part of its Provenance.

### Requirement 8: Tabular Output Emission with Lineage

**User Story:** As a data analyst, I want clean tabular output in standard formats with a lineage column, so that I can feed the data to an LLM or load it into downstream systems while retaining provenance.

#### Acceptance Criteria

1. THE Emitter SHALL write validated Rows to a tabular output in DataFrame, Parquet, and SQL formats as selected in the Pipeline Configuration.
2. WHEN the Emitter is invoked and no validated Rows are available, THE Emitter SHALL write an output containing the Target_Schema columns and zero data Rows.
3. WHEN the Emitter writes output, THE Emitter SHALL include a Lineage_Column carrying the Provenance for each Row.
4. THE emitted output columns SHALL correspond to the fields defined in the Target_Schema.
5. WHEN the Emitter writes a Cell, THE Emitter SHALL include the Faithfulness_Score for that Cell in the Provenance.
6. WHEN the Emitter writes output, THE Emitter SHALL record which extraction engine (Deterministic_Engine or LLM_Engine) produced the Rows.
7. IF the configured output destination is inaccessible, THEN THE Emitter SHALL record a write error containing the destination and the failure reason, regardless of whether Rows are available to write.

### Requirement 9: Human-in-the-Loop Review and Correction Feedback

**User Story:** As a reviewer, I want to inspect and correct flagged rows, with my corrections feeding back into the schema and prompts, so that extraction quality improves over time.

#### Acceptance Criteria

1. WHEN the Validator flags a Row, THE Pipeline SHALL add that Row to the Review_Queue together with its Provenance.
2. WHEN a Reviewer submits a Correction to a Cell, THE Pipeline SHALL update that Cell value and record the Correction with the Reviewer identifier and a timestamp.
3. WHEN a Reviewer approves a flagged Row, THE Pipeline SHALL include that Row in the emitted output without further validation.
4. WHEN a Reviewer submits a Correction, THE Pipeline SHALL store the Correction in a feedback record associating the original Cell value, the corrected Cell value, and the Source_Location.
5. WHERE feedback-driven prompt refinement is enabled in the Pipeline Configuration, THE Extractor SHALL incorporate stored Corrections into subsequent extraction prompts.

### Requirement 10: Plugin and Extensibility Architecture

**User Story:** As a third-party developer, I want to register custom connectors, parsers, extractors, validators, and emitters, so that I can extend the framework for my data sources and formats.

#### Acceptance Criteria

1. THE Framework SHALL expose extension interfaces for Connectors, Parsers, Extractors, Validators, and Emitters.
2. WHEN a Plugin is registered with the Framework, THE Framework SHALL make that Plugin available for selection through the Pipeline Configuration.
3. WHEN a Plugin is submitted for registration, THE Framework SHALL validate that the Plugin implements the methods required by its extension interface before completing registration.
4. IF a Plugin submitted for registration does not implement the methods required by its extension interface, THEN THE Framework SHALL reject the registration and raise a registration error identifying the Plugin and the missing methods.
5. WHERE a Plugin and a built-in component both declare support for the same Source type or content type, THE Pipeline SHALL select the component specified in the Pipeline Configuration.

### Requirement 11: Observability

**User Story:** As a data engineer, I want structured events for each processing step, so that I can monitor, debug, and audit pipeline runs.

#### Acceptance Criteria

1. WHEN the Pipeline executes a phase for a Source, THE Pipeline SHALL emit an Observability_Event recording the phase name, the Source identifier, the start time, the completion time, and the outcome.
2. WHEN the Pipeline records an error in any phase, THE Pipeline SHALL emit an Observability_Event with severity error containing the failure reason.
3. THE Framework SHALL expose emitted Observability_Events through a logging interface configurable in the Pipeline Configuration.
4. WHEN the Pipeline completes processing a Corpus, THE Pipeline SHALL emit an Observability_Event summarizing the count of Sources processed, Rows emitted, Rows flagged, and Rows rejected.
5. WHEN the Pipeline completes processing a Corpus and at least one Source was processed successfully, THE Pipeline SHALL report a Corpus outcome of success even when errors were recorded for individual Sources.

### Requirement 12: Configuration

**User Story:** As a user, I want to control pipeline behavior through configuration, so that I can tune the pipeline without modifying code.

#### Acceptance Criteria

1. THE Pipeline SHALL accept a Pipeline_Configuration, expressed as a Locusfile, that specifies the data source, plugin selection, optional Target_Schema and its mode, optional LLM provider and model selection, retry limits, the Grounding_Threshold, the rejection mode, deduplication settings, and output format.
2. WHERE a configuration value is not supplied for a setting that has a default, THE Pipeline SHALL apply the documented default value for that setting.
3. IF the Pipeline_Configuration contains a value outside the permitted range for a setting, THEN THE Pipeline SHALL raise a configuration error identifying the setting and the permitted range.
4. WHEN the Pipeline starts a run, THE Pipeline SHALL validate the Pipeline_Configuration before processing any Source.
5. THE Pipeline SHALL require only the data source and the image reference; all other settings SHALL be optional with documented defaults.

### Requirement 13: Dual-Engine Operation and Activation

**User Story:** As a privacy-conscious user, I want the pipeline to run deterministically by default and only use an LLM when I explicitly provide a credential, so that I control whether my data is sent to an external provider.

#### Acceptance Criteria

1. THE Extractor SHALL provide both a Deterministic_Engine and an LLM_Engine within a single image.
2. WHERE no LLM_Credential is available at run time, THE Extractor SHALL use the Deterministic_Engine.
3. WHERE an LLM_Credential is available at run time, THE Extractor SHALL activate the LLM_Engine.
4. WHEN the Extractor determines its engine at the start of a run, THE Extractor SHALL detect LLM_Credential availability by a local presence check without contacting any hosted Locus service.
5. WHEN the Deterministic_Engine is used and no LLM_Credential is available, THE Pipeline SHALL surface a notice that the LLM_Engine is available and how to enable it.
6. WHEN the LLM_Engine is activated, THE Pipeline SHALL present a consent notice identifying the configured provider before transmitting any Source content to that provider.

### Requirement 14: LLM Guardrails and Hybrid Ordering

**User Story:** As a data engineer, I want the LLM constrained to a bounded role with deterministic processing taking precedence, so that the LLM cannot make unconstrained decisions about my data.

#### Acceptance Criteria

1. WHEN the LLM_Engine is active, THE Extractor SHALL perform structural processing (parsing, layout detection, table detection, type coercion, deduplication) with deterministic Python before invoking the LLM.
2. WHEN the LLM_Engine is active, THE Extractor SHALL restrict the LLM to mapping content to Target_Schema fields and SHALL NOT delegate structural processing to the LLM.
3. WHEN the LLM_Engine produces a Cell, THE Extractor SHALL constrain the output to the Target_Schema and SHALL retry on a schema violation up to the configured retry limit.
4. IF an LLM-produced value conflicts with a deterministic result for the same Cell, THEN THE Extractor SHALL flag the affected Row rather than silently overriding the deterministic result.
5. WHEN the LLM_Engine produces a Cell, THE Validator SHALL subject that Cell to the grounding contract defined in Requirement 7.

### Requirement 15: LLM Credential Handling and Provider Routing

**User Story:** As a user, I want to supply my LLM credentials locally and switch providers easily, so that my keys stay on my machine and I am not locked to one provider.

#### Acceptance Criteria

1. THE Framework SHALL resolve an LLM_Credential at run time from local sources only, in the precedence order: a referenced environment file, an environment variable, and the local OS keyring.
2. THE Framework SHALL NOT transmit an LLM_Credential or user data to any hosted Locus service.
3. IF the Locusfile contains a literal value that matches the pattern of a raw provider key, THEN THE Framework SHALL reject the Locusfile and raise a configuration error instructing the user to use a reference instead.
4. WHEN a project is initialized, THE Framework SHALL ensure the environment file is listed in the project's ignore file, creating the ignore file if absent.
5. IF the referenced environment file is tracked by version control at run time, THEN THE Framework SHALL halt the run and raise an error instructing the user to untrack it.
6. THE Provider_Router SHALL route LLM requests to the provider and model specified in the Pipeline Configuration.
7. THE Provider_Router SHALL operate in-process and SHALL NOT require the user to install or run a separate provider-router service.
