# -*- coding: utf-8 -*-
"""Обновить дизайн Fragile в AnkiVoice: app/fragile_assets.py.

Цвета (19 тем + базовые тёмная/светлая) и слой трёх типов интерфейса
(чёткий / обычный / стекло) — общие для экосистемы Fragile. Источник —
скилл fragile-design (он сам синхронизируется с Fragile Notes:
scripts/sync_from_notes.py). Здесь они вшиваются в Python-модуль, потому
что страница интерфейса — строка внутри приложения (в Windows-сборке она
запечатана в exe, читать CSS с диска нельзя).

    python lab/sync_fragile.py [папка скилла]

Руками app/fragile_assets.py не правят — только перегенерируют.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.expanduser("~/.claude/skills/fragile-design")
OUT = os.path.join(ROOT, "app", "fragile_assets.py")


def main():
    skill = sys.argv[1] if len(sys.argv) > 1 else SKILL
    with open(os.path.join(skill, "assets", "fragile-themes.css"), encoding="utf-8") as f:
        themes_css = f.read()
    with open(os.path.join(skill, "assets", "fragile-design.css"), encoding="utf-8") as f:
        design_css = f.read()
    with open(os.path.join(skill, "references", "themes.json"), encoding="utf-8") as f:
        data = json.load(f)
    # для галереи нужны только подписи, схема и цвета мини-превью
    keep = ("id", "name", "kanji", "desc", "scheme", "bg", "side", "accent",
            "text", "textAccent")
    themes = [{k: t[k] for k in keep if k in t} for t in data["themes"]]
    base = {s: {"bg": data["base"][s].get("--background-primary"),
                "side": data["base"][s].get("--background-secondary"),
                "text": data["base"][s].get("--text-normal")}
            for s in ("dark", "light") if s in data.get("base", {})}
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("# -*- coding: utf-8 -*-\n")
        f.write('"""Дизайн Fragile: токены цвета, слой типов интерфейса, список тем.\n\n')
        f.write("СГЕНЕРИРОВАНО lab/sync_fragile.py из скилла fragile-design — не править руками.\n")
        f.write('"""\n\n')
        f.write("THEMES_CSS = %r\n\n" % themes_css)
        f.write("DESIGN_CSS = %r\n\n" % design_css)
        f.write("THEMES = %s\n\n" % json.dumps(themes, ensure_ascii=False))
        f.write("BASE = %s\n" % json.dumps(base, ensure_ascii=False))
    print("%s: %d тем, %d + %d байт CSS" % (OUT, len(themes), len(themes_css), len(design_css)))


if __name__ == "__main__":
    main()
