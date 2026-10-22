# -*- coding: utf-8 -*-
"""Дополнить сравнение движков и добавить снимок интерфейса в шапку."""
import io
import os

ROOT = os.environ["AV_ROOT"]


def patch(path, pairs):
    p = os.path.join(ROOT, path)
    s = io.open(p, encoding="utf-8").read()
    for old, new in pairs:
        if old not in s:
            print("  ! не найдено в", path, ":", old.strip().split("\n")[0][:60])
            continue
        s = s.replace(old, new, 1)
        print("  ok", path, ":", old.strip().split("\n")[0][:52])
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


RU_OLD = """| | GPT-SoVITS | IndexTTS 2.5 |
|---|---|---|
| голос | файлы `.ckpt` + `.pth` + референс | **один референс** (3–10 с) |
| веса | свои у каждого голоса | общие у модели |
| как ставится | распакованный архив | `git clone` + `uv sync --extra webui` + веса в `checkpoints` |
| своё чтение японского | g2p движка | свой японский g2p (`ja_g2p`) |"""

RU_NEW = """| | GPT-SoVITS | IndexTTS 2.5 |
|---|---|---|
| голос | файлы `.ckpt` + `.pth` + референс | **один референс** (3–10 с) |
| веса | свои у каждого голоса | общие у модели |
| как ставится | распакованный архив | `git clone` + `uv sync --extra webui` + веса в `checkpoints` |
| размер на диске | 6–10 ГБ (веса отдельно) | ~5 ГБ весов модели |
| своё чтение японского | g2p движка | свой японский g2p (`ja_g2p`) |
| проверка произношения | есть (faster-whisper в окружении) | нет, только акустический QC |
| ручные настройки звука | seed, temperature, top_p, top_k | нет, интерфейс прячет |
| для кого | хочу качество и контроль | хочу минимум возни: один референс |

Переключение — двумя большими карточками на главном экране."""

EN_OLD = """| | GPT-SoVITS | IndexTTS 2.5 |
|---|---|---|
| a voice | `.ckpt` + `.pth` files + a reference | **one reference** (3-10 s) |
| weights | per voice | shared by the model |
| install | unpacked archive | `git clone` + `uv sync --extra webui` + weights in `checkpoints` |
| Japanese reading | the engine's g2p | its own Japanese g2p (`ja_g2p`) |"""

EN_NEW = """| | GPT-SoVITS | IndexTTS 2.5 |
|---|---|---|
| a voice | `.ckpt` + `.pth` files + a reference | **one reference** (3-10 s) |
| weights | per voice | shared by the model |
| install | unpacked archive | `git clone` + `uv sync --extra webui` + weights in `checkpoints` |
| size on disk | 6-10 GB (weights separate) | ~5 GB of model weights |
| Japanese reading | the engine's g2p | its own Japanese g2p (`ja_g2p`) |
| pronunciation check | yes (faster-whisper in the environment) | no, acoustic QC only |
| manual sound settings | seed, temperature, top_p, top_k | none, the UI hides them |
| who it is for | I want quality and control | I want as little fuss as possible: one reference |

You switch between them with two large cards on the main screen."""

# снимок интерфейса сразу после шапки — чтобы было видно, что это за программа
RU_SHOT_OLD = """**Русский** | [English](README.en.md)

---

## Оглавление"""

RU_SHOT_NEW = """<p align="center"><img src="doc/shots/voice-dark.png" alt="Интерфейс AnkiVoice: выбор движка, колода, голос и кнопка «Начать озвучку»" width="820"></p>

**Русский** | [English](README.en.md)

---

## Оглавление"""

EN_SHOT_OLD = """[Русский](README.md) | **English**

---

## Table of contents"""

EN_SHOT_NEW = """<p align="center"><img src="doc/shots/voice-dark.png" alt="The AnkiVoice interface: engine choice, deck, voice and the Start dubbing button" width="820"></p>

[Русский](README.md) | **English**

---

## Table of contents"""

patch("README.md", [(RU_OLD, RU_NEW), (RU_SHOT_OLD, RU_SHOT_OLD + "")])  # снимок — отдельным шагом
patch("README.en.md", [(EN_OLD, EN_NEW)])

# снимок интерфейса — отдельной правкой, чтобы не мешать замене
for path, old, new in (("README.md", RU_SHOT_OLD, RU_SHOT_NEW),
                       ("README.en.md", EN_SHOT_OLD, EN_SHOT_NEW)):
    p = os.path.join(ROOT, path)
    s = io.open(p, encoding="utf-8").read()
    if old in s and new not in s:
        s = s.replace(old, new, 1)
        io.open(p, "w", encoding="utf-8", newline="\n").write(s)
        print("  ok", path, ": снимок интерфейса в шапке")
    else:
        print("  ! шапка со снимком не найдена в", path)
print("готово")
