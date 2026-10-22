# -*- coding: utf-8 -*-
"""Английский README: таблицы вместо простыней."""
import io
import os

ROOT = os.environ["AV_ROOT"]
p = os.path.join(ROOT, "README.en.md")
s = io.open(p, encoding="utf-8").read()

OLD = """## Requirements

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
installer itself is 125 MB) plus room for the engine and its weights."""

NEW = """## What you need before installing

| What | Where to get it | Size | Required | Why |
|---|---|---|---|---|
| **AnkiVoice** (the app) | [Releases](https://github.com/Daii1414/AnkiVoice/releases/latest) → `AnkiVoice-Setup-1.8.exe` | 125 MB, ~1 GB on disk | yes | the window, the local server, the reading dictionary |
| **Anki + AnkiConnect** | Anki → Add-ons → code `2055492159` | ~0 MB | yes | the bridge to your decks and fields |
| **An engine** (one of two) | [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS/releases) or [IndexTTS 2.5](https://github.com/index-tts/index-tts) | 6-10 GB or ~5 GB | yes, one | speech synthesis |
| **A voice** | with the engine or from the community | weights + a 3-10 s reference | yes | timbre and speech character |
| **The recognition model** | HuggingFace cache (`faster-whisper`) | ~1.5 GB | no | the pronunciation check only |
| **GPU and NVIDIA driver** | NVIDIA driver, CUDA 12.8+ | from 6 GB VRAM | yes | synthesis on the GPU |

The internet is only needed to download - the dubbing itself runs fully offline.

### The app and the engine are two separate installations

| Question | AnkiVoice (the app) | The engine | Hint |
|---|---|---|---|
| Where it comes from | GitHub Releases, one file | the engine's own release | the engine is downloaded separately |
| Size | 125 MB, ~1 GB on disk | 6-10 GB / ~5 GB | five to ten times heavier |
| What's inside | the UI, the server, the reading dictionary | the model and the voice weights | the engine makes the sound |
| If it's missing | the app runs, there is no synthesis | dubbing is impossible | install the engine first |

Nothing else has to be installed: the reading dictionary and the bundled Python
are already inside the installer (`pyruntime.zip`, `sudachidict.zip`) and
unpack themselves."""

if OLD not in s:
    print("! не найдено")
else:
    s = s.replace(OLD, NEW, 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("ok README.en.md: таблица требований")
