# -*- coding: utf-8 -*-
"""Переписать шапку README по макету qa/design/a/hero.svg."""
import io
import os

ROOT = os.environ["AV_ROOT"]

RU_OLD = """<p align="center"><b>Локальная озвучка японских карточек Anki голосом GPT-SoVITS или IndexTTS 2.5.</b><br>
Движок читает иероглифы сам — связно, в контексте предложения — а чтение основного слова берётся из фуриганы карточки. Готовые ogg-файлы
кладутся прямо в поля Anki. <b>Бесплатно, без аккаунтов и телеметрии.</b> Интернет нужен только чтобы скачать.</p>

<p align="center">
  <a href="https://github.com/Daii1414/AnkiVoice/releases/latest">
    <img alt="Скачать AnkiVoice 1.8 для Windows" src="https://img.shields.io/badge/%E2%96%A8%20Скачать%20AnkiVoice%201.8%20%E2%80%94%20125%20МБ-4F46E5">
  </a>
</p>

<p align="center">
  <a href="#что-умеет">Возможности</a> •
  <a href="#быстрый-старт">Установка</a> •
  <a href="#интерфейс-четыре-вкладки">Интерфейс</a> •
  <a href="#как-читаются-иероглифы">Чтение иероглифов</a> •
  <a href="#разработка">Разработка</a> •
  <a href="#лицензия">Лицензия</a>
</p>"""

RU_NEW = """<p align="center"><b>Озвучка японских карточек Anki</b><br>
Голос GPT-SoVITS или IndexTTS 2.5 — целиком на вашем компьютере. Движок читает
иероглифы сам, связно, в контексте предложения, а чтение основного слова берётся
из фуриганы карточки. Готовые .ogg-файлы кладутся прямо в поля Anki.</p>

<p align="center">
  <a href="https://github.com/Daii1414/AnkiVoice/releases/latest">
    <img alt="Скачать AnkiVoice 1.8 для Windows" src="https://img.shields.io/badge/%E2%96%A8%20Скачать%20AnkiVoice%201.8%20%E2%80%94%20125%20МБ-4F46E5">
  </a>
  &nbsp;&nbsp;
  <a href="#что-нужно-до-установки">Что нужно перед установкой →</a>
</p>

<p align="center">
  <img alt="Windows 10/11" src="https://img.shields.io/badge/Windows%2010%2F11-0078D6?logo=windows&logoColor=white">
  <img alt="GPU NVIDIA от 6 ГБ" src="https://img.shields.io/badge/GPU%20NVIDIA%20%E2%89%A5%206%20%D0%93%D0%91-0078D6">
  <img alt="Бесплатно" src="https://img.shields.io/badge/%D0%B1%D0%B5%D1%81%D0%BF%D0%BB%D0%B0%D1%82%D0%BD%D0%BE-12A150">
  <img alt="Без облака и телеметрии" src="https://img.shields.io/badge/%D0%B1%D0%B5%D0%B7%20%D0%BE%D0%B1%D0%BB%D0%B0%D0%BA%D0%B0%20%D0%B8%20%D1%82%D0%B5%D0%BB%D0%B5%D0%BC%D0%B5%D1%82%D1%80%D0%B8%D0%B8-12A150">
  <img alt="AGPL-3.0" src="https://img.shields.io/badge/license-AGPL--3.0-4F46E5.svg">
</p>

<p align="center">
  <a href="#как-это-работает">Как это работает</a> •
  <a href="#быстрый-старт">Установка</a> •
  <a href="#интерфейс-четыре-вкладки">Интерфейс</a> •
  <a href="#как-читаются-иероглифы">Чтение иероглифов</a> •
  <a href="#если-что-то-не-работает">Если не работает</a> •
  <a href="#разработка">Разработка</a>
</p>"""

EN_OLD = """<p align="center"><b>Local Japanese audio for Anki decks, voiced by GPT-SoVITS or IndexTTS 2.5.</b><br>
The engine reads the kanji itself - connected, in the context of the sentence -
while the reading of the main term comes from the card's furigana. Finished
ogg files land straight in Anki fields. <b>Free, no accounts, no telemetry.</b>
The internet is only needed to download it.</p>

<p align="center">
  <a href="https://github.com/Daii1414/AnkiVoice/releases/latest">
    <img alt="Download AnkiVoice 1.8 for Windows" src="https://img.shields.io/badge/%E2%96%A8%20Download%20AnkiVoice%201.8%20%E2%80%94%20125%20MB-4F46E5">
  </a>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Install</a> •
  <a href="#interface-four-tabs">Interface</a> •
  <a href="#how-kanji-are-read">Reading</a> •
  <a href="#development">Development</a> •
  <a href="#license">License</a>
</p>"""

EN_NEW = """<p align="center"><b>Japanese audio for your Anki cards</b><br>
A GPT-SoVITS or IndexTTS 2.5 voice - entirely on your own computer. The engine
reads the kanji itself, connected, in the context of the sentence, while the
reading of the main term comes from the card's furigana. Finished .ogg files land
straight in the Anki fields.</p>

<p align="center">
  <a href="https://github.com/Daii1414/AnkiVoice/releases/latest">
    <img alt="Download AnkiVoice 1.8 for Windows" src="https://img.shields.io/badge/%E2%96%A8%20Download%20AnkiVoice%201.8%20%E2%80%94%20125%20MB-4F46E5">
  </a>
  &nbsp;&nbsp;
  <a href="#what-you-need-before-installing">What you need before installing →</a>
</p>

<p align="center">
  <img alt="Windows 10/11" src="https://img.shields.io/badge/Windows%2010%2F11-0078D6?logo=windows&logoColor=white">
  <img alt="NVIDIA GPU from 6 GB" src="https://img.shields.io/badge/NVIDIA%20GPU%20%E2%89%A5%206%20GB-0078D6">
  <img alt="Free" src="https://img.shields.io/badge/free-12A150">
  <img alt="No cloud, no telemetry" src="https://img.shields.io/badge/no%20cloud%2C%20no%20telemetry-12A150">
  <img alt="AGPL-3.0" src="https://img.shields.io/badge/license-AGPL--3.0-4F46E5.svg">
</p>

<p align="center">
  <a href="#how-it-works">How it works</a> •
  <a href="#quick-start">Install</a> •
  <a href="#interface-four-tabs">Interface</a> •
  <a href="#how-kanji-are-read">Reading</a> •
  <a href="#troubleshooting">If it does not work</a> •
  <a href="#development">Development</a>
</p>"""

for name, old, new in (("README.md", RU_OLD, RU_NEW), ("README.en.md", EN_OLD, EN_NEW)):
    p = os.path.join(ROOT, name)
    s = io.open(p, encoding="utf-8").read()
    if old not in s:
        print("  ! шапка не найдена в", name)
        continue
    s = s.replace(old, new, 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("  ok шапка:", name)
print("готово")
