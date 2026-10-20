# Contributing to AnkiVoice

[Русский](CONTRIBUTING.md)

Thanks for wanting to help. The rules below are short on purpose — so that a
patch does not turn into an evening of debugging.

## Quick start

```bash
git clone https://github.com/Daii1414/AnkiVoice.git
cd AnkiVoice
git checkout -b feature/short-description
```

Change, verify, open a pull request against `main`.

## Architecture you should know

| Layer | Files | Rule |
|---|---|---|
| Core | `voice_pipeline.py` | All synthesis, reading and Anki writing logic. It runs from disk — changes take effect immediately, no exe rebuild. |
| Interface | `anki_gui.py`, `anki_web.py`, `anki_web_page.py` | Baked into the exe. After editing these, the exe and the installer must be rebuilt. |
| Reading system | `lab/g2p_*.py`, `lab/domain_dict.py` | Reading modules. Five files from `lab/` are shipped in the installer — do not break their imports. |
| Quality | `lab/quality_v2.py` | Multi-signal audio quality check. Shipped in the installer as well. |

The full technical description is in [PROJECT.md](PROJECT.md).

## Code rules

* Python 3.9+ (engine) and 3.12+ (CI). Only the standard library in
  `voice_pipeline.py`, `anki_web.py`, `anki_web_page.py` — the app itself has
  no third-party dependencies.
* Comments and error messages are in Russian, no slang.
* No network calls except the GitHub update check and the local AnkiConnect.
* Do not touch `pyruntime.zip` and `sudachidict.zip` — they are built
  separately and ship as they are.
* Build file paths through `code_dir()` / `resolve_path()` instead of hard
  coding them: the app runs from `E:\` and from `%LOCALAPPDATA%\Programs`.

## Checks before opening a pull request

```bash
python -m pip install numpy haqumei
python lab/qc_unit.py
python lab/quality_unit.py
python lab/test_g2p_infrastructure.py
python lab/test_v12_features.py
python lab/web_js_check.py
python lab/integration_check.py
```

All six must exit with code 0. `lab/robust_tests.py` (10 robustness checks)
needs a running Anki — run it if your change touches the pipeline.

If the interface changed, attach a screenshot of the tab to the PR description.

## Building

```bat
set ENGINE=C:\Path\To\GPT-SoVITS
%ENGINE%\runtime\python.exe -m pip install pyinstaller
%ENGINE%\runtime\python.exe -m PyInstaller --noconfirm --onefile --windowed ^
    --name AnkiVoice --distpath . --workpath %TEMP%\pyi_build --specpath %TEMP% anki_gui.py
ISCC.exe AnkiVoice.iss
```

The installer is built from the repository root and lands in `dist/`.

## Commit style

```
<type>(<scope>): <imperative summary>

Why this is needed — in the body, wrapped at 72 characters.
```

Types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`,
`chore`. Example: `fix(reading): do not break imports without haqumei`.

## What we do not want

* Heavy models, frameworks or new dependencies in the app.
* Automated commits copied from other repositories.
* Changes that break the `voices.json` format without a migration.

## Where to ask

* Bugs and ideas — <https://github.com/Daii1414/AnkiVoice/issues>.
* Security questions — follow [SECURITY.md](SECURITY.md).
