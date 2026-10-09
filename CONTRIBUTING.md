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

The build uses the bin2whl CLI, then calls `postprocess()` to add documents and the PyPI description via `wheel unpack/pack`, which updates `RECORD`. The description comes from `README.md`, with release and source links added automatically.

## Update and check

Release settings live in `wheel.json`:

- `version` matches the upstream version; the tag is `v<version>`.
- `homepage` identifies the upstream repository.
- `binaries` defines platform tags, command names, and paths under `build/<upstream-target>/`.

Review upstream assets and platform compatibility when updating. `pyproject.toml` manages the build environment only.

Keep `dist/` limited to the release you intend to publish.

```sh
uv run --locked python -m unittest discover -s tests -v
uvx twine check dist/*.whl
```

Before publishing, install the wheel and test `caesiumclt --version` and image compression on the target systems.

## Publish

Set `UV_PUBLISH_TOKEN` to your PyPI API token, then upload the checked wheels:

```sh
uv publish dist/*.whl
```

## License

Packaging code is licensed under [Apache-2.0](LICENSE). Bundled binaries and dependencies retain their original licenses.

Each wheel preserves the upstream release's `LICENSE.md` and `README.md` under `.dist-info/licenses/` and `.dist-info/upstream/`. This project does not collect or audit dependency licenses.
