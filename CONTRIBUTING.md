# Contributing to Locus

Thanks for your interest. Locus is in early design — requirements for both layers are
defined, and implementation has not started yet. Contributions of ideas, feedback, and
(soon) code are welcome.

## Where things are

- **Layer 1 — engine:** [`.kiro/specs/unstructured-to-tabular-etl/`](.kiro/specs/unstructured-to-tabular-etl/)
- **Layer 2 — runtime / hub:** [`.kiro/specs/locus-image-runtime/`](.kiro/specs/locus-image-runtime/)
- **Image catalog & build order:** [`.kiro/specs/locus-image-runtime/image-catalog.md`](.kiro/specs/locus-image-runtime/image-catalog.md)
- **Architecture & decision log:** [`.kiro/specs/unstructured-to-tabular-etl/architecture-notes.md`](.kiro/specs/unstructured-to-tabular-etl/architecture-notes.md)

Start by reading the requirements for the layer you want to work on.

## How to contribute

1. **Open an issue first** for anything non-trivial, so the approach can be discussed
   before code is written.
2. **Fork and branch.** Create a feature branch off `main` (for example
   `feat/<short-name>` or `fix/<short-name>`). Do not commit directly to `main`.
3. **Keep changes focused.** One logical change per pull request.
4. **Open a pull request** with a clear description of what changed and why, and link the
   related issue.

## Guidelines

- Match existing conventions and keep the two layers cleanly separated (the engine must
  not depend on the runtime/hub).
- Never commit secrets. LLM provider keys stay local (`.env`, environment variables, or
  the OS keyring) and `.env` is gitignored.
- Update the relevant spec or docs when a change affects documented behavior.
- Regenerate the architecture diagram with
  [`docs/generate_architecture_diagram.py`](docs/generate_architecture_diagram.py) if you
  change it (see [`docs/requirements-diagram.txt`](docs/requirements-diagram.txt)).

## License

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).
