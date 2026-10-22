# -*- coding: utf-8 -*-
"""Английский README: таблица «что проверяет приложение»."""
import io
import os

ROOT = os.environ["AV_ROOT"]
p = os.path.join(ROOT, "README.en.md")
s = io.open(p, encoding="utf-8").read()

OLD = """**We check sentences, not words.** An isolated word is transcribed
unreliably: the zones "real failure" and "false alarm" overlap completely. The
word is guarded by the acoustic QC (silence, tempo, length)."""

NEW = """### What the app checks on its own

| What it checks | How | Result |
|---|---|---|
| Silence, clipping, duplicates | QC v2 over several signals | rejects are re-generated automatically |
| Breaks inside the speech | a pause longer than 4 s inside a phrase | the piece is re-synthesized |
| Level and speed | too quiet or too fast | re-synthesis at another speed |
| Pronunciation (optional) | ASR listens to its own audio and compares it with the text | a hint, the decision is yours |

**We check sentences, not words.** An isolated word is transcribed
unreliably: the zones "real failure" and "false alarm" overlap completely. The
word is guarded by the acoustic QC (silence, tempo, length)."""

if OLD not in s:
    print("  ! не найдено")
else:
    s = s.replace(OLD, NEW, 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("  ok README.en.md: таблица «что проверяет»")
