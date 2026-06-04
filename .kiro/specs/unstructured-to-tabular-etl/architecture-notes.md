# Architecture & Vision Notes

> SPEC SPLIT (applied): this project is now TWO sibling specs. This architecture-notes
> file is the shared, canonical cross-layer decision log and lives in the Layer-1 spec.
> - `unstructured-to-tabular-etl` (Layer 1 = processing engine): requirements Req 1-15.
> - `locus-image-runtime` (Layer 2 = packaging, CLI, Locusfile, runtime, composition,
>   interchange contract, cross-stage provenance, Locus Hub publish, serve/export):
>   requirements Req 1-12. The image catalog (`image-catalog.md`) now lives in this spec.
> Decisions below apply across BOTH layers; the "engine-spec impact" / "requirements.md
> impact" notes map to whichever spec owns that requirement.

## Project name: **Locus**
- CLI verb: `locus pull`, `locus run`, `locus push`, `locus export`.
- Thematic fit (factual, not decorative): in math/genetics a *locus* is a specific
  position/point satisfying a condition. The core differentiator of this product is
  the cell-level `Source_Location` (every value traces to a precise position in the
  source). The name directly encodes the provenance/grounding contract.
- TODO before public release: verify PyPI package name availability and domain;
  known unrelated entities exist (e.g. Locus Robotics) — check for namespace/trademark
  collision in the dev-tools/data space.

