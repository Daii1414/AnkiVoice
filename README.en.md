# AnkiVoice

[Русский](README.md) | **English**

> **Local Japanese audio for Anki — context-aware kanji readings via Haqumei (Sudachi/UniDic fallback), voices via GPT-SoVITS. Fully offline, nothing to install.**

AnkiVoice voices Anki decks with GPT-SoVITS. It reads kanji with a modern
dictionary, can substitute trusted readings from a card's furigana, clones
the selected voice and writes ready ogg files straight into card fields.
Everything runs locally: the internet is only needed to download it.

The full technical description (architecture, all logic, bug history) is in
`PROJECT.md` (in Russian). This file covers installation and usage.

*The app interface is currently in Russian; UI labels are quoted as they
appear, with English explanations.*

## Built on

Speech synthesis is done by **[GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)** —
an open few-shot TTS engine (MIT license). AnkiVoice does not copy its code:
the engine runs as a normal local server on `127.0.0.1:9880`, and AnkiVoice
sends it text and receives the finished audio. That is why GPT-SoVITS's own
web UI and any of its voices keep working alongside AnkiVoice.

What this means in practice: **5 seconds** of reference audio and the voice
already speaks; **a minute** of training data noticeably improves similarity.

Few-shot demo on an unseen speaker (Chinese and Japanese, 1:26):

https://github.com/user-attachments/assets/f954276c-40ca-4a8a-a4f3-39ad4fb1a4a4

*The file is also kept in the repository — [doc/gptsovits/gpt-sovits-demo.mp4](doc/gptsovits/gpt-sovits-demo.mp4).
Original: [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS).*

AnkiVoice is built against **v2Pro**. Their measured speed:
RTF **0.028** on an RTX 4060 Ti and **0.014** on an RTX 4090 (about 4 minutes
of speech in 3 seconds), **0.526** on an M4 CPU.

Voice similarity on the SeedTTS test set (higher is better, GPT-SoVITS in blue):

<img src="doc/gptsovits/gpt-sovits-similarity.png" width="780"
     alt="GPT-SoVITS voice similarity on the SeedTTS test set">

