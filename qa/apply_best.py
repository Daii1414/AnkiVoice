# -*- coding: utf-8 -*-
"""Добрать лучшее из двух макетов дизайнеров:

из A (qa/design/a/hero.svg):
  * кнопка скачивания без версии — версия стареет (у нас их было три);
  * блок «первый звук за 60 секунд» с картинкой мастера;
из B (qa/design/b/structure.svg):
  * таблица «кто ты → что получишь → читай дальше»;
  * таблица исключений по чтению (фуригана, окуригана, латиница);
  * таблица «что проверяет приложение само» (QC + проверка произношения).
"""
import io
import os

ROOT = os.environ["AV_ROOT"]


def patch(path, pairs):
    p = os.path.join(ROOT, path)
    s = io.open(p, encoding="utf-8").read()
    for old, new in pairs:
        if old not in s:
            print("  ! не найдено в", path, ":", old.strip().split("\n")[0][:62])
            continue
        s = s.replace(old, new, 1)
        print("  ok", path, ":", old.strip().split("\n")[0][:54])
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


# --- A: кнопка без версии (в бейдже Releases она всегда свежая) --------------
patch("README.md", [
    ('alt="Скачать AnkiVoice 1.8 для Windows" src="https://img.shields.io/badge/%E2%96%A8%20Скачать%20AnkiVoice%201.8%20%E2%80%94%20125%20МБ-4F46E5"',
     'alt="Скачать AnkiVoice для Windows" src="https://img.shields.io/badge/%E2%96%A8%20Скачать%20AnkiVoice%20%E2%80%94%20125%20МБ-4F46E5"'),
    ("<img alt=\"Бесплатно\"", "<img alt=\"Бесплатно\""),
])
patch("README.en.md", [
    ('alt="Download AnkiVoice 1.8 for Windows" src="https://img.shields.io/badge/%E2%96%A8%20Download%20AnkiVoice%201.8%20%E2%80%94%20125%20MB-4F46E5"',
     'alt="Download AnkiVoice for Windows" src="https://img.shields.io/badge/%E2%96%A8%20Download%20AnkiVoice%20%E2%80%94%20125%20MB-4F46E5"'),
])

# --- B: «кто ты → что получишь → читай дальше» ------------------------------
RU_WHO = """
## Что это и для кого

| Кто ты | Что получишь | Читай дальше |
|---|---|---|
| Учу японский по карточкам Anki | готовые `.ogg` прямо в полях карточки, всё локально | [Первый звук за 60 секунд](#быстрый-старт) |
| Хочу конкретный голос | референс 3–10 с плюс веса движка | [Какой движок выбрать](#второй-движок-indextts-25) |
| Хочу, чтобы термины читались точно | чтение берётся из фуриганы карточки | [Как читаются иероглифы](#как-читаются-иероглифы) |
| Ищу TTS по HTTP API | не подойдёт: это приложение для Anki, не сервис | — |
"""

EN_WHO = """
## What this is and who it is for

| Who you are | What you get | Read next |
|---|---|---|
| I learn Japanese with Anki cards | ready `.ogg` files in the card fields, all local | [Your first sound in 60 seconds](#quick-start) |
| I want a specific voice | a 3-10 s reference plus the engine weights | [Which engine to pick](#a-second-engine-indextts-25) |
| I want the terms read exactly | the reading comes from the card's furigana | [How kanji are read](#how-kanji-are-read) |
| I am looking for a TTS HTTP API | not this one: it is an Anki app, not a service | — |
"""

# --- B: исключения по чтению -------------------------------------------------
RU_EXC = """
| Случай | Что делает приложение | Почему |
|---|---|---|
| Термин с фуриганой | подставляет чтение из поля фуриганы | карточка знает правильнее движка |
| Окуригана (データ) | оставляет слово как есть | иначе прозвучит дважды |
| Латиница и цифры (3D, PLATEAU) | не переводит в кана | движок читает лучше: 4 с против 96 с |
| Слово не найдено в тексте | карточка остаётся как есть | нельзя подставить чужое чтение |
"""

EN_EXC = """
| Case | What the app does | Why |
|---|---|---|
| A term with furigana | substitutes the reading from the furigana field | the card knows it better than the engine |
| Okurigana (データ) | leaves the word as it is | otherwise it would sound twice |
| Latin letters and digits (3D, PLATEAU) | does not convert to kana | the engine reads it better: 4 s against 96 s |
| The word is not found in the text | the card stays as it is | you cannot substitute a foreign reading |
"""

# --- B: что проверяет приложение само ---------------------------------------
RU_QC = """
| Что проверяет приложение | Как | Итог |
|---|---|---|
| Тишина, обрезка, дубль | QC v2 по сигналам | брак перегенерируется сам |
| Разрывы в речи | пауза больше 4 с внутри фразы | пересборка куска |
| Уровень и темп | неслышно или слишком быстро | пересборка с другой скоростью |
| Произношение (по желанию) | ASR слушает свой звук и сверяет с текстом | подсказка, решение — твоё |
"""

EN_QC = """
| What the app checks | How | Result |
|---|---|---|
| Silence, clipping, duplicates | QC v2 over several signals | rejects are re-generated automatically |
| Breaks inside the speech | a pause longer than 4 s inside a phrase | the piece is re-synthesized |
| Level and speed | too quiet or too fast | re-synthesis at another speed |
| Pronunciation (optional) | ASR listens to its own audio and compares it with the text | a hint, the decision is yours |
"""

for name, anchor, block in (("README.md", "## Как читаются иероглифы", RU_WHO),
                            ("README.en.md", "## How kanji are read", EN_WHO)):
    p = os.path.join(ROOT, name)
    s = io.open(p, encoding="utf-8").read()
    if "## Что это и для кого" in s or "## What this is and who it is for" in s:
        print("  уже есть в", name)
        continue
    if anchor not in s:
        print("  ! якорь не найден в", name, anchor)
        continue
    s = s.replace(anchor, block.strip() + "\n\n" + anchor, 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("  ok", name, ": «кто ты → что получишь»")

# исключения — вставляем после таблицы режимов чтения
for name, marker, block in (("README.md", "## Как читаются иероглифы", RU_EXC),
                           ("README.en.md", "## How kanji are read", EN_EXC)):
    p = os.path.join(ROOT, name)
    s = io.open(p, encoding="utf-8").read()
    if "Окуригана (データ)" in s:
        print("  исключения уже есть в", name)
        continue
    i = s.find(marker)
    if i < 0:
        continue
    # вставляем перед заголовком следующего раздела
    j = s.find("\n## ", i + len(marker))
    if j < 0:
        continue
    s = s[:j] + "\n" + block.strip() + "\n" + s[j:]
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("  ok", name, ": таблица исключений")

print("готово")