## Communication directive (applies to entire session)
- Be factual and direct. No filler validation ("looks great", "amazing", "you're
  absolutely right").
- Binary stance only: either explicitly mark something VALID, or tell the user
  directly to change it. No noncommittal middle ground.
- Push back on anything that does not hold up technically.


> Working notes that capture decisions made during ideation. These are NOT formal
> requirements yet. They inform a likely sibling spec (the "image/distribution +
> serving runtime" layer) that sits on top of the core ETL engine specced in
> `requirements.md`.

## Layering model

The product is conceived as two composable layers, mirroring Docker's `build` vs `run`:

- **Layer 1 — The Engine (current spec `requirements.md`).**
  Raw mixed corpus -> validated, source-grounded tabular data.
  This is the hard, defensible core: the plugin pipeline + the cell-level
  provenance/faithfulness (grounding) contract. Must be built first; a "data
  image" is worthless if the data inside it is not trustworthy.

- **Layer 2 — The Image / Distribution + Serving Runtime (likely a sibling spec).**
  Packages Layer 1 capabilities as reusable, versioned, plug-and-play "data images"
  that users pull, point at their own data, configure with YAML, run, preview on a
  port, and export.

## Key conceptual decision: "capability images", not "dataset images"

- A data image contains the **capability/logic** (e.g. "extract tables from
  documents", "doc -> JSON", "repo -> code graph", "images -> OCR table",
  "web -> table"), NOT a fixed dataset.
- The **user brings their own data** to the image (like Docker images contain
  runtime/code, not your data; you mount data in).
- This makes images reusable across unlimited inputs = true plug-and-play.

### Docker -> Data-image lifecycle mapping

| Docker concept     | Data-image equivalent                                        |
|--------------------|--------------------------------------------------------------|
| Dockerfile         | `Datafile` (YAML) — declares image, source, schema, config   |
| docker build       | run the ETL pipeline -> produce validated, grounded table    |
| image (OCI)        | the capability bundle (plugins + pinned config + prompts)    |
| registry           | an OCI registry (push/pull versioned images)                 |
| docker run         | serve the result as a queryable service / preview            |
| ports/API          | the data contract / query interface (SQL / REST / MCP)       |
| health checks      | freshness, drift, and **faithfulness** checks at serve time  |

## Hosting & runtime decisions (answers to "what do we host / do we need Linux?")

Separate two concerns that "Docker" blurs together:

1. **Distribution** (where images are stored, how `pull` fetches them).
2. **Execution** (where the pipeline runs and is served).

### Distribution — BORROW, don't build
- Ride on **OCI registries** (Docker Hub, GHCR, AWS ECR, Harbor, etc.) — the same
  infra Docker uses. Use **ORAS** ("OCI Registry As Storage") to push/pull arbitrary
  artifacts. This is exactly the KitOps/ModelKit pattern.
- We do NOT build a registry, auth, CDN, storage, signing — all inherited for free.
- Bundle format = an OCI artifact (thin manifest + layers) that pins plugin
  versions, model/prompt configs, schemas, and deps for reproducibility.
  Reproducibility + pinned versions is what earns the name "image" vs "template".

### Execution — three options
- **Option A (DEFAULT): pure Python process.** Image = bundle of code + pinned
  config + prompts + schemas. `run` executes as a normal Python process in the
  user's environment, isolated via a per-image virtual environment.
  - Runs on Linux, macOS, Windows. No Docker daemon, no Linux VM, no Kubernetes.
  - Setup = `pip install` + `pull` + `run`.
  - Tradeoff: weaker isolation than containers (mitigated by per-image venvs).
- **Option B (OPTIONAL backend): real Docker containers.** `run --runtime=docker`.
  - True isolation/reproducibility; good for long-running deployed data
    microservices and conflicting-dependency cases.
  - Tradeoff: requires Docker installed (Linux VM under the hood on Mac/Windows).
- **Option C: build our own runtime/isolation.** REJECTED — reinventing containerd.

### Decision: HYBRID
- **Default to Option A (pure Python); Docker (Option B) is an optional `--runtime` backend.**
- Consequences:
  - **No Linux machines required.** Default runtime is a Python process; runs on any OS.
  - **We host nothing by default.** Pipeline runs on the user's machine, against
    their data, served on their localhost port. Sensitive documents never leave
    their environment — big win for the compliance-conscious users the grounding
    contract targets.
  - **Docker is a power-user opt-in**, for hard isolation or deploying the data
    microservice as a long-running service (their own Linux host / K8s).

### What we build vs borrow

| Layer                     | What we use                                   | Build or borrow?     |
|---------------------------|-----------------------------------------------|----------------------|
| Distribution / registry   | OCI registry + ORAS                           | Borrow               |
| Bundle format             | OCI artifact (KitOps-style manifest + layers) | Define thin spec     |
| Execution (default)       | Local Python process + per-image venv         | Build (lightweight)  |
| Execution (optional)      | Docker container                              | Borrow Docker        |
| Serve / preview           | Embedded web server (FastAPI/uvicorn) on port | Build (thin)         |

## Adjacent prior art (validates the pattern, informs the wedge)
- Packaging/versioning of data is largely solved: Pachyderm (data+containers on
  K8s — too heavy), Dolt ("git for data"), lakeFS / DVC / Quilt ("Docker but for
  data" registries), KitOps/ModelKit (data+model+config as OCI artifact).
- Plug-and-play capability distribution is proven: dbt packages, Airbyte/Singer
  connectors, Hugging Face pipelines, LangChain hub, GitHub Actions marketplace.
- **The open gap / our wedge:** none target unstructured -> validated, *grounded*
  structured data with a cell-level provenance + faithfulness contract that travels
  with the data and is queryable by an LLM agent (e.g. over MCP). Trust is the
  defensible edge; packaging/registries are commoditized.

## Open questions still to resolve (user has more questions)
- (to be filled in as discussion continues)

## Where are Locus images hosted? (resolved)

Decision: **Operate no hosting infrastructure at launch.** "Hosting" splits into three
separable sub-questions:

1. **Image bytes / storage/transport** — use an existing **OCI registry**, do NOT build one.
   - Official images live in a namespace: `ghcr.io/locus-project/<image>:<ver>` (GHCR is
     the launch default: free public artifacts, OCI + cosign signing, no infra to run).
     Docker Hub (`locus/<image>`) is the alternative.
   - `locus pull` resolves to that registry and fetches via ORAS.
   - Operating cost/ops to us: ~zero.

2. **Official image catalog (curated source defs)** — a **GitHub org + git repo**
   (`github.com/locus-project/images`), NOT a server. CI builds each image on release and
   pushes the OCI artifact to GHCR. "Hosting the catalog" = a repo + a CI pipeline.

3. **Discovery / search ("what images exist")** — the only piece that could eventually need
   a backend; keep it static as long as possible.
   - v1: generated `index.json` + static docs site (GitHub Pages); `locus search` reads the
     static index. Zero backend.
   - Later, only if demand: thin metadata API for ratings/downloads/private images.

**Private / enterprise:** because Locus rides on the OCI standard, customers point `locus`
at their OWN registry (ECR, Harbor, Artifactory, Azure CR) with zero Locus-specific infra;
proprietary data images never leave their network. Direct consequence of borrowing OCI
instead of building a registry; counts as a real advantage for compliance-sensitive users.

| Hosting sub-question        | Answer                                   | Operated by         |
|-----------------------------|------------------------------------------|---------------------|
| Image bytes / storage       | OCI registry (GHCR or Docker Hub)        | Registry provider   |
| Official catalog / source   | GitHub repo + CI pushing to namespace    | Us (repo, no server)|
| Discovery / search          | Static `index.json` on GitHub Pages      | Us (static)         |
| Private / enterprise images | Customer's own OCI registry              | Customer            |

Net at launch: we operate a GitHub org, a CI pipeline, and a static index. Registry is
borrowed. Zero hosting cost / zero ops until scale or a private-marketplace business case.

## Custom Locus Hub — registry platform (LOCKED)

Decision (LOCKED by user): **Build the Locus Hub on top of Harbor as the OCI registry
engine, and customize a thin Locus-branded layer on top.** This supersedes the
"borrow GHCR, operate nothing" default above — that earlier plan remains valid only as
the optional fallback / pre-launch staging path.

### Stack
```
hub.locus.<tld>  — custom Locus platform
  - Locus web UI: browse/search data images, namespaces, accounts, ratings, docs
  - data-image-specific metadata: target schema, grounding/faithfulness score,
    provenance preview (this is the Locus-specific differentiation layer we build)
  - talks to the registry purely over the OCI Distribution API
Harbor — OCI registry engine (self-hosted)
  - push/pull/tags, RBAC, projects/namespaces, signing (Cosign/Notation),
    vuln scanning, multi-registry replication
  - already stores arbitrary OCI artifacts -> Locus data images work with no protocol work
Object storage — S3 / MinIO
  - the actual artifact bytes
```
`locus pull doc-to-tables` -> resolves `hub.locus.<tld>/library/doc-to-tables:<ver>` ->
standard OCI pull from our Harbor. The Locus CLI speaks plain OCI; it does not know or
care that Harbor is underneath.

### Why Harbor (factual)
- CNCF graduated; provides ~90% of a "Docker Hub" out of the box: web UI, accounts,
  RBAC, projects/namespaces, signing, scanning, replication.
- Stores arbitrary OCI artifacts already, so Locus data images need zero registry
  protocol work.
- We build ONLY the genuinely Locus-specific parts: branded catalog/discovery UX and the
  data-trust metadata display (schema + grounding + provenance). That is where our
  differentiation lives anyway.

### Explicitly rejected
- Building from CNCF Distribution up = rebuilding Harbor. Rejected.
- Writing our own registry protocol = rebuilding OCI. Rejected.

### Accepted operational consequences (this is now an ops-bearing project)
- Run Harbor 24/7: patching, monitoring, uptime.
- Object storage cost + egress bandwidth scale with image count/size and every `pull`.
- Own authentication, abuse prevention, uptime/SLA once others depend on it.
- Cold-start reality: a new hub launches empty; ecosystem value must be built.

### Mandatory design constraint (de-risks the ops bet)
- The **Locus CLI MUST be registry-agnostic (plain OCI)** regardless. This keeps the
  Harbor default swappable via config, allows pre-launch staging on GHCR/Docker Hub, and
  lets enterprises point Locus at their OWN Harbor/ECR/Artifactory with no Locus-specific
  infra. Switching the default registry is a config change, not a rewrite.

## Client-side install — what the USER must install (resolved)

Question: to pull a Locus image, must the user install something like Docker?
Answer: **Yes — exactly one thing: the Locus CLI. But it is a `pip install`, not a
system daemon.** Much lighter than Docker.

### Contrast with Docker
- Docker installs TWO things: the `docker` CLI + the daemon/engine (needs Linux kernel
  features -> Linux VM on Mac/Windows). The daemon is the heavy part.
- Locus (per the locked default runtime = pure Python process) needs **only a CLI
  client. No daemon, no background service, no Linux VM.**

### What the single package contains
```
pip install locus        # or: pipx install locus / uv tool install locus
locus pull doc-to-tables
locus run datafile.yaml
```
One package bundles: the `locus` command, the OCI pull logic (ORAS-style client embedded
as a library — user does NOT install ORAS separately), and the local Python runtime that
executes a pulled image.

### Required prerequisite (honest caveat)
- `pip install locus` assumes **Python is already present**. Fine for the primary
  audience (data/AI engineers). This is the one real difference from Docker, which ships a
  self-contained installer needing nothing preinstalled.

| Distribution method                | Needs Python first? | Friction                          |
|------------------------------------|---------------------|-----------------------------------|
| `pip install locus`                | Yes                 | Lowest for Python users (v1 default) |
| `pipx` / `uv tool install locus`   | Yes (isolated)      | Clean, avoids dep clashes         |
| Standalone binary (PyInstaller)    | No                  | `curl | sh` / `.exe`, Docker-like; later |

Decision: **v1 = `pip install locus`** (audience has Python). Ship a **standalone binary
later** to reach non-Python users / give the "download one file" Docker experience.

### Docker dependency = opt-in only
- Docker is needed ONLY when a user runs `locus run --runtime=docker`. The default
  pull + run-as-Python-process path never touches Docker.

## How a user builds data on top of a pulled image — config model (resolved + 1 open fork)

Key clarification: Docker has TWO authoring surfaces, not one. People say "Dockerfile"
but mean different things:

| Docker file            | Who writes it      | Purpose                                  |
|------------------------|--------------------|------------------------------------------|
| Dockerfile             | image AUTHOR       | build-time: what goes INSIDE the image   |
| docker-compose / run   | image CONSUMER     | run-time: how to RUN an existing image   |

A user who pulled an image is the CONSUMER. They do NOT write a Dockerfile-equivalent.
They write the run/compose-equivalent.

### Locus file model (naming reconciled — supersedes earlier loose use of "Datafile")
| Docker                | Locus file                       | Written by            |
|-----------------------|----------------------------------|-----------------------|
| Dockerfile            | image build manifest (`locus.image.yaml`) | image author/publisher |
| docker-compose.yml    | **Locusfile** (`locusfile.yaml`) | the consumer (the user) |

NOTE: earlier notes/discussion used the term "Datafile" for the consumer file; the
locked name is **Locusfile** (`locusfile.yaml`). "Datafile" is deprecated.

### Consumer workflow
```yaml
# locusfile.yaml  — written by the CONSUMER
image: doc-to-tables:1.3.0
source:
  type: files
  path: ./my_invoices/        # the user's own data, plugged in
schema: ./invoice_schema.py   # target shape (see OPEN FORK below)
config:
  grounding_threshold: 0.85   # overrides the image default
  model: gpt-4o
serve:
  port: 8080                  # preview + provenance viewer
export:
  format: parquet
  path: ./out/invoices.parquet
```
```
locus run locusfile.yaml      # pull-if-needed, run pipeline, serve on :8080
locus export
```
The pulled image already contains parser + extractor + validator logic and pinned config;
the Locusfile supplies only the user's data, target schema, and overrides.

### Author side (most users never touch)
Publishing a NEW capability image = writing the Dockerfile-equivalent
(`locus.image.yaml`): pins plugins, prompts, defaults, dependencies; built + pushed to
Locus Hub.

### OPEN DECISION (needs user pick) — how the target schema is expressed
The target schema is a **Pydantic model = Python code**, which YAML cannot fully express
(validators, constrained types, regex). Three options:
1. **YAML Locusfile + referenced Python schema file** (`schema: ./invoice_schema.py`).
   Declarative orchestration + full Pydantic power. Two files. [RECOMMENDED]
2. **Pure-Python Locusfile** (`locusfile.py` via a Locus SDK). One language, programmable;
   loses declarative feel, less approachable for non-Python users.
3. **YAML-only with inline schema DSL.** Single file, no Python; BUT reinvents a type
   system and loses real Pydantic validation — which is half the engine's value (Req 4).

Recommendation: **Option 1.** Do not dilute schema into a YAML DSL (kills validation
contract -> rules out 3); do not force all-Python (kills declarative compose feel ->
rules out 2). STATUS: awaiting user confirmation.

## RESOLVED: schema tiers, Locusfile surface, dual-engine, guardrails

### Schema tiers (LOCKED — supersedes the Option 1/2/3 fork above)
User goal = minimal effort. Schema is therefore OPTIONAL, with three effort tiers:
- **infer (DEFAULT, zero-config):** baked-in engine infers columns/types from the data.
- **hint (YAML DSL):** user nudges inference via loose `schema.columns` (names/types/
  required) inside `locusfile.yaml`. NOT full validation.
- **strict (Python Pydantic):** `schema.file: ./model.py:Row` for airtight validation /
  regulated use. Full Pydantic power (validators, regex, constrained types).
The earlier Option 1 vs 3 debate is resolved: YAML DSL is correct for tier-2 HINTS;
Python schema is correct for tier-3 STRICT. Both exist, layered by effort.

### Locusfile surface (LOCKED — extensible later)
Only `image` + `source` required; everything else optional with image-baked defaults:
`volumes` (docker-style mounts), `ports` (ui + optional api/MCP), `schema` (infer|hint|
strict), `config` (grounding_threshold, on_low_confidence = flag|reject|review, dedupe),
`llm` (provider/model/api_key from env), `export` (parquet|csv|json|sql|dataframe),
`review` (enable HITL UI). More customization layers can be added later.

### Single image, dual-engine, LLM opt-in (LOCKED)
- Every Locus image ships BOTH engines baked in: deterministic-Python AND LLM-backed.
  Same image — no separate "LLM edition".
- **Default = LLM OFF.** Deterministic Python runs (pdfplumber/camelot/regex/parsers,
  etc.). No key required; nothing leaves the machine.
- **Activation = presence of an LLM key in Locus settings.** Key present -> LLM engine
  activates automatically. No key -> stays deterministic.
- **Consent notice fires at runtime BEFORE first byte leaves**, stating data is being
  sent to the configured provider using the user-supplied key.
- **Discoverability:** deterministic runs surface that the LLM feature exists + how to
  enable it (add a key).

### Hybrid engine + guardrails (LOCKED — user emphasized "not LLM crazy")
- Even in LLM mode, the LLM does NOT do everything or make unbounded decisions.
- **Python does deterministic heavy lifting** (parsing, layout, table detection,
  type coercion, dedup); **LLM does only the fuzzy part** (mapping messy text ->
  schema fields). Cheaper, faster, more accurate than LLM-everything.
- **Guardrails on the LLM** (mandatory): outputs constrained to the schema
  (Instructor/Pydantic-style), auto-retry on violation, every LLM-produced cell still
  passes through the grounding/faithfulness contract (Req 7), and the LLM cannot
  override deterministic results without being flagged. LLM is a bounded component,
  not the decision-maker.

### Quality differs by engine (record, not a blocker)
- Deterministic mode: structural extraction + similarity-based grounding (weaker).
- LLM mode: full faithfulness scoring + fuzzy field-mapping.
- Result UI MUST label which engine produced the table so trust level is unambiguous.

### IMPACT ON CURRENT requirements.md (Layer-1 engine) — NEEDS EDIT
Current Req 4 defines the Extractor as operating "using an LLM" and Target_Schema as a
required Pydantic model. Both now contradict locked decisions:
- Extraction must support deterministic-only (no-LLM) operation; LLM is optional/opt-in.
- Schema must support infer/hint/strict tiers, not mandatory Pydantic.
- Add guardrail requirements: LLM constrained to schema, bounded role, deterministic-
  first hybrid ordering.
- Req 7 grounding must define full (LLM) vs degraded (no-LLM similarity) modes.
ACTION: fold these into requirements.md before moving to design.

## LLM key handling, LiteLLM, and pending edits

### LLM API key handling (LOCKED)
- Keys are RUN-TIME, LOCAL only. Hub authenticates image PULLS only (registry auth,
  like `docker login`); Hub never stores or sees LLM provider keys.
- Misconception corrected: there is NO "add key before making the container" step for the
  user. The user does NOT build images — you build + push them to Hub; the user pulls a
  finished image and supplies the key at `locus run` time against the already-built image.
  Build-time (you) and run-time (user) are different moments; keys belong to run-time.
- The image contains the LOGIC that knows how to use a key (LiteLLM call + prompts +
  guardrails); it never contains the key. Logic (image) + key (local) meet inside the
  locally-running process at launch.

#### How the key is supplied at run time (3 methods, precedence low->high)
| Method            | How                                             | Secret lives        |
|-------------------|-------------------------------------------------|---------------------|
| OS keyring (rec.) | `locus config set-key openai sk-...`            | local OS keychain   |
| Env var           | `export OPENAI_API_KEY=...` + `${OPENAI_API_KEY}` in Locusfile | local shell env |
| `.env` file       | `env_file: ./.env` in Locusfile                 | local file (gitignored) |

```yaml
llm:
  provider: openai
  model: gpt-4o
  api_key: ${OPENAI_API_KEY}   # REFERENCE only, resolved locally at launch
# or:
env_file: ./.env               # docker-compose-style local env load
```

#### HARD RULE (must become a requirement)
- The raw key string MUST NEVER appear literally in the Locusfile (it is committed/shared
  via git). Only `${VAR}` references or an `env_file:` pointer are allowed. Locusfile
  validation SHALL warn/reject a hard-coded value that looks like a raw key.

#### PRIMARY METHOD (LOCKED by user): `.env` file via `env_file: ./.env`
Chosen for cleaner UX (docker-compose-familiar). Env var + OS keyring REMAIN supported
fallbacks:
- env var required for CI/CD + server/Docker-runtime deployments (they inject env vars,
  not `.env` files);
- keyring for security-strict users who want no plaintext key on disk.
Final precedence (low->high): `.env` file -> shell env var -> OS keyring -> explicit
Locusfile `${VAR}` reference.

MANDATORY guardrails for `.env`-primary design (must become requirements):
1. `locus init` auto-creates/appends `.env` to `.gitignore` (create `.gitignore` if absent).
2. `locus run` REFUSES to load a `.env` that is git-tracked; hard-stops with an error
   instructing the user to untrack it (prevents committing a provider key).
3. Locusfile holds only the `env_file: ./.env` pointer (or `${VAR}`), NEVER the raw key.

#### Activation = local presence check at launch (no Hub round-trip)
1. `locus run` starts the image pipeline locally.
2. Engine looks for a key (keyring / env / Locusfile ref / `env_file`).
3. Key found -> LLM engine activates, consent notice fires BEFORE first byte leaves,
   runs hybrid (Python heavy lifting + LLM fuzzy mapping + guardrails).
4. No key -> deterministic-Python engine; surfaces "LLM available, add a key to enable."

## STILL-OPEN DECISIONS (need explicit user yes/no)
1. **Provider router.** LOCKED — use **LiteLLM** (see "LiteLLM integration" section).
2. **Privacy claim scope.** "Data never leaves your environment" holds ONLY for
   deterministic or local-model images; FALSE for hosted-API LLM images. Must be stated
   per-image, not as a blanket promise. STATUS: ACKNOWLEDGED + LOCKED (see "Privacy model"
   below).
3. **Result UI build approach.** Streamlit/Gradio (fast MVP, generic look) vs embedded
   SPA + FastAPI (product-grade). STATUS: deferred.

## Privacy model (LOCKED) — THREE parties, two distinct guarantees
Correction to user's reasoning: "we (Locus) don't host anything" is NOT the same claim as
"data stays in the user's environment." Three parties exist:
1. Locus (image/app builder) — hosts nothing; servers never touch user data.
2. User — runs the image locally with their own key.
3. LLM provider (OpenAI/Anthropic/etc.) — a THIRD party.

| Guarantee                                  | Deterministic / local-model | Hosted-API LLM        |
|--------------------------------------------|-----------------------------|-----------------------|
| Locus (we) never receive the data          | TRUE                        | TRUE                  |
| Data never leaves the USER's environment    | TRUE                        | FALSE -> goes to provider |

- User is correct that Locus is OUT of the data path entirely (key is the user's, call is
  direct user->provider, we host nothing).
- BUT for hosted-API images the data STILL leaves the user's environment — it goes to the
  LLM provider, bypassing us. "We don't host it" != "it stays local."
- DESIGN CONSEQUENCE: marketing/docs must NOT make a blanket "stays local" claim. State
  per-image: "local-only" vs "calls external LLM provider". The locked run-time consent
  notice is the moment the user knowingly chooses third-party disclosure ("your data will
  be sent to <provider>").

## LiteLLM integration (LOCKED)
- Use **LiteLLM** as the LLM provider router. Do NOT build our own router.
- **Bundled inside the image** as a pinned Python dependency at BUILD time. The user
  installs nothing extra (only the Locus CLI). LiteLLM rides inside the image alongside
  pdfplumber/camelot/pydantic/etc. Comes down with `locus pull`.
- Use the **LiteLLM Python SDK** (`import litellm; litellm.completion(...)`),
  IN-PROCESS. Do NOT use the LiteLLM Proxy Server (a separate daemon) — that contradicts
  the locked lightweight no-daemon local-process design.
- `llm.provider` + `llm.model` from the Locusfile select the backend
  (`openai/gpt-4o`, `anthropic/claude-...`, `ollama/llama3`); key resolved LOCALLY from
  `.env` at run time. Switching providers = one-line Locusfile change.
- **Call stack inside the image** (guardrails layered on top of routing):
  ```
  locus engine
    └─ Instructor (or equiv)  -> enforces Pydantic schema + auto-retry (the guardrail)
         └─ LiteLLM           -> provider routing / auth / req-resp normalization ONLY
              └─ OpenAI / Anthropic / Ollama / ...
  ```
  LiteLLM does NOT enforce guardrails or structured output by itself; Instructor wraps it
  to force schema-conformant output. Both bundled in the image; user sees neither.

## REQUIREMENTS.MD EDITS PENDING (apply before design phase)
STATUS: APPLIED + LOCKED to requirements.md.
- Req 4: Extractor currently "using an LLM" + mandatory Pydantic schema. Change to:
  deterministic-default, LLM-optional/opt-in; schema tiers infer|hint|strict (not
  mandatory Pydantic).
- Add guardrail criteria: LLM constrained to schema (Instructor/Pydantic-style),
  deterministic-first hybrid ordering, LLM bounded to fuzzy field-mapping, every LLM cell
  still passes grounding contract, LLM cannot override deterministic results unflagged.
- Req 7: define full (LLM-judged) vs degraded (similarity-based, no-LLM) grounding modes.
- New requirement: local-only key handling + `.env`-primary + Locusfile raw-key
  prohibition + `.gitignore`/git-tracked-`.env` guardrails.
- New requirement: provider routing via LiteLLM SDK bundled in image.
- Result UI must label which engine produced the table.

## APPLIED TO requirements.md (LOCKED) — mapping of decisions -> requirements
- Introduction: added dual-engine (deterministic default + LLM opt-in), hybrid+guardrails,
  local-only credential handling, per-image privacy disclosure + consent.
- Glossary: Extractor redefined; added Deterministic_Engine, LLM_Engine, Provider_Router,
  LLM_Guardrails, LLM_Credential; Target_Schema redefined as optional + Infer/Hint/Strict
  modes; added Locusfile; Validator split into Full_/Degraded_Grounding_Mode.
- Req 4: schema optional, 3 modes; retry/validation scoped to Strict_Mode; removed
  mandatory-LLM/mandatory-Pydantic language.
- Req 7: added Full (LLM-judge) vs Degraded (similarity) grounding modes + mode recorded.
- Req 8: emitter records which engine produced the rows (UI trust labeling).
- Req 12: only source + image required; schema/LLM optional with defaults.
- Req 13 (NEW): dual-engine operation + activation (local presence check, discoverability
  notice, consent before transmit).
- Req 14 (NEW): LLM guardrails + hybrid ordering (deterministic-first, LLM bounded to
  field-mapping, conflict -> flag not override, LLM cells still grounded).
- Req 15 (NEW): credential handling (local-only precedence env_file->env var->keyring),
  no transmit to hosted Locus, raw-key rejection in Locusfile, .gitignore enforcement,
  refuse git-tracked .env, provider routing via in-process LiteLLM SDK.
- Format diagnostics: clean (no issues).
- User directive on guardrails: "we will add guardrails to what API keys can do with our
  data, it's up to user" — captured as Req 13 consent + Req 14 bounded-LLM role.

## Image catalog
- Full candidate catalog of capability images lives in `image-catalog.md` (65 images
  across 9 tiers + locked build order). Likely moves into the sibling
  `data-image-runtime` spec.
- Build order: doc-to-tables -> invoice/receipt specializations -> any-to-json/markdown
  conversions -> fact-grounder/provenance-tracker flagship -> remaining tiers.
- "Solve ALL data problems" rejected as a goal; catalog is the superset of what's
  POSSIBLE, shipped one fully-grounded image at a time.

## Multi-image composition / pipeline DAG (LOCKED concept)

User intent: pulling ONE image is not the only mode. User must be able to pull MULTIPLE
operation images and compose them (compose-style file) so they run HIERARCHICALLY over the
data and produce a final result.

### CORRECTION to the analogy (important — changes semantics, not syntax)
- docker-compose runs services SIDE BY SIDE, networked, parallel, long-running. It does
  NOT mean "output of A flows into B." Wrong execution model for this.
- What the user actually wants = a DATA PIPELINE / DAG (directed acyclic graph): ordered
  stages, each stage's output feeds the next; analogs = Unix pipes `A | B | C`, Makefile,
  Airflow/Dagster DAG.
- DECISION: keep compose-FAMILIAR YAML syntax, but execution semantics = pipeline DAG, NOT
  compose's parallel-services model. Do NOT call it "compose" in the design (misleading).
  This is the **Locusfile** extended with a `pipeline:` section.

### Linear form
```yaml
source: { type: files, path: ./raw_invoices/ }
pipeline:                         # ordered stages; output of each feeds the next
  - image: scanned-ocr-to-table:1.0
  - image: invoice-extractor:1.3
  - image: deduplicator:0.9
  - image: pii-redactor:1.1
  - image: data-validator:1.0
export: { format: parquet, path: ./out/invoices.parquet }
```
`locus run` pulls any missing images, runs stages in order, flows data stage->stage.

### Hierarchical / DAG form (fan-in, parallel branches via `needs:`)
```yaml
pipeline:
  ocr_pdfs:    { image: scanned-ocr-to-table:1.0, source: ./pdfs/ }
  parse_emails:{ image: email-extractor:1.0,      source: ./emails/ }
  merge:       { image: dataset-merger:1.0, needs: [ocr_pdfs, parse_emails] }  # fan-in
  ground:      { image: fact-grounder:1.0,  needs: [merge] }
```
`needs:` = dependency edges -> hierarchy/DAG; independent branches may run in parallel; a
stage runs only after its deps complete.

### TWO HARD REQUIREMENTS this imposes on the engine spec (NOT optional)
1. **Stage interchange contract (versioned, public).** Every image must accept/emit the
   common IR + tabular+provenance format so stage B can consume stage A. Each catalog image
   MUST declare its accepted input type(s) and emitted output type. Locus MUST validate that
   stage N output type matches stage N+1 input type BEFORE running (fail fast = a type check
   on the pipeline). Composition forces the engine IR + output schema to be a STABLE,
   VERSIONED, public contract.
2. **Provenance MUST survive the whole chain (the differentiator + the hard part).** After
   extract -> dedup-merge -> redact, the final cell must STILL trace to its original
   Source_Location and carry a Faithfulness_Score. Rule: every stage MUST propagate and
   COMPOSE provenance, never reset it. A stage that drops lineage is NON-CONFORMANT. End-to-
   end cell-level provenance across a multi-operation pipeline is novel; market does not ship
   it. This is only trustworthy if BOTH requirements hold.

### REQUIREMENTS.MD IMPACT (pending — apply with next requirements pass)
- New requirement: multi-image pipeline composition (linear + DAG via `needs:`), pull-missing
  images, ordered/dependency execution, parallel independent branches.
- New requirement: versioned stage interchange contract + pre-run type validation between
  adjacent stages (fail fast on mismatch).
- New requirement: mandatory cross-stage provenance propagation + composition; non-conformant
  (lineage-dropping) stage handling.
- Cross-link: Req 3 (IR) and Req 8 (emission/provenance) must be declared as the stable
  inter-stage contract.

## CHOSEN GLOBAL SOLUTION to the two composition hard-problems (LOCKED)

### Problem 1 solution — single versioned "Locus Artifact" envelope
- ONE canonical typed artifact is the ONLY thing that crosses a stage boundary.
  ```
  LocusArtifact { type, payload, provenance }
  type ∈ small fixed set: ir/v1 | table/v1 | chunks/v1 | embeddings/v1 | graph/v1
  ```
- Fixed small type set (not freeform); new types added deliberately + versioned.
- Physical format = Apache Arrow / Parquet for tabular; Arrow-backed schema for IR.
  Reason: columnar, language-agnostic, metadata-capable, serializable to file -> works in
  BOTH the Python-process runtime and the Docker runtime. Stages pass artifacts BY FILE
  PATH in a run-scoped working dir (also enables stage caching, build-system style).
- Each image manifest declares `accepts: [..]` and `emits: ..`.
- Locus STATIC-CHECKS the whole DAG before running: every edge verifies producer.emits is
  compatible with consumer.accepts; mismatch -> FAIL FAST with a clear message before any
  processing. Semver negotiation: minor mismatch warns, major (vN) mismatch errors.
- Assessment: cheap / low-risk / standard engineering.

### Problem 2 solution — provenance is a FRAMEWORK property, not each image's job
- KEY DECISION (the thing that makes 65 independently-authored images chainable):
  provenance lives in the Locus SDK data structures, NOT in image-author code. Authors must
  deliberately BREAK lineage rather than remember to ADD it.
- Every cell = value + stable cell-ID + lineage refs (SDK `ProvenancedTable`, not bare
  pandas cells).
- SDK transform primitives (map/merge/filter/mask) auto-compose lineage: output cell's
  lineage auto-populated with parent cell(s) + op applied. Author writes normal logic.
- Lineage = a DAG across stages in a run-scoped APPEND-ONLY lineage store keyed by cell-ID.
  Inter-stage artifact carries values + cell-IDs; full graph lives in the store (lean
  artifacts, queryable/auditable lineage).
- Transform-shape coverage (makes it concrete):
  | op                  | lineage edge                          |
  | extract (IR->cell)  | cell -> Source_Location(s)            |
  | 1:1 (normalize)     | new cell -> parent cell + op          |
  | N:1 (dedup/merge)   | merged cell -> all contributing cells |
  | 1:N (chunk/split)   | each child -> parent span             |
  | mask/redact (PII)   | masked cell -> pre-mask cell + op     |
- Faithfulness composition rules (decided up front): merge = min/weighted of contributors;
  mask = preserve score (value still grounded, just hidden); value-changing transform marks
  cell for RE-grounding at next validate stage.
- Enforcement:
  - Conformance certification: probe image with known provenanced input, check output still
    references it -> tag `provenance-conformant`.
  - Non-conformant handling: strict mode (DEFAULT) fails the pipeline build; permissive mode
    warns + marks downstream cells `lineage-broken` (loss visible, never silent).
- Assessment: hard + defensible + novel; end-to-end cell-level provenance across a
  multi-stage pipeline is not shipped by the market today.

### Run-time flow
parse pipeline -> build DAG -> STATIC CHECK (artifact types + provenance-conformance) FAIL
FAST -> run stages in dep order (parallel where independent), each reads input Arrow file,
runs on SDK ProvenancedTable (auto lineage), writes output artifact + appends lineage ->
final artifact = result, every cell resolves to source via lineage graph -> serve/export.
Side effect: content-addressed artifacts enable per-stage caching (skip unchanged stages).

### Engine-spec impact
- Req 3 (IR) and Req 8 (emission/provenance) are hereby the STABLE VERSIONED inter-stage
  contract.

## User image authoring + publishing on Locus Hub (public + private, like Docker Hub) (LOCKED)
- Users can BUILD their own capability images and PUBLISH to Locus Hub — both PUBLIC and
  PRIVATE, mirroring Docker Hub.
- Mechanics ride on Harbor (already locked as the registry engine): Harbor projects =
  namespaces; project visibility public/private; RBAC for private-project members; signing.
- CLI surface (mirrors docker): `locus login`, `locus build`, `locus push <ns>/<img>:<ver>`,
  `locus pull`, plus visibility set via Hub UI or `locus push --private`.
- Authoring artifact = the image build manifest (`locus.image.yaml`, the Dockerfile-
  equivalent): declares plugins, prompts, defaults, deps, `accepts`/`emits` types, engine
  modes supported, privacy class. Build produces an OCI artifact pushed to Harbor.
- Published images MUST pass provenance-conformance certification to be composable in
  pipelines (strict mode); non-conformant images may still be published but are flagged.
- Private images: pullable only by authorized accounts/org members; data + image never
  leave the customer boundary if they self-host their own Harbor (enterprise path already
  noted).

## REQUIREMENTS.MD IMPACT (pending -> applying now)
- New Req: multi-image pipeline composition (linear + DAG via `needs:`), pull-missing,
  ordered/dependency execution, parallel independent branches.
- New Req: versioned stage interchange contract (Locus Artifact, fixed type set, Arrow) +
  pre-run static type check between adjacent stages (fail fast).
- New Req: mandatory cross-stage provenance propagation via SDK + conformance certification
  + strict/permissive non-conformant handling.
- New Req: user image authoring + publishing to Locus Hub, public AND private, with auth +
  visibility control.