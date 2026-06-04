# Requirements Document

## Introduction

This document specifies Layer 2 of Locus: the packaging, distribution, command-line interface, multi-image composition, and registry concerns that build on top of the Layer 1 processing engine specified in the companion `unstructured-to-tabular-etl` spec.

Locus packages data-processing capabilities (parsing, extraction, cleaning, grounding, conversion, and more) as reusable, versioned **images**. An image contains the processing logic, pinned configuration, prompts, and dependencies; it does not contain data. A user pulls a finished image, points it at their own data through a declarative **Locusfile**, and runs it locally to produce a validated, source-grounded result that can be previewed in a local web UI and exported. Images are distributed through **Locus Hub**, a registry built on Harbor that supports public and private namespaces, and any user can author and publish their own images.

A central capability is **multi-image composition**: a Locusfile can chain several operation images into a pipeline that runs hierarchically (a directed acyclic graph) over the user's data, where the output of one stage feeds the next, producing a single final result. To make composition trustworthy, two contracts are enforced. First, a versioned **stage interchange contract**: a single canonical typed artifact is the only structure that crosses a stage boundary, and the runtime statically validates type compatibility across the whole pipeline before executing anything. Second, **cross-stage provenance propagation**: provenance and faithfulness are framework-managed data structures that compose automatically through every operation, so a final value still traces to its original source location after extraction, merging, and redaction.

The runtime is deliberately lightweight. The default execution model is a local Python process requiring no container daemon and no Linux virtual machine; a Docker-based runtime is an optional backend for isolation or long-running deployments. The Locus client is installed as a single CLI; the user installs nothing else. LLM provider credentials, when used, are supplied locally and never transmitted to any hosted Locus service.

## Glossary

- **Locus_CLI**: The single command-line client the user installs to pull, run, build, publish, and serve Locus images.
- **Image**: A versioned, distributable package containing processing logic, pinned configuration, prompts, dependencies, and a declared interchange contract. It contains no user data.
- **Capability_Image**: An Image that performs one data operation (for example table extraction, format conversion, deduplication, redaction).
- **Image_Manifest**: The build-time authoring document that declares an Image's plugins, prompts, defaults, dependencies, accepted and emitted Artifact_Types, supported engine modes, and privacy class. Building it produces a publishable Image.
- **Locusfile**: The declarative YAML run-configuration file, written by the consumer of one or more Images, that supplies the data source, optional schema, LLM settings, volume mounts, port mappings, output settings, and optional multi-image Pipeline composition.
- **Engine**: The Layer 1 processing engine (specified in `unstructured-to-tabular-etl`) that an Image embeds to perform its operation.
- **Pipeline**: A composition of one or more Stages declared in a Locusfile and executed by the runtime.
- **Stage**: A single Image invocation within a Pipeline; it consumes one or more input Locus_Artifacts and produces an output Locus_Artifact.
- **Pipeline_Graph**: The directed acyclic graph of Stages, where dependency edges determine execution order and permit parallel execution of independent branches.
- **Locus_Artifact**: The single canonical, versioned, typed envelope that is the only data structure permitted to cross a Stage boundary. It carries a declared Artifact_Type, a payload, and Provenance.
- **Artifact_Type**: The declared, versioned type of a Locus_Artifact, drawn from a fixed, deliberately extended set (for example ir, table, chunks, embeddings, graph), each carrying a version.
- **Provenance**: Framework-managed lineage attached to each Cell, combining the originating Source_Location(s) and a Faithfulness_Score, as defined by the Layer 1 engine.
- **Provenance_Conformance**: A certification that an Image propagates and composes Provenance through its operation rather than discarding it; required for an Image to be composable in strict mode.
- **Lineage_Store**: A run-scoped, append-only store, keyed by cell identifier, that records the Provenance graph across all Stages of a Pipeline run.
- **Runtime_Backend**: The execution mechanism for a Stage; either the default local Python process backend or the optional Docker backend.
- **Locus_Hub**: The registry platform, built on Harbor, that stores and serves Images, supporting public and private namespaces with authentication and access control.
- **Namespace**: An ownership scope within Locus_Hub under which Images are published (for example an organization or user account).
- **Registry_Credential**: The authentication token, obtained by logging in to Locus_Hub, that authorizes pulling and pushing Images. It is distinct from any LLM provider credential.
- **Result_UI**: The local web interface served on a mapped port that displays the final result table, per-cell provenance and faithfulness, flagged rows, and the review queue.
- **Run_Workspace**: The run-scoped working directory where intermediate Locus_Artifacts are materialized between Stages.

