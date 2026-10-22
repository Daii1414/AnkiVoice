# -*- coding: utf-8 -*-
"""Английский README: схема картинкой + убрать историю изменений."""
import io
import os
import re

ROOT = os.environ["AV_ROOT"]
p = os.path.join(ROOT, "README.en.md")
s = io.open(p, encoding="utf-8").read()

old = """```
Anki card
   │
   ├─► reading mode (a per-deck setting)
   │      ├─► "kanji only": the engine reads the kanji itself
   │      └─► "kanji + reading from furigana": the term keeps the card's reading
   │
   ├─► engine: GPT-SoVITS (127.0.0.1:9880) or IndexTTS 2.5 (127.0.0.1:9881) ──► ogg
   │
   ├─► QC v2: quality signals ──► re-synthesis of rejects
   │
   └─► pronunciation check (advice): ASR compares audio with text
```"""
new = "![How it works](doc/how-it-works.en.svg)"
if old in s:
    s = s.replace(old, new, 1)
    print("  схема заменена")
else:
    print("  ! схема не найдена")

pattern = re.compile(r"\n## What's new in 1\.\d\n.*?(?=\n## )", re.S)
n = len(pattern.findall(s))
s = pattern.sub("", s)
print("  удалено разделов истории:", n)

s = re.sub(r"^- \[What's new in 1\.\d\]\(#[^\)]+\)\n", "", s, flags=re.M)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("  готово")
