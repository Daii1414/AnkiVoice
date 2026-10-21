# -*- coding: utf-8 -*-
"""Правки README.en.md по итогам разбора страницы проекта новым посетителем."""
import io
import os

ROOT = os.environ["AV_ROOT"]
p = os.path.join(ROOT, "README.en.md")
s = io.open(p, encoding="utf-8").read()


def sub(a, b):
    global s
    if a not in s:
        print("  НЕ НАЙДЕНО:", a[:70].replace("\n", " "))
        return
    s = s.replace(a, b, 1)
    print("  ok:", a[:50].replace("\n", " "))


sub("""<p align="center"><b>Offline Japanese audio for Anki decks, in the GPT-SoVITS voice.</b><br>""",
    """<p align="center"><b>Offline Japanese audio for Anki decks, in the GPT-SoVITS or IndexTTS 2.5 voice.</b><br>""")

sub("""<p align="center">
  <a href="#features">Features</a> •""",
    """<p align="center">
  <a href="https://github.com/Daii1414/AnkiVoice/releases/latest">
    <img alt="Download AnkiVoice 1.6 for Windows" src="https://img.shields.io/badge/%E2%96%A8%20Download%20AnkiVoice%201.6%20%E2%80%94%20125%20MB-4F46E5">
  </a>
</p>

<p align="center">
  <a href="#features">Features</a> •""")

sub("""goes straight into the Anki fields. The internet is only needed to download.</p>""",
    """goes straight into the Anki fields. <b>Free, no accounts, no telemetry.</b> The internet is only needed to download.</p>""")

sub("""## Requirements

1. **Windows 10/11** and a CUDA GPU (comfortably from 6 GB of video memory).
2. **GPT-SoVITS** installed and launched at least once (a folder with
   `runtime\\python.exe` and `api_v2.py`).
3. **Anki** with **AnkiConnect** enabled (the addon answers on `127.0.0.1:8765`).""",
    """## Requirements

1. **Windows 10/11** and a CUDA GPU (comfortably from 6 GB of video memory) with a
   recent NVIDIA driver (CUDA 12.8+ is needed for IndexTTS 2.5).
2. **One of the two engines** - pick it in the wizard on the first run:
   * **[GPT-SoVITS v2Pro](https://github.com/RVC-Boss/GPT-SoVITS/releases)** -
     the unpacked Windows package, roughly **6-10 GB** (voice weights are not
     included);
   * **[IndexTTS 2.5](https://github.com/index-tts/index-tts)** - `git clone` +
     `uv sync --extra webui` + the model weights (~5 GB) in `checkpoints`.
3. **A voice of your own.** For GPT-SoVITS: a `.ckpt` + `.pth` pair and a 3-10 s
   reference clip; for IndexTTS 2.5: **one reference clip** of 3-10 s (the
   weights belong to the model). The engine ships its own voices.
4. **Anki** with **AnkiConnect** enabled (the addon answers on `127.0.0.1:8765`).""")

sub("""1. Download **`AnkiVoice-Setup-1.6.exe`** from the
   [Releases](https://github.com/Daii1414/AnkiVoice/releases/latest) page — one
   file with everything inside.
2. Run it: **“Далее” → “Установить” → “Завершить”** (Next → Install → Finish;
   the “Launch AnkiVoice” checkbox is on, so the app opens by itself).""",
    """1. Download **`AnkiVoice-Setup-1.6.exe`** from the
   [Releases](https://github.com/Daii1414/AnkiVoice/releases/latest) page — one
   file with everything inside. Size **125 MB**, SHA256:
   `385481551c6404ec8927a37d6c234630c87ee71660aa5c689eab9654da0dbc28`
2. Run it: **“Далее” → “Установить” → “Завершить”** (Next → Install → Finish;
   the “Launch AnkiVoice” checkbox is on, so the app opens by itself).
   > [!IMPORTANT]
   > The installer is not digitally signed, so Windows shows a blue SmartScreen
   > window. Click **“More info” → “Run anyway”** - the usual warning for files
   > downloaded outside the store.""")

sub("""[release v1.2](https://github.com/Daii1414/AnkiVoice/releases/tag/v1.2).""",
    """[release v1.6](https://github.com/Daii1414/AnkiVoice/releases/tag/v1.6).""")

io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("README.en.md сохранён")
