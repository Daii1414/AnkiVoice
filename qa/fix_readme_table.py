# -*- coding: utf-8 -*-
"""Таблица структуры репозитория — под новую раскладку (app/, bundled/)."""
import io
import os

ROOT = os.environ["AV_ROOT"]

ru_pairs = [
    ("| `voice_pipeline.py` |", "| `app/voice_pipeline.py` |"),
    ("| `anki_gui.py` |", "| `app/anki_gui.py` |"),
    ("| `anki_web.py` |", "| `app/anki_web.py` |"),
    ("| `anki_web_page.py` |", "| `app/anki_web_page.py` |"),
    ("| `sudachi_g2p.py` |", "| `app/sudachi_g2p.py` |"),
    ("| `g2p_core.py` |", "| `app/g2p_core.py` |"),
    ("| `kana_stress.py` |", "| `app/kana_stress.py` |"),
    ("| `i18n_en.py` |", "| `app/i18n_en.py` |"),
    ("| `voices.json` |", "| `app/voices.json` |"),
    ("| `pyruntime.zip` |", "| `bundled/pyruntime.zip` |"),
    ("| `sudachidict.zip` |", "| `bundled/sudachidict.zip` |"),
]
en_pairs = [
    ("| `voice_pipeline.py` |", "| `app/voice_pipeline.py` |"),
    ("| `anki_gui.py` |", "| `app/anki_gui.py` |"),
    ("| `anki_web.py` |", "| `app/anki_web.py` |"),
    ("| `anki_web_page.py` |", "| `app/anki_web_page.py` |"),
    ("| `sudachi_g2p.py` |", "| `app/sudachi_g2p.py` |"),
    ("| `g2p_core.py` |", "| `app/g2p_core.py` |"),
    ("| `kana_stress.py` |", "| `app/kana_stress.py` |"),
    ("| `i18n_en.py` |", "| `app/i18n_en.py` |"),
    ("| `voices.json` |", "| `app/voices.json` |"),
    ("| `pyruntime.zip` |", "| `bundled/pyruntime.zip` |"),
    ("| `sudachidict.zip` |", "| `bundled/sudachidict.zip` |"),
]

for name, pairs in (("README.md", ru_pairs), ("README.en.md", en_pairs)):
    p = os.path.join(ROOT, name)
    s = io.open(p, encoding="utf-8").read()
    n = 0
    for a, b in pairs:
        if a in s:
            s = s.replace(a, b, 1)
            n += 1
        else:
            print("  ! нет в", name, ":", a)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("  ok", name, "— строк обновлено:", n)
