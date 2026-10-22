# -*- coding: utf-8 -*-
"""Правки по разбору страницы агентом:

1. японские примеры, побитые кириллицей (13 мест);
2. упоминания версий и хэш от v1.6 в README;
3. мёртвые якоря (#быстрый-старт, #quick-start);
4. «Что это и для кого» — в начало, сразу после оглавления;
5. пути к модулям в разделе про разработку;
6. ссылка на демо-звук (doc/gptsovits/gpt-sovits-demo.mp4) — он лежал в git
   молча.
"""
import io
import os

ROOT = os.environ["AV_ROOT"]


def patch(path, pairs, must=True):
    p = os.path.join(ROOT, path)
    s = io.open(p, encoding="utf-8").read()
    for old, new in pairs:
        if old not in s:
            print("  ! не найдено в %s: %s" % (path, old.strip().split("\n")[0][:60]))
            continue
        s = s.replace(old, new)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("  ok", path)


# 1. японские примеры с кириллицей ------------------------------------------
MIXED = {
    "README.md": [
        ("麻院[あさすса]", "麻院[あさすさ]"),
        ("点群データ[てんぐんでーта]", "点群データ[てんぐんでーた]"),
    ],
    "CHANGELOG.md": [
        ("点群データ[てんぐんでーта]", "点群データ[てんぐんでーた]"),
        ("でーたてんぐんでーта", "でーたてんぐんでーた"),
    ],
    "PROJECT.md": [
        ("アイイーシーきаку", "アイイーシーきかく"),
        ("げн", "げん"),
    ],
    "doc/reports/REPORT-g2p-benchmark.md": [
        ("ロッпиャк", "ロッピャク"),
        ("ロクхиゃк", "ロクチャク"),
        ("ドно", "ドノ"),
        ("は → ワ.", "は → ワ."),
        ("ビェニャк殿", "ビェニャク殿"),
        ("コンニЧа", "コンニチャ"),
        ("コンbanハ", "コンバンハ"),
        ("トウ = トо", "トウ = トウ"),
        ("ау не схлопывается", "あう не схлопывается"),
        ("相欠ки", "相欠ギ"),
        ("相欠ки継ぎ", "相欠ギ継ぎ"),
        ("相决り", "相決リ"),
        ("相决り継ги", "相決リ継ギ"),
        ("相决り矧ги", "相決リ矧ギ"),
        ("板矧ги", "板矧ギ"),
        ("ハハジハナヘツки", "ハハジハナヘツキ"),
        ("シュкаヘГэцу", "シュカヘツユ"),
        ("ベни", "ベニ"),
        ("クレナи", "クレナイ"),
        ("デャデュнは", "デャデュンは"),
        ("ズボн", "ズボン"),
    ],
}
for path, pairs in MIXED.items():
    patch(path, pairs)

# 2. версии и хэш в README --------------------------------------------------
patch("README.md", [
    ("1. Скачай **`AnkiVoice-Setup-1.8.exe`** со страницы\n"
     "   [Releases](https://github.com/Daii1414/AnkiVoice/releases/latest) — один файл,\n"
     "   внутри всё. Размер **125 МБ**, SHA256:\n"
     "   `385481551c6404ec8927a37d6c234630c87ee71660aa5c689eab9654da0dbc28`",
     "1. Скачай установщик **`AnkiVoice-Setup-x.y.exe`** со страницы\n"
     "   [Releases](https://github.com/Daii1414/AnkiVoice/releases/latest) — один файл,\n"
     "   внутри всё, размер **125 МБ**. Контрольная сумма указана в заметках\n"
     "   к релизу; проверить её можно командой\n"
     "   `certutil -hashfile AnkiVoice-Setup-x.y.exe SHA256`."),
    ("→ получится `dist\\AnkiVoice-Setup-1.8.exe`.",
     "→ получится `dist\\AnkiVoice-Setup-x.y.exe`."),
])
patch("README.en.md", [
    ("1. Download **`AnkiVoice-Setup-1.8.exe`** from the\n"
     "   [Releases](https://github.com/Daii1414/AnkiVoice/releases/latest) page — one\n"
     "   file with everything inside. Size **125 MB**, SHA256:\n"
     "   `385481551c6404ec8927a37d6c234630c87ee71660aa5c689eab9654da0dbc28`",
     "1. Download the installer **`AnkiVoice-Setup-x.y.exe`** from the\n"
     "   [Releases](https://github.com/Daii1414/AnkiVoice/releases/latest) page — one\n"
     "   file with everything inside, **125 MB**. The checksum is in the release\n"
     "   notes; check it with\n"
     "   `certutil -hashfile AnkiVoice-Setup-x.y.exe SHA256`."),
    ("→ produces `dist\\AnkiVoice-Setup-1.8.exe`.",
     "→ produces `dist\\AnkiVoice-Setup-x.y.exe`."),
])