## Requirements

### Requirement 1: Client Installation and Invocation

**User Story:** As a user, I want to install a single lightweight client and run images without a container daemon, so that I can start processing data with minimal setup on any operating system.

#### Acceptance Criteria

1. THE Locus_CLI SHALL be installable as a single client package without requiring a container daemon or a Linux virtual machine.
2. THE Locus_CLI SHALL run on Linux, macOS, and Windows.
3. WHEN the user runs an Image, THE Locus_CLI SHALL execute it using the local Python process Runtime_Backend by default.
4. WHERE the user selects the Docker Runtime_Backend, THE Locus_CLI SHALL execute the Image inside a container.
5. IF the Docker Runtime_Backend is selected and Docker is unavailable, THEN THE Locus_CLI SHALL raise an error identifying the missing backend and SHALL NOT silently fall back.
6. THE Locus_CLI SHALL bundle the artifact-pull mechanism so that the user is not required to install a separate registry client.

### Requirement 2: Image Pull and Local Cache

**User Story:** As a user, I want to pull versioned images and have them cached locally, so that runs are reproducible and do not re-download unchanged images.

#### Acceptance Criteria

1. WHEN the user pulls an Image by name and version, THE Locus_CLI SHALL retrieve that Image from Locus_Hub and store it in a local cache.
2. WHEN an Image required by a run is already present in the local cache at the requested version, THE Locus_CLI SHALL use the cached Image without re-downloading it.
3. WHEN a Locusfile references an Image that is not present locally, THE Locus_CLI SHALL pull that Image before executing its Stage.
4. IF a referenced Image cannot be found in Locus_Hub, THEN THE Locus_CLI SHALL raise an error identifying the Image name and version.
5. WHERE an Image reference does not specify a version, THE Locus_CLI SHALL apply the documented default version-resolution behavior.

### Requirement 3: Locusfile Run Configuration

**User Story:** As a user, I want to declare what data to process and how to output it in one file with minimal required fields, so that I can run an image with as little configuration as possible.

#### Acceptance Criteria

1. THE Locusfile SHALL require only a data source and an Image reference; all other settings SHALL be optional with documented defaults.
2. THE Locusfile SHALL accept optional volume mounts that map local paths into the run.
3. THE Locusfile SHALL accept optional port mappings for the Result_UI and for an optional query interface.
4. THE Locusfile SHALL accept an optional schema in infer, hint, or strict form as defined by the Layer 1 engine.
5. THE Locusfile SHALL accept optional LLM settings, output format settings, and review settings.
6. WHEN the Locus_CLI starts a run, THE Locus_CLI SHALL validate the Locusfile before executing any Stage.
7. IF the Locusfile is invalid, THEN THE Locus_CLI SHALL raise a configuration error identifying the invalid setting.

### Requirement 4: Local LLM Credential Handling

**User Story:** As a user, I want to supply LLM credentials locally through an environment file, so that my keys stay on my machine and are never sent to a hosted service.

#### Acceptance Criteria

1. THE Locus_CLI SHALL resolve an LLM credential at run time from local sources only, in the precedence order: a referenced environment file, an environment variable, and the local OS keyring.
2. THE Locus_CLI SHALL NOT transmit an LLM credential or user data to any hosted Locus service.
3. IF the Locusfile contains a literal value matching the pattern of a raw provider key, THEN THE Locus_CLI SHALL reject the Locusfile and instruct the user to use a reference instead.
4. WHEN a project is initialized, THE Locus_CLI SHALL ensure the environment file is listed in the project's version-control ignore file, creating that ignore file if absent.
5. IF the referenced environment file is tracked by version control at run time, THEN THE Locus_CLI SHALL halt the run and instruct the user to untrack it.

