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
uv run --locked python update_version.py
```

This changes only the configured version. It does not query PyPI, commit, or publish anything. You can also edit the version manually.

Compare the configured version with PyPI without modifying files:

```sh
uv run --locked python check_version.py
```

The check reports `needs_publish=true` when the configured version is newer, or the PyPI project does not exist yet. It does not query upstream releases.

Keep `dist/` limited to the release you intend to publish.

```sh
uv run --locked python -m unittest discover -s tests -v
uvx twine check dist/*.whl
```

Before publishing, install the wheel and test `caesiumclt --version` and image compression on the target systems.

## GitHub Actions

The [update workflow](.github/workflows/update.yml) runs daily at 06:17 UTC or manually. It checks out `main`, updates `wheel.json`, and creates or updates a PR on `update-upstream-version` targeting `main`. Review and merge the PR to select the new version; this workflow does not publish.

Enable **Allow GitHub Actions to create and approve pull requests** in Settings → Actions → General. The workflow uses the built-in `GITHUB_TOKEN`.

The [release workflow](.github/workflows/release.yml) runs on pushes to `main` and manual runs. It tests the code, builds all wheels, checks their descriptions, and smoke-tests the Linux x86_64 wheel. It always builds the version in `wheel.json` at the checked-out commit.

After validation, it publishes if the configured version is newer than PyPI. Manual runs use the selected branch and can also publish. Only the update workflow runs on a schedule.

Automatic publishing uses [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/adding-a-publisher/). Add a GitHub publisher to the `caesium-clt-py` project on PyPI with these values:

| Field | Value |
| --- | --- |
| Owner | `Noai-oss` |
| Repository | `caesium-clt-py` |
| Workflow | `release.yml` |
| Environment | `pypi` |

No PyPI token is needed in GitHub secrets. Wheels are available as the `wheels` artifact on successful build runs.

If publishing fails partway through, rerun the failed publish job to reuse the same wheel artifacts. A fresh version check skips an equal version even if some platform wheels are still missing.

## Publish

Set `UV_PUBLISH_TOKEN` to your PyPI API token, then upload the checked wheels:

```sh
uv publish dist/*.whl
```

## License

Packaging code is licensed under [Apache-2.0](LICENSE). Bundled binaries and dependencies retain their original licenses.

Each wheel preserves the upstream release's `LICENSE.md` and `README.md` under `.dist-info/licenses/` and `.dist-info/upstream/`. This project does not collect or audit dependency licenses.