# 3. мёртвые якоря ------------------------------------------------------------
patch("README.md", [
    ('<a href="#быстрый-старт">Установка</a>',
     '<a href="#первый-звук-за-60-секунд">Установка</a>'),
    ("[Первый звук за 60 секунд](#быстрый-старт)",
     "[Первый звук за 60 секунд](#первый-звук-за-60-секунд)"),
])
patch("README.en.md", [
    ('<a href="#quick-start">Install</a>',
     '<a href="#your-first-sound-in-60-seconds">Install</a>'),
    ("[Your first sound in 60 seconds](#quick-start)",
     "[Your first sound in 60 seconds](#your-first-sound-in-60-seconds)"),
])

# 4. раздел «кому это нужно» — в начало --------------------------------------
def move_section(path, marker, before):
    p = os.path.join(ROOT, path)
    s = io.open(p, encoding="utf-8").read()
    i = s.find(marker)
    if i < 0:
        print("  ! раздел не найден:", path, marker)
        return
    j = s.find("\n## ", i + len(marker))
    if j < 0:
        return
    block = s[i:j].rstrip() + "\n\n"
    s = s[:i] + s[j:].lstrip("\n")
    k = s.find(before)
    if k < 0:
        print("  ! якорь вставки не найден:", path, before)
        io.open(p, "w", encoding="utf-8", newline="\n").write(s)
        return
    s = s[:k] + block + s[k:]
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("  ok", path, ": раздел перенесён выше")


move_section("README.md", "## Что это и для кого", "## Что умеет")
move_section("README.en.md", "## What this is and who it is for", "## Features")

# 5. пути к модулям в разделе про разработку --------------------------------
patch("README.md", [
    ("python kana_stress.py", "python app/kana_stress.py"),
    ("после правок `anki_gui.py`, `anki_web.py` или\n`anki_web_page.py`",
     "после правок `app/anki_gui.py`, `app/anki_web.py` или\n`app/anki_web_page.py`"),
])
patch("README.en.md", [
    ("python kana_stress.py", "python app/kana_stress.py"),
    ("after editing `anki_gui.py`, `anki_web.py` or\n`anki_web_page.py`",
     "after editing `app/anki_gui.py`, `app/anki_web.py` or\n`app/anki_web_page.py`"),
])

# 6. демо-звук: он лежал в git и не был упомянут --------------------------
patch("README.md", [
    ("## Как это работает",
     "> **Послушать, как это звучит:** [демо-ролик](doc/gptsovits/gpt-sovits-demo.mp4) —\n"
     "> озвучка японских предложений моделью (озвучка идёт офлайн на вашей машине).\n\n"
     "## Как это работает"),
])
patch("README.en.md", [
    ("## How it works",
     "> **Hear what it sounds like:** [demo clip](doc/gptsovits/gpt-sovits-demo.mp4) —\n"
     "> Japanese sentences voiced by a model (the synthesis runs offline on your machine).\n\n"
     "## How it works"),
])
print("готово")
