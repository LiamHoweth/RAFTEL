# Contributing to RAFTEL

Start with the [research roadmap](docs/roadmap.md) and [engineering documentation](docs/README.md). Useful first contributions include reproducing a result on another platform, investigating a failing logical layout, adding a numerical regression with an independently derived expected value, or improving a setup instruction. Open an issue before changing a public data format, modeling assumption, or integration boundary.

## Set up a development environment

Install Git and Python 3.11 or newer. CI covers CPython 3.11–3.14 on Linux and Windows. Run the commands from the repository root.

On macOS or Linux:

```sh
make setup
make demo
make verify
```

Without Make, use `python3 -m venv arm-01/.venv`, then run the commands below with `arm-01/.venv/bin/python` as the interpreter. On Windows PowerShell:

```powershell
py -3 -m venv arm-01\.venv
arm-01\.venv\Scripts\python.exe -m pip install --only-binary :all: -r arm-01/requirements-dev.lock -e 'arm-01[dev]'
arm-01\.venv\Scripts\raftel-sort.exe --seed 42
arm-01\.venv\Scripts\python.exe scripts\verify.py
```

Initial installation uses a package index. The runtime uses the Python standard library. Tests, engineering CLI checks, wheel building, and the fresh environment wheel smoke can run offline once the development environment is installed. The verifier writes evidence to `.work/verification/run-*`, including the pytest report, logical demo outputs, engineering reports, and installed-wheel verification JSON.

For a focused check, use the development environment from `arm-01`:

```sh
python -m pytest tests/test_installed_wheel.py
python -m ruff check .
python -m ruff format --check .
python -m compileall -q src
```

Update exact dependency versions in `arm-01/requirements-dev.lock`. Keep direct development and build pins synchronized with `arm-01/pyproject.toml` and the wheel metadata assertions. The lock records versions and platform markers. Use the supported interpreter matrix to verify availability and compatibility after changes.

## Submit a focused change

1. Reproduce the issue on a known commit. Include commands, Python and OS versions, seeds, input configuration or scenario IDs, and relevant output.
2. Keep changes close to the existing module boundary. State units, coordinate frames, source revisions, assumptions, and failure behavior wherever they affect the result.
3. Run the relevant tests and include the results in the pull request. Mark analytical and simulation evidence by scope and cite physical data with its collection conditions when available.
4. Describe third-party material and the permission to include it. Consult the [license review](docs/licensing.md) before submitting creative assets, CAD derivatives, firmware, or datasets. RAFTEL's distribution license awaits owner selection.

Keep transient run outputs, native scratch files, virtual environments, and credentials outside the diff. Preserve existing evidence and create a separately named revision when a new study supersedes it. Live motion, purchasing, and fabrication require the project's documented approvals. Standard contribution checks use the mock software and offline studies. [Safety and commissioning](arm-01/docs/safety.md).

Follow the [code of conduct](CODE_OF_CONDUCT.md). For sensitive vulnerabilities, use the [security reporting process](SECURITY.md).
