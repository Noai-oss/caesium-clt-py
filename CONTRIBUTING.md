# Building and publishing

With [uv](https://docs.astral.sh/uv/) installed, run from the repository root:

```sh
uv run --locked python build.py
```

This downloads upstream assets over HTTPS and writes seven wheels to `dist/`. Each run downloads fresh copies; Linux wheel variants share one download per architecture within a run. Nothing is uploaded.

To select a target:

```sh
uv run --locked python build.py --target x86_64-unknown-linux-musl
```

Repeat `--target` to select more targets. Use `--output-dir` to change the destination or `--prepare-only` to download and prepare files without building wheels.

The version in `wheel.json` selects both the downloaded binaries and the Python wheel version.

The build uses the bin2whl CLI, then calls `postprocess()` to add documents and the PyPI description via `wheel unpack/pack`, which updates `RECORD`. The description comes from `README.md`, with release and source links added automatically.

## Update and check

Release settings live in `wheel.json`:

- `version` is the only source of the build version; the upstream tag is `v<version>`.
- `homepage` identifies the upstream repository.
- `binaries` defines platform tags, command names, and paths under `build/<upstream-target>/`.

Review upstream assets and platform compatibility when updating. `pyproject.toml` manages the build environment only.

Update `wheel.json` when a newer upstream release is available:

```sh
uv run --locked python -m scripts.update_version
```

This queries GitHub's [`/releases/latest` endpoint](https://docs.github.com/en/rest/releases/releases#get-the-latest-release), which excludes drafts and prereleases. The script uses `packaging.Version` to check canonical PEP 440 spelling and compare versions, preserving the upstream version text. For a newer version, every asset required by `wheel.json` must be uploaded and nonempty before the configured version changes. API, version format, or asset errors leave the file unchanged. This command does not query PyPI, commit, or publish anything.

The upstream query uses a 30-second timeout and reports failures directly. Rerun a failed update manually or let the next scheduled run check again.

Keep `dist/` limited to the release you intend to publish.

```sh
uv run --locked python -m unittest discover -s tests -v
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked twine check dist/*.whl
```

Ruff, Twine, and Pillow are locked development dependencies. `.python-version` selects Python 3.12 for local and CI `uv sync` / `uv run`; CI uses the latest uv through `setup-uv` without a uv version pin. Run `uv sync --locked` to create or update the local environment.

On a compatible host, install a built wheel in a temporary venv and check its version and image compression:

```sh
uv run --locked python -m scripts.smoke dist/*-manylinux_2_17_x86_64.whl
```

The fixed PNG fixture is 32×24 pixels. Its compressed output must fully decode with Pillow and retain its format and dimensions; a size reduction is not required. Runtime tests create a clean venv and install the exact local wheel with index access and dependencies disabled.

## GitHub Actions

| Workflow | Trigger | Behavior |
| --- | --- | --- |
| [Update](.github/workflows/update.yml) | Friday 06:17 UTC / manual | Check out main, preflight the newer release's assets, and maintain a version-only PR on `update-upstream-version` |
| [CI](.github/workflows/ci.yml) | PR / main push / reusable call | Build all seven wheels, run Twine, then install and exercise the same artifact on three platforms |
| [Release](.github/workflows/release.yml) | `v*` tag push / manual | Validate the selected commit, call CI, and optionally upload its exact artifact |

CI runs the Linux x86_64 glibc, macOS ARM64, and Windows x86_64 wheels on `ubuntu-24.04`, `macos-15`, and `windows-2022`. The other four wheels are built and checked by Twine; runtime coverage can be added later. These tests do not certify every wheel's minimum OS version.

The stable `CI result` check fails if build or any required runtime job fails, is cancelled, or is skipped. Set it as a required check for main after it first appears.

Enable **Allow GitHub Actions to create and approve pull requests** in Settings → Actions → General. The update workflow uses `GITHUB_TOKEN`; approve its PR checks using **Approve workflows to run**, then review and merge. It does not merge or create release tags.

Main pushes run CI without publishing. To publish, create and push a tag named exactly `v<version>` for a reviewed commit already included in main. Both lightweight and annotated tags are supported; the release preflight rejects a mismatched tag or an unmerged commit.

To run a release from the GitHub website:

1. Open **Actions → Release → Run workflow**.
2. Set **Use workflow from** to `main`.
3. Fill in the required **tag** input with an existing repository tag, such as `v1.6.0`.
4. Leave **publish** unchecked to validate, or check it to publish after validation.
5. Click **Run workflow**. The run title shows `Validate v1.6.0` or `Publish v1.6.0`.

The tag is required for both validation and publication. The selected workflow branch supplies the workflow definition; the **tag** input selects the source commit and its `wheel.json` version. The workflow does not create tags or edit versions. Both modes reject missing tags and tag/version mismatches. Publishing also requires the target commit to be included in main, and the workflow must run from main or the target tag. The summary records the exact version, tag, and commit.

The equivalent CLI invocation is:

```sh
gh workflow run release.yml --ref main -f tag=v1.6.0 -f publish=true
```

Omit `-f publish=true` to validate only. The workflow file must be present on the default branch before GitHub offers manual dispatch. When introducing these workflows, validate the feature branch through PR CI first.

Automatic publishing uses [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/adding-a-publisher/). Add a GitHub publisher to the `caesium-clt-py` project on PyPI with these values:

| Field | Value |
| --- | --- |
| Owner | `Noai-oss` |
| Repository | `caesium-clt-py` |
| Workflow | `release.yml` |
| Environment | `pypi` |

Create the `pypi` GitHub environment. **Deployment branches and tags** can stay at **No restriction**; additional deployment rules are optional. If you choose **Selected branches and tags**, add a **Branch** rule for `main` and a **Tag** rule for `v*` to support both manual and tag-triggered runs. See [GitHub deployment rules](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments). Only the publish job requests `id-token: write`; no PyPI token is needed in GitHub secrets. If the project does not yet exist on PyPI, register a pending Trusted Publisher.

CI saves the wheels as `wheels-<run ID>-<build attempt>` for 30 days. Tests and publication download that artifact by its returned ID. After CI passes, a separate publish job follows [uv's GitHub Actions guide](https://docs.astral.sh/uv/guides/integration/github/#publishing-to-pypi): install uv, download the tested wheels, and upload with `uv publish --trusted-publishing always`. It only requests `id-token: write` and needs no source checkout.

## Retry a failed upload

Inspect the error and use **Re-run failed jobs** in the original run to reuse the successful build's artifact. uv skips identical files already on PyPI and rejects conflicting contents. See [uv publishing](https://docs.astral.sh/uv/guides/package/#publishing-your-package).

Uploads can fail after some files have been accepted; they are not rolled back. The workflow relies on uv's upload result and does not audit the complete remote release or poll afterward. Avoid rebuilding a partially published version because wheel bytes may change. If the original artifact has expired, stop and resolve it manually. Independent packaging revision versions remain out of scope.

Merge the workflow files into main and configure the repository settings above before first production use.

## License

Packaging code is licensed under [Apache-2.0](LICENSE). Bundled binaries and dependencies retain their original licenses.

Each wheel preserves the upstream release's `LICENSE.md` and `README.md` under `.dist-info/licenses/` and `.dist-info/upstream/`. This project does not collect or audit dependency licenses.
