<p align="center">
  <img src="doc/logo.svg" alt="AnkiVoice" width="880">
</p>

<p align="center">
  <a href="https://github.com/Daii1414/AnkiVoice/actions/workflows/checks.yml">
    <img alt="CI" src="https://github.com/Daii1414/AnkiVoice/actions/workflows/checks.yml/badge.svg">
  </a>
  <a href="https://github.com/Daii1414/AnkiVoice/releases/latest">
    <img alt="Release" src="https://img.shields.io/github/v/release/Daii1414/AnkiVoice?label=release&color=8B9BFF">
  </a>
  <a href="https://github.com/Daii1414/AnkiVoice/blob/main/LICENSE">
    <img alt="AGPL-3.0" src="https://img.shields.io/badge/license-AGPL--3.0-4F46E5.svg">
  </a>
  <img alt="Windows 10/11" src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white">
  <img alt="No cloud" src="https://img.shields.io/badge/data-off%20line%2C%20no%20cloud-12A150">
</p>

<p align="center"><b>Local Japanese audio for Anki decks, voiced by GPT-SoVITS or IndexTTS 2.5.</b><br>
The engine reads the kanji itself - connected, in the context of the sentence -
while the reading of the main term comes from the card's furigana. Finished
ogg files land straight in Anki fields. <b>Free, no accounts, no telemetry.</b>
The internet is only needed to download it.</p>

<p align="center">
  <a href="https://github.com/Daii1414/AnkiVoice/releases/latest">
    <img alt="Download AnkiVoice 1.7 for Windows" src="https://img.shields.io/badge/%E2%96%A8%20Download%20AnkiVoice%201.7%20%E2%80%94%20125%20MB-4F46E5">
  </a>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Install</a> •
  <a href="#interface-four-tabs">Interface</a> •
  <a href="#how-kanji-are-read">Reading</a> •
  <a href="#development">Development</a> •
  <a href="#license">License</a>
</p>

[Русский](README.md) | **English**

---

## Table of contents