### Requirement 5: Multi-Image Pipeline Composition

**User Story:** As a data engineer, I want to compose multiple operation images into one pipeline that runs hierarchically over my data, so that I can produce a final result from several chained operations in a single run.

#### Acceptance Criteria

1. THE Locusfile SHALL allow a Pipeline composed of multiple Stages, where each Stage references one Image.
2. WHEN a composed Pipeline is run, THE Locus_CLI SHALL build a Pipeline_Graph from the declared Stages and their dependency edges.
3. WHEN a Stage declares no dependency, THE Locus_CLI SHALL treat the Pipeline's data source as that Stage's input.
4. WHEN a Stage declares one or more dependencies, THE Locus_CLI SHALL provide the output Locus_Artifacts of those dependencies as that Stage's input and SHALL execute the Stage only after all its dependencies have completed.
5. WHERE two or more Stages have no dependency relationship between them, THE Locus_CLI MAY execute those Stages in parallel.
6. IF the Pipeline_Graph contains a cycle, THEN THE Locus_CLI SHALL raise a configuration error identifying the cycle and SHALL NOT execute any Stage.
7. WHEN all Stages have completed, THE Locus_CLI SHALL treat the output of the terminal Stage as the final result for emission and serving.
8. WHERE a Stage's input and Image version are unchanged from a prior run, THE Locus_CLI MAY reuse the cached output Locus_Artifact of that Stage.

### Requirement 6: Stage Interchange Contract and Static Validation

**User Story:** As a data engineer, I want the runtime to verify that chained images are type-compatible before running, so that incompatible compositions fail fast instead of producing corrupt results.

#### Acceptance Criteria

1. THE data crossing any Stage boundary SHALL be a Locus_Artifact carrying a declared, versioned Artifact_Type.
2. THE runtime SHALL define a fixed set of Artifact_Types and SHALL serialize tabular payloads in a columnar, language-agnostic format materialized in the Run_Workspace.
3. THE Image_Manifest of each Image SHALL declare the Artifact_Types the Image accepts and the Artifact_Type it emits.
4. WHEN a composed Pipeline is run, THE Locus_CLI SHALL validate, before executing any Stage, that for every dependency edge the producing Stage's emitted Artifact_Type is compatible with the consuming Stage's accepted Artifact_Types.
5. IF an Artifact_Type compatibility check fails for any edge, THEN THE Locus_CLI SHALL raise a type-mismatch error identifying the two Stages and the incompatible types and SHALL NOT execute any Stage.
6. WHERE a producing Stage emits a version of an Artifact_Type that differs from the consuming Stage's accepted version, THE Locus_CLI SHALL treat a minor-version difference as compatible with a warning and a major-version difference as incompatible.

### Requirement 7: Cross-Stage Provenance Propagation

**User Story:** As a compliance-conscious user, I want provenance and faithfulness to survive every stage of a pipeline, so that a final value still traces to its original source after extraction, merging, and redaction.

#### Acceptance Criteria

1. WHEN a Stage transforms a Cell, THE runtime SHALL compose the resulting Cell's Provenance from the Provenance of the input Cells and the operation applied, rather than discarding prior Provenance.
2. WHEN a Stage merges multiple Cells into one, THE runtime SHALL retain references to every contributing Cell in the merged Cell's Provenance.
3. WHEN a Stage derives multiple Cells from one Cell, THE runtime SHALL reference the originating Cell in each derived Cell's Provenance.
4. WHEN a Stage modifies a Cell value, THE runtime SHALL compose the Faithfulness_Score according to the operation's documented composition rule and SHALL mark a value-changing result for re-grounding by a subsequent validating Stage.
5. THE runtime SHALL record the Provenance graph across all Stages in the Lineage_Store.
6. WHEN the terminal Stage produces the final result, THE runtime SHALL resolve each final Cell's Provenance to its originating Source_Location through the Lineage_Store.
7. WHERE a Stage in a composed Pipeline is not Provenance_Conformant and the Pipeline is in strict mode, THE Locus_CLI SHALL fail the run and identify the non-conformant Stage.
8. WHERE a Stage in a composed Pipeline is not Provenance_Conformant and the Pipeline is in permissive mode, THE Locus_CLI SHALL continue and mark the affected downstream Cells as lineage-broken.

