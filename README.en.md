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

<p align="center"><b>Local Japanese audio for Anki decks, voiced by GPT-SoVITS.</b><br>
Reads kanji with a context-aware dictionary (Haqumei), substitutes the trusted
reading from the card's furigana, and writes finished ogg files straight into
Anki fields. The internet is only needed to download it.</p>

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
- [What's new in 1.2](#whats-new-in-12)
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
| 🎧 **Card audio** | Writes `<audio>` with the voiced sentence and word straight into Anki fields. GPT-SoVITS clones the voice itself. |
| 📖 **Smart reading** | Kanji are read by Haqumei in sentence context; the card's furigana is the source of truth for the main word. |
| 🧪 **Quality control** | QC v2 measures several independent signals (silence, speech gaps, duplicated speech, clipping, level, speed) and re-synthesizes rejects on its own. |
| 🧙 **First-run wizard** | Four steps: GPT-SoVITS folder, AnkiConnect, server, test phrase. It tells you what to download, where to put it and what to click. |
| 🔄 **In-app updates** | “Check for updates”: changelog, installer download and a mandatory SHA256 check. |
| 🔒 **Fully local** | The page works offline, without a CDN. The only outbound request is the update check. |
| 🧩 **Transparent** | No telemetry, no accounts. AGPL-3.0 — the sources are open. |

## How it works

```
Anki card
   │
   ├─► ExpressionFurigana field ──► trusted reading of the main word
   │
   ├─► kanaize(): Haqumei in sentence context → hiragana
   │      (Sudachi + UniDic and pyopenjtalk as fallbacks)
   │
   ├─► GPT-SoVITS (127.0.0.1:9880) ──► ogg
   │
   └─► QC v2: signal check ──► card in Anki
```

AnkiVoice does not copy the engine's code:
[GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) runs as a normal local
server, the app sends it text and receives the audio. That is why GPT-SoVITS's
own web UI and any of its voices keep working alongside AnkiVoice.

## Requirements

1. **Windows 10/11** and a CUDA GPU (6 GB of VRAM is comfortable).
2. **GPT-SoVITS** installed and started at least once (the folder with
   `runtime\python.exe` and `api_v2.py`).
3. **Anki** with **AnkiConnect** enabled (the add-on listens on `127.0.0.1:8765`).

Nothing else has to be installed: the reading dictionary and the bundled Python
are already inside the installer (`pyruntime.zip`, `sudachidict.zip`) and
unpack themselves.

## Quick start

1. Download **`AnkiVoice-Setup-1.2.exe`** from the
   [Releases](https://github.com/Daii1414/AnkiVoice/releases/latest) page — one
   file with everything inside.
2. Run it: **“Далее” → “Установить” → “Завершить”** (Next → Install → Finish;
   the “Launch AnkiVoice” checkbox is on, so the app opens by itself).
3. The setup wizard walks you through the steps: engine folder → AnkiConnect →
   server → test phrase. It opens by itself on every launch until the setup is
   finished.

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
  shows the status of each step and what to do when one is red.
* **Updates** — the “Check for updates” button shows the latest changelog,
  downloads the installer and verifies its SHA256.
* **GPT-SoVITS folder** — the path to the engine; the “Check” and “Browse…”
  buttons tell you exactly what is wrong instead of just “check the folder”.
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

## What's new in 1.2

* **First-run setup wizard** — four steps (engine, AnkiConnect, server, test
  phrase) with concrete instructions: what to download, where to unpack it and
  what to click. Until the setup is finished, the wizard opens by itself on
  every launch.
* **Update check** — the “Check for updates” button on the “Приложение” tab
  shows the changelog, downloads the installer and **always** verifies its
  SHA256 (if the release has no hash, downloading is refused). The hash is
  checked once more before the installer is started.
* **Live diagnostics** — the “Приложение” tab shows the state of the engine,
  Anki, the server, the voices and the test.
* **The installer now ships the reading subsystems** — five modules from `lab/`
  are added to the installed app: the reading system (provenance, domain
  dictionary, resolver) and QC v2. They never reached the installer before, so
  the app silently ran on the simple “is there sound” criterion.

The full list of changes is in [CHANGELOG.md](CHANGELOG.md) and in the
[v1.2 release](https://github.com/Daii1414/AnkiVoice/releases/tag/v1.2).

### Pronunciation check

GPT-SoVITS sometimes **loses a chunk of a phrase or invents an extra one**:
the duration is fine, the sound is speech, but the content is not. A
silence/length/loop check cannot see that — on 43 voiced cards it happened to
roughly one sentence out of twenty.

On the “Озвучка” tab, **“Проверять произношение”** (Check pronunciation)
makes the app recognize its own audio and compare it with the text.

* **the model lost a chunk** — the app re-synthesizes with another seed by
  itself and keeps the best take;
* **“·” in a furigana reading** no longer breaks the synthesis: it separates
  morphemes, it is not something to pronounce;
* **still in doubt** — the card is tagged `av_suspect` (find it in Anki with
  `tag:av_suspect`) and the audio is saved to `lab\rejected` so you can
  listen and decide.

Two buttons on the “Озвучка” tab:

* **“Проверить произношение”** (Check pronunciation) — recognizes the cards you
  have already voiced and shows where the model lost a chunk. Doubtful cards
  get the `av_suspect` tag right away;
* **“Переделать подозрительные”** (Re-do doubtful ones) — re-voices only the
  tagged cards, picking the best take by content again.

**How the reading is chosen.** In the “Источник чтения” select you can pick
the field the reading comes from, or “Как есть (кандзи, без фуриганы)” — then
the engine gets the kanji and reads it itself, with no furigana at all.
Measured on the same 150 sentences: with the furigana the check flags 4, in
“as is” mode it flags 12 — the model reads a term its own way, so the
comparison is noisier. The furigana mode is better for checking; “as is” is
fine when you want the natural reading.

**We check sentences, not words.** An isolated word is transcribed unreliably:
the measured “coverage” of a real failure and of a false alarm overlap
completely, so there is no threshold that separates them. Words are still
guarded by the acoustic QC (silence, tempo, length); the content check runs on
sentences, where the recogniser has context.

**The “Брак” (Rejects) deck — for your ears.** Doubtful pieces are collected
into `AnkiVoice_Брак`: a card with the expected text, the reason, the coverage
and the sounds — the original take and three variants side by side on one card.
Type “верно” (the sound really is bad) or “ложное сработавание” (the sound is fine)
into the “Вердикт” field and `pipeline.bat verdicts` shows whether our
thresholds are too low or too high.

**Where exactly it was lost.** With the Japanese acoustic model
(`reazon-research/japanese-wav2vec2-base-rs35kh`, ~370 MB in the HuggingFace
cache) the app aligns the expected text straight against the audio and shows
the time span where the sentence diverged. Without the model it falls back to
comparing the recognized text — coarser, but it still works.

**Thresholds are per voice.** One voice may sit at 0.95 coverage, another at
0.85. The app measures the norm from the accepted pieces and compares against
it, not against one global number.

**Fields are per deck.** Field settings are stored in a per-deck profile: pick
another deck and its fields are applied.

On a real collection: 56 voiced pieces, 4 of them broken; after the automatic
re-do only 1 was left (an exotic term worth listening to). No false positives
on the checked deck.

Requirements: `faster-whisper` in the GPT-SoVITS Python and one downloaded
model (in the HuggingFace cache). Without them the toggle simply does nothing
and dubbing works as before. One clip costs about 0.5 s on a GPU.

Separately about the text: it is no longer split the Chinese way (`cut5`) —
that is exactly where chunks were lost. Short sentences (a typical card) are
synthesized whole, long ones are split at “。”.

## How kanji are read

GPT-SoVITS accepts text only, so somebody has to read the kanji. On the
“Поля колоды” tab that is the job of **two different rows**, and they are easy
to mix up:

| Row | What it does | Default |
|---|---|---|
| **Word furigana ← field** | Reads **only the main word** strictly from that field's furigana; everything else is read automatically. Always active when a field is selected, even if “Reading source” is set to “Do not substitute” | `ExpressionFurigana` |
| **Reading source** | The older way: substitutes a ready-made reading **into the whole sentence**, not only into the main word. Switched on only by picking a field explicitly | “Do not substitute” (`off`) |

If both rows are set, the **furigana wins** for the main word — it is applied
last. In practice:

* a deck with `ExpressionFurigana` → “Word furigana ← field” =
  `ExpressionFurigana`, “Reading source” = “Do not substitute”;
* a deck without furigana → leave both rows at their defaults: the word and
  the sentence are read by the built-in Haqumei core, with Sudachi 0.7 and
  UniDic 20261015 as the fallback.

In the console these are the flags `--furigana-src FIELD` (furigana of the main
word) and `--reading off|FIELD` (a ready-made reading for the whole sentence).

Safety rules for the substitution: hiragana/katakana only, only if the word is
found in the sentence, otherwise the card is left as is.

**What furigana buys you (measured on real cards):**

* readings from the field and the automatic Haqumei reading **match in 77% of
  cases** (a random sample of 100 cards with non-empty furigana);
* for domain terms the **field is more precise**: `亜鉛鍍金` → あえん**めっき**
  (the core gives あえんときん), `I形梁` → あいがた**ば**り, `IAEE` → by letters;
* sometimes the field contains junk or a list of readings — then automation
  saves the day;
* the rest is markup, spaces and variants that sound the same.

Bottom line: a deck with `ExpressionFurigana` → furigana on; without furigana →
both rows by default, Haqumei reads (Sudachi is the fallback).

## How text becomes hiragana

GPT-SoVITS parses Japanese with its own morphology (MeCab) and gets rare terms
and katakana abbreviations wrong — that is why the `kanaize()` pipeline
prepares the text itself, strictly step by step:

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
--reading off|FIELD                   a ready-made reading for the whole sentence (see above)
```

## Console

`pipeline.bat` is the same thing in a console; it finds the engine folder on
its own:

```
pipeline.bat list              list the voices
pipeline.bat selftest          check the environment (run this when in trouble)
pipeline.bat test --voice madara --text "こんにちは"
pipeline.bat voice --voice madara --deck "Архитектура" --mode both
pipeline.bat check --deck "Архитектура"          full deck check
pipeline.bat check --deck "Архитектура" --fast   same without downloading audio
pipeline.bat scan --apply     find voices in the engine and add them to voices.json
pipeline.bat doctor           short environment diagnostics
```

The exe has diagnostics too: `AnkiVoice.exe doctor`.

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

A rebuild is needed only after editing `anki_gui.py`, `anki_web.py` or
`anki_web_page.py` — `voice_pipeline.py` runs from disk and takes effect
immediately.

**exe** (needs the Python from the GPT-SoVITS engine with PyInstaller):

```bat
set ENGINE=C:\Path\To\GPT-SoVITS
%ENGINE%\runtime\python.exe -m pip install pyinstaller
%ENGINE%\runtime\python.exe -m PyInstaller --noconfirm --onefile --windowed ^
    --name AnkiVoice --distpath . --workpath %TEMP%\pyi_build --specpath %TEMP% anki_gui.py
```

**installer** (Inno Setup 6, run it from the repository root):

```bat
ISCC.exe AnkiVoice.iss
```

→ produces `dist\AnkiVoice-Setup-1.2.exe`.

**tests** (Python 3.12+, no GPU and no network needed):

```bash
python -m pip install numpy haqumei
python lab/qc_unit.py
python lab/quality_unit.py
python lab/test_g2p_infrastructure.py
python lab/test_v12_features.py
python lab/web_js_check.py
python lab/integration_check.py
```

`lab/robust_tests.py` — 10 robustness checks of the pipeline; it needs a
running Anki. CI runs everything else on every push
([checks.yml](.github/workflows/checks.yml)) and builds the installer on
windows-latest.

## Repository layout

| File | What it is |
|---|---|
| `AnkiVoice.exe` | The app with the interface (double-click) |
| `AnkiVoice.iss` | Installer build script (Inno Setup 6) |
| `voice_pipeline.py` | All logic: synthesis, kanji reading, substitution, CLI |
| `anki_gui.py` | Exe entry point: web UI by default, `--classic` for the old window |
| `anki_web.py` | Local HTTP server for the UI (127.0.0.1 only) |
| `anki_web_page.py` | HTML/CSS/JS for the page (offline, no CDN) |
| `pipeline.bat` | Console entry point |
| `sudachi_g2p.py` | Fallback “reader” helper: SudachiPy 0.7 + UniDic dictionary |
| `g2p_core.py` | Haqumei reading core: word in sentence context, pron form |
| `kana_stress.py` | A battery of 63 difficult words for reading checks |
| `pyruntime.zip` | Bundled Python + Haqumei 0.12.2 + SudachiPy 0.7 (~44 MB, unpacks itself) |
| `sudachidict.zip` | Sudachi core dictionary 20261015 (~73 MB, unpacked by the helper) |
| `voices.json` | Voice registry: weights, references, prompt, sampling |
| `lab/` | Reading system and QC v2 modules (five files are shipped) + tests and dev tools |
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