- [Features](#features)
- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Quick start](#quick-start)
- [Interface (four tabs)](#interface-four-tabs)
- [Pronunciation check](#pronunciation-check)
- [A second engine: IndexTTS 2.5](#a-second-engine-indextts-25)
- [How kanji are read](#how-kanji-are-read)
- [How text becomes hiragana](#how-text-becomes-hiragana)
- [Card fields](#card-fields)
- [Console](#console)
- [Updates](#updates)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Repository layout](#repository-layout)
- [Contributing](#contributing)
- [License](#license)
- [Credits](#credits)

---

## Features

| | |
|---|---|
| 🎧 **Deck dubbing** | Writes `<audio>` with the sentence and the word straight into Anki fields. GPT-SoVITS clones the voice itself. |
| 📖 **Two reading modes** | The engine reads the kanji itself - connected, in context - while the main term keeps the reading from the card's furigana. No furigana - it reads the kanji itself. |
| 🧩 **Per-deck settings** | Fields and reading mode belong to a deck: switch decks and its settings come with them. |
| 🧪 **Quality control** | QC v2 measures several independent signals (silence, speech gaps, duplicate speech, clipping, level, speed) and re-synthesizes rejects on its own. |
| 🎙 **Pronunciation check** | The app listens to its own audio and compares it with the text, showing where the sentence diverged. Advice, not a verdict - you decide. |
| 🧙 **First-run wizard** | Five steps: pick the engine, the engine folder, AnkiConnect, server, test phrase. It tells you what to download, where to put it and what to click. |
| 🔄 **In-app updates** | "Check for updates": changelog, installer download and a mandatory SHA256 check. |
| 🌐 **Two languages** | The whole interface in English and Russian - switch with the EN button in the header. |
| 🔒 **Fully local** | The page works offline, without a CDN. The only outbound request is the update check. |
| 🧩 **Transparent** | No telemetry, no accounts. AGPL-3.0 - the sources are open. |
## How it works

![How it works](doc/how-it-works.en.svg)

AnkiVoice does not copy the engine's code: [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)
runs as an ordinary local server, the app sends it text and takes the sound back.
So the engine's own web interface and any of its voices keep working next to it.
## Requirements

1. **Windows 10/11** and a CUDA GPU (6 GB of VRAM is comfortable) with a recent
   NVIDIA driver (CUDA 12.8+ is needed for IndexTTS 2.5).
2. **One of the two engines** - pick it in the wizard on the first run:
   * **[GPT-SoVITS v2Pro](https://github.com/RVC-Boss/GPT-SoVITS/releases)** -
     the unpacked Windows package, roughly **6-10 GB** (voice weights are not
     included);
   * **[IndexTTS 2.5](https://github.com/index-tts/index-tts)** - `git clone` +
     `uv sync --extra webui` + the model weights (~5 GB) in `checkpoints`.
3. **A voice of your own.** For GPT-SoVITS: a `.ckpt` + `.pth` pair and a 3-10 s
   reference clip; for IndexTTS 2.5: **one reference clip** of 3-10 s (the
   weights belong to the model). The engine ships its own voices.
4. **Anki** with **AnkiConnect** enabled (the add-on listens on `127.0.0.1:8765`).

Nothing else has to be installed: the reading dictionary and the bundled Python
are already inside the installer (`pyruntime.zip`, `sudachidict.zip`) and
unpack themselves.

The **internet** is only needed to download the installer and the engine - the
dubbing itself is fully offline. Allow about **1 GB** of disk for the app (the
installer itself is 125 MB) plus room for the engine and its weights.

## Quick start

1. Download **`AnkiVoice-Setup-1.8.exe`** from the
   [Releases](https://github.com/Daii1414/AnkiVoice/releases/latest) page — one
   file with everything inside. Size **125 MB**, SHA256:
   `385481551c6404ec8927a37d6c234630c87ee71660aa5c689eab9654da0dbc28`
   (The **Code → Download ZIP** button gives you the sources, not the installer —
   you do not need to unpack and run those by hand.)
2. Run it: **“Далее” → “Установить” → “Завершить”** (Next → Install → Finish;
   the “Launch AnkiVoice” checkbox is on, so the app opens by itself).
   > [!IMPORTANT]
   > The installer is not digitally signed, so Windows shows a blue SmartScreen
   > window. Click **“More info” → “Run anyway”** - the usual warning for files
   > downloaded outside the store.
3. The setup wizard walks you through the steps: pick the engine → engine folder
   → AnkiConnect → server → test phrase. It opens by itself on every launch
   until the setup is finished.

   ![Setup wizard](doc/shots/wizard-dark.png)

4. Then: the **“Голос”** (Voice) tab to pick a voice, the **“Поля колоды”**
   (Deck fields) tab to pick a deck and fields, and the **“Озвучка”** (Dubbing)
   tab to press **“Начать озвучку”** (Start dubbing).

The **AnkiConnect** add-on code is `2055492159` (Anki → Tools → Add-ons → Get
Add-ons). Restart Anki after installing the add-on.

The app starts a local server and opens a page in your browser — that is
normal, nothing else needs to be installed. The server only accepts its own
requests: another site open in the same browser cannot start dubbing or close
the app.

The **EN** button in the header switches the interface to English (and back). It installs into your user profile
(`%LOCALAPPDATA%\Programs\AnkiVoice`) and does not ask for administrator
rights. To uninstall: Start menu → “Удалить AnkiVoice” (settings and voices
are kept).

> [!TIP]
> No engine yet? The wizard links to the official
> [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS/releases) releases and
> shows which files must be in the folder. It does not download the engine for
> you.

## Interface (four tabs)

The shell is a local web page (`anki_web.py`): the server listens only on
`127.0.0.1`, nothing goes outside. The old tkinter window is still available
via the `--classic` flag.

### “Озвучка” (Dubbing) — the main screen

![Dubbing tab](doc/shots/voice-dark.png)

* **Synthesis engine — two big cards at the top.** GPT-SoVITS or IndexTTS 2.5,
  each with a one-line description. You can switch while working, no restart:
  the engine folder, the server address and the voice list all follow. Under
  the cards — how many voices are ready and where the server lives.
* **Deck** and **Voice** — lists pulled from Anki and `voices.json`.
* **What to voice** — “word + sentence” (the usual choice), sentence only or
  word only; a card limit (0 = all); “rebuild everything” ignores cards that
  are already done.
* **The limit is an amount of work**, not a position in the deck: “voice 20
  cards” takes the 20 cards that have no audio yet, not the first twenty.
* **“Начать озвучку”** (Start dubbing) — the main button; next to it are
  **“Остановить”** (Stop), **“Проверить колоду”** (Check deck) and
  **“Самопроверка”** (Self-test).
* **Progress bar** — an exact “N / total” counter and the error count.
* **Log** — a live SSE stream with color coding: green = done, red = error,
  yellow = rejected and QC retries.

### “Поля колоды” (Deck fields) — what to read from where

![Deck fields tab](doc/shots/anki-dark.png)

* **Deck** + the **“Поля выбранной колоды”** (Fields of the selected deck)
  button — fills the role table automatically from the template
  (Sentence / Expression / \*Audio / Furigana). The fields also fill
  themselves in: pick a deck and the app reads its fields and matches the
  roles; you can still change them by hand on the “Поля колоды” tab.
* Table rows: sentence text, sentence audio, main word, word audio,
  **word furigana ← field** and the reading source.
* An empty choice in the “→” column means “do not write audio”. Empty
  furigana means the word is read automatically.

### “Голос” (Voice) — reference and speech character

![Voice tab](doc/shots/sound-dark.png)

* **Voice cards** — every voice from `voices.json`; ✅/✗ shows whether the
  gpt/sovits/ref files were found.
* **Reference (3–10 s)** — the voice sample: file, its text and language. Do
  not use a long aux reference — the API will run out of memory.
* **Speech character** — `temperature`/`top_p`/`top_k`/`speed` sliders and a
  `seed` field: lower values give more even, calmer speech (defaults from the
  official web UI: 0.6 / 0.6 / 20).
* **“Прослушать тест”** (Play test) — a quick voice check; the file plays
  right on the page. **“Обновить веса в движке”** (Refresh engine weights) —
  scans for new weights.

### “Приложение” (App) — wizard, updates, diagnostics

![App tab](doc/shots/app-dark.png)

* **Setup wizard** — four steps: engine, AnkiConnect, server, test phrase. It
  shows the status of each step and what to do when one is red. The first step
  picks the engine (two cards) and its folder.
* **Updates** — the “Check for updates” button shows the latest changelog,
  downloads the installer and verifies its SHA256.
* **Diagnostics** — everything at once: tool, config, path, Anki, server, voice
  list. Look here first if something does not work.
* **Where the files live** — program folder and config.

Status chips in the header: **Anki** (connected?), **Server** (GPT-SoVITS is
running), the version and a running-operation indicator. The theme is toggled
on the right.

Light theme — the same tabs: [Dubbing](doc/shots/voice-light.png),
[Deck fields](doc/shots/anki-light.png), [Voice](doc/shots/sound-light.png),
[App](doc/shots/app-light.png). A full-page snapshot:
[voice-dark-full.png](doc/shots/voice-dark-full.png).

## A second engine: IndexTTS 2.5

Besides GPT-SoVITS you can run **IndexTTS 2.5**, a zero-shot engine that
needs only one reference clip. The switch lives **on the main screen**, at the
top, as two large cards. The choice is remembered and applies to the whole app.

| | GPT-SoVITS | IndexTTS 2.5 |
|---|---|---|
| a voice | `.ckpt` + `.pth` files + a reference | **one reference** (3-10 s) |
| weights | per voice | shared by the model |
| install | unpacked archive | `git clone` + `uv sync --extra webui` + weights in `checkpoints` |
| Japanese reading | the engine's g2p | its own Japanese g2p (`ja_g2p`) |

Install IndexTTS 2.5:

```
git clone https://github.com/index-tts/index-tts.git D:\DOWNLOAD\index-tts
cd D:\DOWNLOAD\index-tts
uv sync --extra webui
uv tool install "huggingface-hub"
hf download IndexTeam/IndexTTS-2.5 --local-dir checkpoints
```

Point AnkiVoice at that folder in “App” (or press “Check” - it finds the
folder by itself). `uv` has to be in PATH and the NVIDIA driver needs CUDA
12.8 or newer.

**Why a bridge.** IndexTTS has no HTTP API - only a Python API and a web UI.
AnkiVoice starts a small service next to itself
(`lab/indextts_service.py`, shipped with the installer) that loads the model
**once** and answers `POST /tts`. Without it every card would reload the
weights.

What stays the same: the acoustic QC, the reading mode (auto / kanji only),
the rules for substituting the furigana reading, writing the audio into the
card, the review deck and the verdicts.

What is missing in the IndexTTS mode:

* the **content check** (recognising our own voice) - it lives in the
  GPT-SoVITS environment (faster-whisper). Without GPT-SoVITS the acoustic
  check remains and the recognition is off;
* the manual sampling settings (seed, temperature, top_p, top_k) - IndexTTS
  has none, the interface hides them.

## What's new in 1.8

- **The repository root is tidy:** the code lives in `app/`, the heavy archives
  (the bundled Python and the Sudachi dictionary) in `bundled/`, the lab in
  `lab/`, the interface checks in `qa/`.
- **`AnkiVoice.exe` is no longer in the repository** - it is a build artifact.

## Pronunciation check

GPT-SoVITS sometimes **loses a chunk of a sentence or invents extra**: the
duration looks normal, the sound is speech, but the content is wrong. A
"silence / length / duplicate" check cannot see that.

On the "Dubbing" tab, **"Check pronunciation"**: the app recognizes its own
audio (faster-whisper) and compares it with the text it was asked to say. The
divergence is reported to a fraction of a second - you see right away where the
sentence went apart.

**This is advice, not a verdict.** Measured on 27 labeled cards: 2 confirmed
failures against 25 false alarms - the recognizer mangles domain terms
("だいくはこうさぶ" → "ないくはこうさぶん"), and by text alone they cannot be
told apart from a real mistake. So the check

* does not reject a card and does not tag it;
* prints the coverage, the error rate and the diverging span in the log;
* collects the doubtful pieces into a **"Брак" (Rejects) deck**, three
  variants each. Listen and write down "верно" or "ложное срабатывание".

Three buttons on the "Dubbing" tab:

* **"Check pronunciation"** - recognizes the cards you have already voiced;
* **"Build the “Брак” deck"** - collects the doubtful pieces with variants;
* **"Verdict summary"** - counts your labels and shows where our thresholds
  sit too low.

**We check sentences, not words.** An isolated word is transcribed
unreliably: the zones "real failure" and "false alarm" overlap completely. The
word is guarded by the acoustic QC (silence, tempo, length).

**Thresholds are per voice.** One voice may sit at 0.95 coverage, another at
0.85. The app measures the norm from the accepted pieces and compares against
it, not against one global number.

What it needs: `faster-whisper` in the GPT-SoVITS python and one downloaded
model (in the HuggingFace cache). Without them the check simply does not run
and dubbing goes on as usual. One piece takes about 0.5 s on a GPU.
## How kanji are read

GPT-SoVITS can read kanji on its own - but on rare terms it picks its own
reading. So the reading mode is switched in "Deck fields" → "Reading source":

| Mode | What the engine gets | When to pick it |
|---|---|---|
| **Auto (default)** | If the furigana field has something in it - the whole text in kanji, except the main term, whose reading is substituted from the furigana. If the field is missing or empty - the whole text in kanji | Universal: exact reading where there is a furigana, ordinary reading where there is none |
| **Kanji only (the engine reads it)** | The whole text in kanji, nothing substituted | Decks with ordinary words: the sound is the most connected |

The mode is a **per-deck setting**: it is stored in the deck profile together
with the fields. In the "auto" mode the decision is made **for every card**: an
empty furigana field means "read the kanji yourself", and there is nothing to
substitute.

What "exact" and "plain" cost, measured on 150 sentences and a blind A/B on 10
of them:

* in sound, plain kanji wins - 7 votes out of 10;
* but in 12 sentences out of 150 the model read the term differently from the
  card (`麻院[あさすさ]` → "アサイン"). In the mixed mode it is 2 out of 150.

The card's furigana is the source of truth for the main term: the
`ExpressionFurigana` field (or another one, if the deck names it
differently). Substitution rules: clean kana only, only when the term is
found in the sentence as a whole, otherwise the card is left as it is.

Two exceptions, both measured on cards with katakana terms:

* a reading that covers the whole word ("点群データ[てんぐんでーた]") is taken
  as it is - otherwise the okurigana ("データ") would be added a second time and
  the word would be heard twice. As a safety net, the finished text is checked:
  if the okurigana would be heard twice, the term is left as it is and the
  engine reads it itself;
* terms with latin letters or digits ("3D", "PLATEAU", "BIM/CIM", "2.0") are
  left alone: the engine reads them better on its own, and our own
  transcription ("3D" -> "すりーでぃー") sends the model into a loop - measured
  96 seconds and coverage 0.89 against 4 seconds and 1.00.

In the console this is the `--reading ""|mix|asis` flag (empty = auto).
## How text becomes hiragana

The sentence goes to the engine **in kanji**: GPT-SoVITS reads the kanji
itself, in the context of the sentence - that is what makes the sound connected
instead of a set of separate pieces.

The `kanaize()` pipeline prepares hiragana - but only where it is needed:

* **the main term** - in the mode with a furigana the reading is taken from the
  card's furigana; if the furigana does not fit (the word is not found in the
  text, the reading still has kanji in it) the word is converted to kana by our
  own pipeline;
* **in the "kanji only" mode** nothing is prepared: both the word and the
  sentence go to the engine as they are, it reads them itself.

The steps of `kanaize()`:

1. **NFKC normalization** — full-width letters/digits and half-width katakana
   are folded into normal forms (punctuation is left alone);
2. **Latin → katakana by letters** (`IEC` → アイイーシー);
3. **katakana → hiragana** (greetings コンニチハ/コンバンハ stay katakana —
   otherwise MeCab reads them as a particle; the repetition marks ヽゝゞヾ are
   expanded contextually — repeat of the previous syllable);
4. **g2p only for the kanji that are left**: Haqumei reads every word in the
   context of the sentence (sandhi, neighbouring katakana), with Sudachi over
   the UniDic dictionary and pyopenjtalk (MeCab) as fallbacks; digits always go
   through MeCab, because Sudachi reads numbers as dates (2024 → 二月二日);
5. **one more katakana → hiragana pass** — and the API receives pure hiragana.

What the pipeline **does not touch**: the note in Anki itself (a copy of the
text is processed) and the card's furigana (it is only used as a reading
source).

Reading is covered by tests: `pipeline.bat selftest` (10 substitution checks
and 11 reading-mode checks) and the extended battery
`python kana_stress.py` (63 difficult words). Detailed measurements live in
[doc/reports/](doc/reports).

## Card fields

Decks name their fields differently — where to take the text from and where to
write the audio is configurable (GUI: the “Поля колоды” tab; console: the
`voice` / `make-deck` / `check` commands):

```
--sentence-src "Sentence"             field with the sentence text
--sentence-audio "SentenceAudio"      field the sentence audio goes to
--word-src "Expression"               field with the word (furigana parsing works for Expression)
--word-audio "ExpressionAudio"        field the word audio goes to
--furigana-src "ExpressionFurigana"   field with the furigana of the main word
    --reading ""|mix|asis         reading mode (see above; empty = auto)
```

## Console

`pipeline.bat` is the same thing in the console; it finds the engine folder on
its own:

```
pipeline.bat list              list of voices
pipeline.bat selftest          check the environment (run it when in trouble)
pipeline.bat test --voice madara --text "こんにちは"
pipeline.bat voice --voice madara --deck "Архитектура" --mode both
pipeline.bat verify --deck "Архитектура"    check the pronunciation of what is voiced
pipeline.bat qc-deck                         build the "Брак" deck with variants
pipeline.bat verdicts                        summary of your verdicts
pipeline.bat check --deck "Архитектура"          full check of a deck
pipeline.bat check --deck "Архитектура" --fast   the same without downloading audio
pipeline.bat scan --apply     find voices in the engine and add them to voices.json
```

Diagnostics are available in the exe as well: `AnkiVoice.exe doctor`.
## Updates

* **From the app**: the “Приложение” tab → **“Проверить обновления”**. The
  app shows the changelog, downloads the installer and verifies the SHA256 —
  without that check the download is not started. Then press “Запустить
  установщик” (Launch installer).
* **Manually**: download the new installer from
  [Releases](https://github.com/Daii1414/AnkiVoice/releases/latest) and run it
  over the old version — the engine path and the settings are kept.
* **Uninstall**: Start menu → “Удалить AnkiVoice” (settings are kept and are
  picked up again on the next install).

## Troubleshooting

| Message | What to do |
|---|---|
| `Не найдена папка GPT-SoVITS` | Set the path: `gptsovits_path.txt`, the `GPT_SOVITS_ROOT` environment variable, or the “Browse…” button in the app |
| `AnkiConnect недоступен` | Open Anki; if the add-on is missing — Tools → Add-ons → Get Add-ons, code `2055492159`, then restart Anki |
| `Референс X с — API требует 3–10 с` | Trim the clip to 3–10 seconds |
| `Не получилось переключить... Перезапуск` | Normal: the pipeline restarts the server and retries |
| `сервер вернул пустой звук` | Usually VRAM is occupied by other processes (browser, games). Close them or restart the server: `pipeline.bat serve --voice <voice>` |
| `Пайплайн уже запущен другим процессом` | Wait for the first run to finish (protection against double work) |
| Windows: “Your PC protected” | The downloaded exe is unsigned: in the SmartScreen window click “More info” → “Run anyway” |

Useful: `selftest` prints exactly what it sees (engine, voices, reading
dictionary, reading modules, QC v2, AnkiConnect, server) — 90% of problems are
visible immediately.

## Development

```bash
git clone https://github.com/Daii1414/AnkiVoice.git
cd AnkiVoice
```

A rebuild is needed only after editing `app/anki_gui.py`, `app/anki_web.py` or
`anki_web_page.py` — `voice_pipeline.py` runs from disk and takes effect
immediately.

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

→ produces `dist\AnkiVoice-Setup-1.6.exe`.

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

## Contributing

* Patches and ideas — via [issues](https://github.com/Daii1414/AnkiVoice/issues)
  and pull requests. Templates live in `.github/ISSUE_TEMPLATE`.
* Development rules, build, commit style — in
  [CONTRIBUTING.md](CONTRIBUTING.md).
* Vulnerabilities — follow the instructions in [SECURITY.md](SECURITY.md).

## License

**AGPL-3.0** (text in [LICENSE](LICENSE)): whoever modifies and distributes
this tool is obliged to publish the sources of their changes, including when
it is used over a network.

## Credits

* [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) — the synthesis engine
  (MIT).
* [Haqumei](https://github.com/o24s/haqumei) — context-aware kanji readings
  (the main core).
* [Sudachi](https://github.com/WorksApplications/SudachiPy) and the UniDic
  dictionary — fallback and reading checks.
* [gradio](https://github.com/gradio-app/gradio) — the Voice tab is styled
  after their web UI.
* [AnkiConnect](https://ankiweb.net/shared/info/2055492159) — the bridge to
  Anki.