### Requirement 8: Result Serving, Preview, and Export

**User Story:** As a user, I want to view my final result in a local web UI with provenance and export it, so that I can inspect what was produced and use it downstream.

#### Acceptance Criteria

1. WHEN a run completes and a Result_UI port is mapped, THE Locus_CLI SHALL serve the final result on that port.
2. THE Result_UI SHALL display the result rows, each Cell's Faithfulness_Score, the flagged rows, and the originating Source_Location for each Cell.
3. THE Result_UI SHALL indicate which engine mode produced the result.
4. WHEN the user exports the result, THE Locus_CLI SHALL write it in the format selected in the Locusfile.
5. THE Result_UI SHALL operate locally and SHALL NOT require a hosted Locus service.

### Requirement 9: Image Authoring and Building

**User Story:** As an image author, I want to build my own capability image from a manifest, so that I can package a custom operation for reuse.

#### Acceptance Criteria

1. THE Locus_CLI SHALL build a publishable Image from an Image_Manifest.
2. THE Image_Manifest SHALL declare the Image's accepted and emitted Artifact_Types, supported engine modes, and privacy class.
3. WHEN building an Image, THE Locus_CLI SHALL pin the Image's dependency and configuration versions for reproducibility.
4. WHEN building an Image, THE Locus_CLI SHALL certify Provenance_Conformance by verifying that the Image's output retains references to a known provenanced input.
5. IF an Image fails Provenance_Conformance certification, THEN THE Locus_CLI SHALL record the Image as non-conformant.

### Requirement 10: Publishing to Locus Hub with Public and Private Visibility

**User Story:** As an image author, I want to publish my images publicly or privately to Locus Hub, so that I and my organization can reuse and share operations like on a container registry.

#### Acceptance Criteria

1. WHEN an author authenticates to Locus_Hub, THE Locus_CLI SHALL obtain a Registry_Credential that authorizes pull and push operations.
2. THE Locus_CLI SHALL allow an authenticated author to publish an Image to a Namespace the author is authorized to use.
3. THE Locus_Hub SHALL support publishing an Image with public visibility and with private visibility.
4. WHEN an Image is published with private visibility, THE Locus_Hub SHALL restrict pulling of that Image to authorized accounts.
5. WHEN a user pulls an Image, THE Locus_Hub SHALL authenticate the user's authorization to access that Image's Namespace.
6. WHEN an Image is published, THE Locus_Hub SHALL record the Image's declared accepted and emitted Artifact_Types and its Provenance_Conformance status.
7. THE Locus_CLI SHALL permit an organization to publish to and pull from a self-hosted Locus_Hub instance without using any hosted Locus service.
8. THE Registry_Credential SHALL be distinct from any LLM provider credential, and authenticating to Locus_Hub SHALL NOT grant access to LLM provider credentials.

### Requirement 11: Image Discovery

**User Story:** As a user, I want to discover available images and their contracts, so that I can find the right operation and know how to compose it.

#### Acceptance Criteria

1. THE Locus_CLI SHALL provide a command to search for available Images in Locus_Hub.
2. WHEN the user inspects an Image, THE Locus_CLI SHALL report its versions, accepted and emitted Artifact_Types, supported engine modes, privacy class, and Provenance_Conformance status.
3. WHERE an Image is private, THE Locus_CLI SHALL include it in discovery results only for authorized accounts.

### Requirement 12: Runtime Privacy Disclosure

**User Story:** As a privacy-conscious user, I want the runtime to disclose when my data will leave my machine, so that I can make an informed choice before it happens.

#### Acceptance Criteria

1. WHEN a Stage will transmit data to an external LLM provider, THE Locus_CLI SHALL present a consent notice identifying the provider before any data leaves the user's environment.
2. THE Locus_CLI SHALL classify each Image by privacy class as local-only or as calling an external provider, and SHALL surface that classification before a run.
3. THE Locus_CLI SHALL NOT present a blanket data-stays-local claim for a run that includes an Image that calls an external provider.
