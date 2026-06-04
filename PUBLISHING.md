# Publishing Locus to PyPI

The package is build-ready. The distribution name is **`locus-etl`** (the name
`locus` is already taken on PyPI); the installed CLI command is still **`locus`** and
the import packages are `locus` and `locus_engine`.

## What you need to do

1. **Create a PyPI account + API token**
   - Register at https://pypi.org/account/register/
   - Create an API token at https://pypi.org/manage/account/token/ (scope it to the
     project after the first upload, or "entire account" for the first upload).

2. **Build the distributions** (already verified to work):
   ```bash
   uv build
   # produces dist/locus_etl-0.0.1-py3-none-any.whl and .tar.gz
   ```

3. **Upload** (pick one):
   ```bash
   # with uv
   uv publish --token pypi-XXXXXXXX

   # or with twine
   pip install twine
   twine upload dist/* -u __token__ -p pypi-XXXXXXXX
   ```

4. **Verify**:
   ```bash
   pip install locus-etl
   locus version
   locus catalog list
   ```

## Optional: test on TestPyPI first

```bash
uv publish --publish-url https://test.pypi.org/legacy/ --token pypi-TESTXXXX
pip install --index-url https://test.pypi.org/simple/ locus-etl
```

## Notes

- A clean `pip install locus-etl` already runs the full pipeline end-to-end (verified):
  `locus run locusfile.yaml` produces a grounded table with provenance. Heavy/optional
  features are extras: `pip install "locus-etl[pdf,serve,llm,oci]"`.
- If you secure the `locus` name on PyPI later (or pick another), change `name` in
  `pyproject.toml` and rebuild; nothing else needs to change.
- Before a real `1.0.0`, bump `version` in `pyproject.toml` and add a git tag.
