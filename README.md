# caesium-clt-py

[caesium-clt](https://github.com/Lymphatus/caesium-clt) (Caesium Command Line Tools) is a command-line tool for compressing images.

This package ships the official prebuilt caesium-clt binaries as Python wheels, so you can install the command with a Python package manager:

```sh
uv tool install caesium-clt-py
caesiumclt --help
```

## Supported platforms

| OS | Architectures |
| --- | --- |
| macOS | x86_64, arm64 |
| Linux (glibc) | x86_64, arm64 |
| Linux (musl) | x86_64, arm64 |
| Windows | x86_64 |

## Notes

This is an unofficial distribution. Binaries are unchanged from upstream releases, and the packaging code is open source at [Noai-oss/caesium-clt-py](https://github.com/Noai-oss/caesium-clt-py).

For documentation and issues about caesium-clt itself, see the [upstream project](https://github.com/Lymphatus/caesium-clt). Upstream license and README files are included in each wheel.

For build and publishing instructions, see the [contributor guide](https://github.com/Noai-oss/caesium-clt-py/blob/main/CONTRIBUTING.md).
