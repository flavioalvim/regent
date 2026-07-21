# Releasing regent-cli

Releases publish to PyPI via **Trusted Publishing** (OIDC) — there is no API
token anywhere in the repo or CI. PyPI mints a short-lived credential for the
exact `(repository, workflow, environment)` tuple at run time.

## One-time setup (owner, PyPI web UI)

Because `regent-cli` already exists on PyPI, add the trusted publisher under the
project's publishing settings (not the pending-publisher form):

1. Go to <https://pypi.org/manage/project/regent-cli/settings/publishing/>.
2. **Add a new trusted publisher → GitHub Actions**:
   - **Owner:** `flavioalvim`
   - **Repository name:** `regent`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi`
3. In GitHub → repo **Settings → Environments**, create an environment named
   `pypi`. Optionally add a required reviewer / branch restriction so a human
   approves each publish.
4. Revoke any legacy PyPI API tokens for this project — they are no longer used.

## Cutting a release

1. Bump the version in **both** `pyproject.toml` and `src/regent/__init__.py`
   (the packaging gate and `test_cli_version_reports_0XX` keep these honest).
2. Land it on `main` (CI must be green).
3. Create a **GitHub Release** whose tag is the version — `v0.8.0` or `0.8.0`
   both work (the workflow strips a leading `v`).

Publishing the release triggers `.github/workflows/publish.yml`:

- **test** — the suite on Python 3.10–3.13.
- **build** — `scripts/gate-package.sh` (suite + `python -m build` +
  `twine check --strict`), then asserts `pyproject` version == release tag.
- **publish** — `pypa/gh-action-pypi-publish` under the `pypi` environment with
  `id-token: write`; PyPI accepts it via OIDC.

`workflow_dispatch` allows a manual re-run (e.g. if the publish step failed after
a green build) without cutting a new release.

## Verifying

After the run finishes, confirm the version is installable from a clean
environment:

```sh
python -m venv /tmp/verify && /tmp/verify/bin/pip install "regent-cli==<version>"
/tmp/verify/bin/regent doctor
```