Credits: [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) — the engine;
[gradio](https://github.com/gradio-app/gradio) — the slider layout on the
Voice tab is styled after theirs; [Haqumei](https://github.com/o24s/haqumei) —
context-aware kanji readings (the main engine); [Sudachi](https://github.com/WorksApplications/SudachiPy)
and the UniDic dictionary — fallback and reading checks.

## Requirements

1. **Windows 10/11** and a CUDA GPU (6 GB of VRAM is comfortable).
2. **GPT-SoVITS** installed and started at least once (the folder with
   `runtime\python.exe` and `api_v2.py`).
3. **Anki** with **AnkiConnect** enabled (the plugin listens on `127.0.0.1:8765`).

Nothing else: kanji reading runs on the **bundled Python**
(`pyruntime.zip` with Haqumei and `sudachidict.zip` are already inside the
installer and unpack themselves on first launch — no separate installs).

## Quick start

1. Download **`AnkiVoice-Setup-1.1.exe`** from the [Releases](https://github.com/Daii1414/AnkiVoice/releases)
   page — one file with everything inside.
2. Run it: **“Далее”** → **“Установить”** → **“Завершить”** (Next → Install → Finish;
   the “Launch AnkiVoice” checkbox is on, so the app opens by itself).
3. Point it to the GPT-SoVITS folder (it usually finds it automatically and
   remembers the path).
4. On the **“Голос”** (Voice) tab pick a voice → on the **“Поля колоды”**
   (Deck fields) tab pick a deck and fields → on the **“Озвучка”** (Dubbing)
   tab press **“Начать озвучку”** (Start dubbing).

The app starts a local server and opens a page in your browser — that is
normal, nothing else needs to be installed.

It installs into your user profile (`AppData\Local\Programs\AnkiVoice`) and
does not ask for administrator rights. To uninstall: Start menu → “Удалить
AnkiVoice”. The first launch takes longer (~10 seconds) because the bundled
Python and dictionary are unpacked. After that everything is fast.

## Interface (four tabs)

The UI is a local web page (`anki_web.py`): the server listens only on
`127.0.0.1`, nothing goes outside. The page works offline, without a CDN.
The old tkinter window is still available via the `--classic` flag.

### “Озвучка” tab — the main screen

![Dubbing tab](doc/shots/voice-dark.png)

* **Deck** and **Voice** — lists pulled from Anki and `voices.json`.
* **What to voice** — “word + sentence” (the usual choice), sentence only or
  word only; a card limit (0 = all); “rebuild everything” ignores cards that
  are already done.
* **“Начать озвучку”** (Start dubbing) — the main button; next to it are
  **“Остановить”** (Stop), **“Проверить колоду”** (Check deck) and
  **“Самопроверка”** (Self-test).
* **Progress bar** — an exact “N / total” counter and the error count.
* **Log** — a live SSE stream with color coding: green = done, red = error,
  yellow = rejected and QC retries. The “Follow” option scrolls the log
  automatically.

### “Поля колоды” tab — what to read from where

![Deck fields tab](doc/shots/anki-dark.png)

* **Deck** + the **“Поля выбранной колоды”** (Fields of the selected deck)
  button — fills the role table automatically from the template
  (Sentence / Expression / *Audio / Furigana).
* Table rows: sentence text, sentence audio, main word, word audio,
  **word furigana ← field** and the reading source.
* An empty choice in the “→” column means “do not write audio”. Empty
  furigana means the word will be read automatically.

### “Голос” tab — reference and speech character

![Voice tab](doc/shots/sound-dark.png)

* **Voice cards** — every voice from `voices.json`; ✅/✗ shows whether the
  gpt/sovits/ref files were found.
* **Reference (3–10 s)** — the voice sample: file, its text and language.
  Do not use a long aux reference — the API will run out of memory.
* **Speech character** — `temperature`/`top_p`/`top_k`/`speed` sliders and a
  `seed` field: lower values give more even, calmer speech (defaults from the
  official web UI: 0.6 / 0.6 / 20).
* **“Прослушать тест”** (Play test) — a quick voice check; the file plays
  right on the page. **“Обновить веса в движке”** (Refresh engine weights) —
  scans for new weights.

### “Приложение” tab — engine folder and diagnostics

![App tab](doc/shots/app-dark.png)

* **GPT-SoVITS folder** — the path to the engine; the “Check” and “Browse…”
  buttons tell you exactly what is wrong instead of just “check the folder”.
* **Diagnostics** — everything at once: tool, config, path, Anki, server,
  voice list. Look here first if something does not work.
* **Where the files are** — the app folder and config.

Header statuses: **Anki** (connected?), **Server** (GPT-SoVITS running) and
an indicator for the operation in progress. The theme is switched by the
button on the right.

Light theme — the same tabs: [Dubbing](doc/shots/voice-light.png),
[Deck fields](doc/shots/anki-light.png), [Voice](doc/shots/sound-light.png),
[App](doc/shots/app-light.png). A full-page snapshot:
[voice-dark-full.png](doc/shots/voice-dark-full.png).

## Word reading modes (important)

GPT-SoVITS accepts text only, so someone has to read the kanji. On the
“Deck fields” tab this is handled by **two different rows**, and they are easy
to confuse:

| Row | What it does | Default |
|---|---|---|
| **Word furigana ← field** | Reads **only the main word** strictly from the furigana in this field; the rest of the text is read automatically. Always works when the field is selected, even if “Reading source” is set to “Do not substitute” | `ExpressionFurigana` |
| **Reading source** | The older method: substitutes a ready reading **into the whole sentence**, not just the main word. Enabled only when a field is explicitly selected | “Do not substitute” (`off`) |

If both rows are selected, **furigana wins** for the main word — it is applied
last. In practice:

* a deck with `ExpressionFurigana` → “Word furigana ← field” =
  `ExpressionFurigana`, “Reading source” = “Do not substitute”;
* a deck without furigana → leave both rows at their defaults: the bundled
  Haqumei engine reads the word and the sentence, with Sudachi 0.7 + UniDic
  20261015 as the fallback.

On the command line these are `--furigana-src FIELD_NAME` (furigana for the
main word) and `--reading off|FIELD_NAME` (ready reading for the whole
sentence).

Substitution safety rules: pure kana only, and only if the word is found in
the sentence as a whole; otherwise the card is left as is.

**What furigana gives you (measurements on real cards):**

* field readings and automatic Haqumei readings **match in 77% of cases**
  (a random sample of 100 cards with non-empty furigana);
* for domain terms the **field is more accurate**: `亜鉛鍍金` →
  あえん**めっき** (the engine gives あえんときん), `I形梁` →
  あいがた**ば**り, `IAEE` → read letter by letter;
* sometimes the field contains garbage or a list of readings — then the
  automation saves the day;
* the rest is markup, spaces and variants that sound the same.

Bottom line: a deck with `ExpressionFurigana` → turn furigana on; without
furigana → keep both rows at their defaults and let Haqumei read (Sudachi is
the fallback).

## How text becomes hiragana

GPT-SoVITS parses Japanese with its own morphological analyzer (MeCab) and
makes mistakes on rare terms and katakana abbreviations — so the `kanaize()`
pipeline prepares the text itself, strictly step by step:

1. **NFKC normalization** — full-width letters/digits and half-width
   katakana are reduced to normal forms (punctuation is left alone);
2. **Latin → katakana letter by letter** (`IEC` → アイイーシー);
3. **katakana → hiragana** (the greetings コンニチハ/コンバンハ stay in
   katakana — otherwise MeCab reads them as a particle; repetition marks
   ヽゝゞヾ are expanded from context — repeating the previous syllable);
4. **g2p only for the remaining kanji**: Haqumei reads every word in the
   context of the sentence (sandhi, neighbouring katakana); the fallbacks are
   Sudachi with the UniDic dictionary and pyopenjtalk (MeCab); digits always
   go through MeCab because Sudachi reads numbers as dates (2024 → 二月二日);
5. **a second katakana → hiragana pass** — and pure hiragana goes to the API.

What the pipeline **does not touch**: the note in Anki itself (a copy of the
text is processed) and the card's furigana (used only as a reading source).

Reading checks are built in: `pipeline.bat selftest` (10 substitution checks
and 11 reading-mode checks) and the extended battery
`python kana_stress.py` (63 difficult words).

## Card fields

Different decks name their fields differently — where to take text from and
where to write audio is configurable (GUI: the “Deck fields” tab; console:
the `voice` / `make-deck` / `check` commands):

```
--sentence-src "Sentence"        field with the sentence text
--sentence-audio "SentenceAudio" field where the sentence audio is written
--word-src "Expression"          field with the word (Expression enables furigana parsing)
--word-audio "ExpressionAudio"   field where the word audio is written
--furigana-src "ExpressionFurigana"  field with furigana for the main word
--reading off|FIELD_NAME         ready reading for the whole sentence (see above)
```

## Command line (without the exe)

`pipeline.bat` does the same in a console and finds the engine folder itself:

```
pipeline.bat list              list voices
pipeline.bat selftest          check the environment (run it when in trouble)
pipeline.bat test --voice madara --text "こんにちは"
pipeline.bat voice --voice madara --deck "Архитектура" --mode both
pipeline.bat check --deck "Архитектура"          full deck check
pipeline.bat check --deck "Архитектура" --fast   same without downloading audio (30x faster)
pipeline.bat scan --apply     find voices in the engine and add them to voices.json
pipeline.bat doctor           short environment diagnostics
```

The exe has diagnostics too: `AnkiVoice.exe doctor`.

## Troubleshooting

| Message | What to do |
|---|---|
| `Не найдена папка GPT-SoVITS` | Set the path: `gptsovits_path.txt`, the `GPT_SOVITS_ROOT` environment variable, or the “Browse…” button in the app |
| `AnkiConnect недоступен` | Open Anki and make sure AnkiConnect is installed/enabled |
| `Референс X с — API требует 3–10 с` | Trim the clip to 3–10 seconds |
| `Не получилось переключить... Перезапуск` | Normal: the pipeline restarts the server and retries |
| `сервер вернул пустой звук` | Usually VRAM is occupied by other processes (browser, games). Close them or restart the server: `pipeline.bat serve --voice <voice>` |
| `Пайплайн уже запущен другим процессом` | Wait for the first run to finish (protection against double work) |
| Windows: “Защитил ваш компьютер” | The downloaded exe is unsigned: in the SmartScreen window click “More info” → “Run anyway” |

Useful: `selftest` prints exactly what it sees (engine, voices, reading
dictionary, AnkiConnect, server) — 90% of problems are visible immediately.

## Limitations (tested in practice)

* **The reference must be exactly 3–10 seconds** — the API rejects anything
  outside that range.
* **The engine needs ~4–6 GB of free RAM** at startup; a long aux reference
  causes a CUDA OOM on a 6 GB GPU.
* **Do not use `localhost` in the AnkiConnect URL** — IPv6 resolution adds
  delays of seconds (the code uses `127.0.0.1` everywhere).
* A corporate proxy/VPN does not interfere — local requests bypass it.
* A note open in the Anki editor does not accept writes — the pipeline asks
  you to close the editor and continues.
* Large decks are processed in chunks; cards that already have audio are
  skipped (unless `--force`).

## Rebuilding the exe

Changes to `voice_pipeline.py` do not require rebuilding the exe — it runs
the pipeline from disk. Rebuild only after editing `anki_gui.py`,
`anki_web.py` or `anki_web_page.py` (~20 seconds):

```
set ENGINE=C:\Path\To\GPT-SoVITS
%ENGINE%\runtime\python.exe -m pip install pyinstaller
%ENGINE%\runtime\python.exe -m PyInstaller --noconfirm --onefile --windowed ^
    --name AnkiVoice --distpath . --workpath %TEMP%\pyi_build --specpath %TEMP% anki_gui.py
```

The installer is built with Inno Setup 6 (the script is already in the repo):

```
ISCC.exe AnkiVoice.iss
```

→ produces `dist\AnkiVoice-Setup-1.1.exe`.

## Repository structure

| File | What it is |
|---|---|
| `AnkiVoice.exe` | The app with the interface (double-click) |
| `AnkiVoice.iss` | Installer build script (Inno Setup 6) |
| `voice_pipeline.py` | All logic: synthesis, kanji reading, substitution, CLI |
| `anki_gui.py` | Exe entry point: web UI by default, `--classic` for the old window |
| `anki_web.py` | Local HTTP server for the UI (127.0.0.1 only) |
| `anki_web_page.py` | HTML/CSS/JS for the page (offline, no CDN) |
| `pipeline.bat` | Console entry point |
| `sudachi_g2p.py` | Fallback “reader” helper: SudachiPy 0.7 + 20261015 dictionary |
| `g2p_core.py` | Haqumei reading core: words in sentence context, pron form |
| `pyruntime.zip` | Bundled Python 3.13 + Haqumei 0.12.2 + SudachiPy 0.7.0 (~44 MB, unpacks itself) |
| `sudachidict.zip` | Sudachi core dictionary 20261015 (~73 MB, unpacked by the helper) |
| `voices.json` | Voice registry: weights, references, prompt, sampling |
| `kana_stress.py` | A battery of 63 difficult words for reading checks |
| `anki_tts.py` | Old standalone script, kept for history, unused |
| `doc/` | UI screenshots and engine media for the README |
| `lab/` | Tests and helper scripts (not included in the installer) |
| `.github/workflows/checks.yml` | CI: compile and tests on every push |
| `README.md`, `README.en.md`, `PROJECT.md` | Instructions (RU/EN) and the full technical description |
| `LICENSE` | AGPL-3.0 |

Not tracked by git: `gptsovits_path.txt`, `pyruntime/` (unpacked from the
zip), `test_*.ogg`, `logs/`.

## Updates and releases

* **Update**: download the new installer from Releases and simply run it over
  the old version — the engine path and settings are preserved.
* **Uninstall**: Start menu → “Удалить AnkiVoice” (settings remain and are
  picked up again on the next install).
* A release is one file, `AnkiVoice-Setup-x.y.exe`, on [Releases](https://github.com/Daii1414/AnkiVoice/releases).
* For developers: clone the repo, `git pull`, and run from disk — everything
  works without installation.

## License

**AGPL-3.0** (the text is in the `LICENSE` file): anyone who modifies and
distributes this tool must publish the source of their changes, including
when it is used over a network.
