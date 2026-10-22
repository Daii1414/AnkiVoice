# -*- coding: utf-8 -*-
"""Схема «Как это работает» — картинкой вместо ASCII; история изменений из README — прочь."""
import io
import os
import re

ROOT = os.environ["AV_ROOT"]

# --- 1. ASCII-схема -> картинка -------------------------------------------
ru_old = """```
карточка Anki
   │
   ├─► режим чтения (настройка колоды)
   │      ├─► авто: есть фуригана — термин ровно по ней, нет — кандзи
   │      └─► «только кандзи»: движок читает иероглифы сам
   │
   ├─► движок: GPT-SoVITS (127.0.0.1:9880) или IndexTTS 2.5 (127.0.0.1:9881) ──► ogg
   │
   ├─► QC v2: сигналы качества ──► перегенерация брака
   │
   └─► проверка произношения (совет): ASR сверяет звук с текстом
```"""
ru_new = """![Как это работает](doc/how-it-works.svg)"""

en_old = """```
Anki card
   │
   ├─► reading mode (deck setting)
   │      ├─► auto: furigana present — term read exactly by it, absent — kanji
   │      └─► "kanji only": the engine reads the kanji itself
   │
   ├─► engine: GPT-SoVITS (127.0.0.1:9880) or IndexTTS 2.5 (127.0.0.1:9881) ──► ogg
   │
   ├─► QC v2: quality signals ──► re-record the rejects
   │
   └─► pronunciation check (advice): ASR compares the audio with the text
```"""
en_new = """![How it works](doc/how-it-works.en.svg)"""

for path, old, new in (("README.md", ru_old, ru_new),
                       ("README.en.md", en_old, en_new)):
    p = os.path.join(ROOT, path)
    s = io.open(p, encoding="utf-8").read()
    if old in s:
        s = s.replace(old, new, 1)
        print("  схема заменена в", path)
    else:
        print("  ! ASCII-схема не найдена в", path)

    # --- 2. убрать историю изменений -------------------------------------
    # разделы «Что нового в 1.x» / «What's new in 1.x» — подряд идущие
    pattern = re.compile(r"\n## (?:Что нового|What's new) в 1\.\d\n.*?(?=\n## )",
                         re.S)
    n = len(pattern.findall(s))
    s = pattern.sub("", s)
    print("  удалено разделов истории:", path, "->", n)

    # --- 3. убрать их из оглавления --------------------------------------
    s = re.sub(r"^- \[(?:Что нового|What's new) в 1\.\d\]\(#[^\)]+\)\n", "", s,
               flags=re.M)
    # одинаковое число разделов в обоих README
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)

print("готово")
