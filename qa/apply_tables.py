# -*- coding: utf-8 -*-
"""Таблицы вместо простыней — по предложению qa/design/b/PROPOSAL.md.

Заменяем: «Требования» -> две таблицы, «Если что-то не работает» -> таблица
«симптом -> причина -> что делать», добавляем «Что перезаписывается и что
уходит в сеть» и сравнение движков.
"""
import io
import os

ROOT = os.environ["AV_ROOT"]


def patch(name, pairs):
    p = os.path.join(ROOT, name)
    s = io.open(p, encoding="utf-8").read()
    for old, new in pairs:
        if old not in s:
            print("  ! не найдено в", name, ":", old.strip().split("\n")[0][:70])
            continue
        s = s.replace(old, new, 1)
        print("  ok", name, ":", old.strip().split("\n")[0][:56])
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


# ---------------------------------------------------------------- требования
RU_REQ_OLD = """## Требования

1. **Windows 10/11** и GPU с CUDA (комфортно — от 6 ГБ видеопамяти), драйвер
   NVIDIA свежей версии (нужна CUDA 12.8+ под IndexTTS 2.5).
2. **Один из двух движков** — выбираешь в мастере при первом запуске:
   * **[GPT-SoVITS v2Pro](https://github.com/RVC-Boss/GPT-SoVITS/releases)** —
     распакованный архив Windows-пакета, примерно **6–10 ГБ** (веса голосов в
     него не входят);
   * **[IndexTTS 2.5](https://github.com/index-tts/index-tts)** — `git clone` +
     `uv sync --extra webui` + веса модели (~5 ГБ) в папку `checkpoints`.
3. **Своя модель голоса.** Для GPT-SoVITS — пара файлов `.ckpt` + `.pth` и
   референс 3–10 с; для IndexTTS 2.5 — **один референс** 3–10 с (веса общие у
   модели). Готовые голоса можно взять у движка или скачать со страниц
   сообщества.
4. **Anki** с включённым **AnkiConnect** (плагин отвечает на `127.0.0.1:8765`).

Больше ничего ставить не нужно: словарь чтения и встроенный Python уже внутри
установщика (`pyruntime.zip`, `sudachidict.zip`) и разворачиваются сами.

**Интернет** нужен только чтобы скачать установщик и движок — сама озвучка
полностью офлайн. На диске нужно примерно **1 ГБ** под приложение (сам
установщик — 125 МБ) плюс место под движок и его веса."""

RU_REQ_NEW = """## Что нужно до установки

| Что | Где взять | Размер | Обязательно | Зачем |
|---|---|---|---|---|
| **AnkiVoice** (программа) | [Releases](https://github.com/Daii1414/AnkiVoice/releases/latest) → `AnkiVoice-Setup-1.8.exe` | 125 МБ, ~1 ГБ на диске | да | окно, локальный сервер, словарь чтения |
| **Anki + AnkiConnect** | Anki → Дополнения → код `2055492159` | ~0 МБ | да | мост к колодам и полям |
| **Движок** (один из двух) | [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS/releases) или [IndexTTS 2.5](https://github.com/index-tts/index-tts) | 6–10 ГБ или ~5 ГБ | да, один | синтез речи |
| **Голос** | в движке или у сообщества | веса + референс 3–10 с | да | тембр и характер речи |
| **Модель распознавания** | кэш HuggingFace (`faster-whisper`) | ~1,5 ГБ | нет | только проверка произношения |
| **GPU и драйвер NVIDIA** | драйвер NVIDIA, CUDA 12.8+ | от 6 ГБ VRAM | да | синтез на видеокарте |

Интернет нужен только чтобы скачать — сама озвучка идёт полностью офлайн.

### Приложение и движок — это разные установки

| Вопрос | AnkiVoice (приложение) | Движок синтеза | Подсказка |
|---|---|---|---|
| Откуда берётся | GitHub Releases, один файл | официальный релиз движка | движок качается отдельно |
| Размер | 125 МБ, на диске ~1 ГБ | 6–10 ГБ / ~5 ГБ | в 5–10 раз тяжелее |
| Что внутри | интерфейс, сервер, словарь чтения | модель и веса голосов | звук делает движок |
| Если его нет | приложение работает, синтеза нет | озвучка невозможна | сначала ставим движок |

Больше ничего ставить не нужно: словарь чтения и встроенный Python уже внутри
установщика (`pyruntime.zip`, `sudachidict.zip`) и разворачиваются сами."""

EN_REQ_OLD = """## Requirements

1. **Windows 10/11** and a CUDA GPU (comfortably from 6 GB of video memory) with a recent
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
4. **Anki** with **AnkiConnect** enabled (the addon answers on `127.0.0.1:8765`).

Nothing else has to be installed: the reading dictionary and the bundled Python
are already inside the installer (`pyruntime.zip`, `sudachidict.zip`) and
unpack themselves.

The **internet** is only needed to download the installer and the engine - the
dubbing itself is fully offline. Allow about **1 GB** of disk for the app (the
installer itself is 125 MB) plus room for the engine and its weights."""

EN_REQ_NEW = """## What you need before installing

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

patch("README.md", [(RU_REQ_OLD, RU_REQ_NEW)])
patch("README.en.md", [(EN_REQ_OLD, EN_REQ_NEW)])
print("готово")
