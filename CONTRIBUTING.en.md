# Contributing to AnkiVoice

[Русский](CONTRIBUTING.md)

Thanks for wanting to help. The rules below are short on purpose — so that a
patch does not turn into an evening of debugging.

## Quick start

```bash
git clone https://github.com/Daii1414/AnkiVoice.git
cd AnkiVoice
```

A rebuild is needed only after editing `app/anki_gui.py`, `app/anki_web.py` or
`anki_web_page.py` — `voice_pipeline.py` runs from disk and takes effect
immediately.

## Architecture you should know

| Layer | Files | Rule |
|---|---|---|
| Core | `voice_pipeline.py` | All synthesis, reading and Anki writing logic. It runs from disk — changes take effect immediately, no exe rebuild. |
| Interface | `anki_gui.py`, `anki_web.py`, `anki_web_page.py` | Baked into the exe. After editing these, the exe and the installer must be rebuilt. |
| Reading system | `lab/g2p_*.py`, `lab/domain_dict.py` | Reading modules. Ten files from `lab/` are shipped in the installer - do not break their imports. |
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

**tests** (Python 3.12+, no GPU and no network needed):

```bash
python -m pip install numpy haqumei
python lab/qc_unit.py
python lab/quality_unit.py
python lab/test_g2p_infrastructure.py
python lab/test_v12_features.py
python lab/web_js_check.py
python lab/integration_check.py
python lab/readme_check.py
python lab/fmt_check.py
```

`lab/readme_check.py` compares the READMEs with the code: the files listed in
the layout table, the images, the table-of-contents anchors, the console
commands, the number of reading modes and the modules shipped with the
installer. If they drift apart, it fails.

`lab/fmt_check.py` checks that every format string has as many placeholders
as there are arguments - such a mismatch only blows up at the moment it runs,
usually at the very end of a long job.

`lab/robust_tests.py` — 10 robustness checks of the pipeline; it needs a
running Anki. CI runs everything else on every push
([checks.yml](.github/workflows/checks.yml)) and builds the installer on
windows-latest.

## Building

**exe** (needs the Python from the GPT-SoVITS engine with PyInstaller):

```bat
set ENGINE=C:\Path\To\GPT-SoVITS
%ENGINE%\runtime\python.exe -m pip install pyinstaller
%ENGINE%\runtime\python.exe -m PyInstaller --noconfirm --onefile --windowed ^
    --name AnkiVoice --distpath . --workpath %TEMP%\pyi_build --specpath %TEMP% app\anki_gui.py
```

**installer** (Inno Setup 6, run it from the repository root):

```bat
ISCC.exe AnkiVoice.iss
```

→ produces `dist\AnkiVoice-Setup-x.y.exe`.


## Repository layout

| File | What it is |
|---|---|
| `AnkiVoice.exe` | The app with the interface (double-click) |
| `AnkiVoice.iss` | Installer build script (Inno Setup 6) |
| `app/voice_pipeline.py` | All logic: synthesis, kanji reading, substitution, CLI |
| `app/anki_gui.py` | Exe entry point: web UI by default, `--classic` for the old window |
| `app/anki_web.py` | Local HTTP server for the UI (127.0.0.1 only) |
| `app/anki_web_page.py` | HTML/CSS/JS for the page (offline, no CDN) |
| `pipeline.bat` | Console entry point |
| `app/sudachi_g2p.py` | Fallback “reader” helper: SudachiPy 0.7 + UniDic dictionary |
| `app/g2p_core.py` | Haqumei reading core: word in sentence context, pron form |
| `app/kana_stress.py` | A battery of 63 difficult words for reading checks |
| `app/i18n_en.py` | Dictionary of the English interface (RU/EN) |
| `lab/pron_check.py` | Pronunciation check: recognition, coverage, quarantine, locating the divergence |
| `lab/align_ja.py` | Experimental acoustic alignment with a Japanese CTC model (off by default) |
| `bundled/pyruntime.zip` | Bundled Python + Haqumei 0.12.2 + SudachiPy 0.7 (~44 MB, unpacks itself) |
| `bundled/sudachidict.zip` | Sudachi core dictionary 20261015 (~73 MB, unpacked by the helper) |
| `app/voices.json` | Voice registry: weights, references, prompt, sampling |
| `lab/` | Reading system, QC v2 modules and the IndexTTS service (10 files ship with the installer) + tests and dev tools |
| `doc/` | UI screenshots, logo, engine media, measurement reports |
| `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md` | History, development rules, security policy |
| `.github/` | CI, issue and pull request templates |
| `LICENSE` | AGPL-3.0 |

Not tracked by git: `gptsovits_path.txt`, `pyruntime/` (unpacked from the zip),
`test_*.ogg`, `logs/`, `dist/`.

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
