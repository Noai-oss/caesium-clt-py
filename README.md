# caesium-clt-py

Unofficial Python wheels for [Caesium CLI](https://github.com/Lymphatus/caesium-clt), an image compression tool. Built from unchanged upstream release binaries using [bin2whl](https://github.com/WaterJuice/bin2whl).

Installs `caesiumclt` (`caesiumclt.exe` on Windows) with no Python runtime dependencies.

## Install and use

Once published to PyPI:

```sh
uv tool install caesium-clt-py
caesiumclt --help
caesiumclt --lossless -o output/ image.png
```

You can also use `pip install caesium-clt-py` in a virtual environment, or install a locally built wheel from `dist/`.

Platforms: Windows x86-64, macOS x86-64/ARM64, and Linux x86-64/ARM64 (manylinux and musllinux).

## Build

With [uv](https://docs.astral.sh/uv/) installed, run from this directory:

```sh
uv run --locked python build.py
```

This downloads upstream assets over HTTPS and writes seven wheels to `dist/`. Each run downloads fresh copies; Linux wheel variants share one download per architecture within a run. Nothing is uploaded.

To select a target:

```sh
uv run --locked python build.py --target x86_64-unknown-linux-musl
```

Repeat `--target` to select more targets. Use `--output-dir` to change the destination or `--prepare-only` to download and prepare files without building wheels.

The build uses the bin2whl CLI, then calls `postprocess()` to add documents and the PyPI description via `wheel unpack/pack`, which updates `RECORD`.

## Update and check

Release settings live in `wheel.json`:

- `version` selects the upstream tag: both `1.5.0` and `1.5.0.post1` use `v1.5.0`.
- `homepage` identifies the upstream repository.
- `binaries` defines platform tags, command names, and paths under `build/<upstream-target>/`.

Review upstream assets and platform compatibility when updating. `pyproject.toml` manages the build environment only.

```sh
uv run --locked python -m unittest discover -s tests -v
uvx twine check dist/*.whl
```

Before publishing, test `caesiumclt --version` and image compression on the target systems.

## License and source

Packaging code is licensed under [Apache-2.0](LICENSE). Bundled binaries and dependencies retain their original licenses.

Each wheel preserves the upstream release's `LICENSE.md` and `README.md` under `.dist-info/licenses/` and `.dist-info/upstream/`. The PyPI description includes release and source links. This project does not collect or audit dependency licenses.
