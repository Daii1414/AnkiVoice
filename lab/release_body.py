# -*- coding: utf-8 -*-
"""Тело релиза из CHANGELOG.md — для шага публикации в CI.

CI передаёт имя тега (v1.9.1), скрипт вырезает соответствующую секцию
CHANGELOG (## [1.9.1] ...) до следующей секции и печатает её в stdout —
action-gh-release забирает её через body_path. Строку «Установщик: …»
вырезаем: ссылку на релиз GitHub допишет сам. Нет секции — печатаем
короткий запасной текст, публикация не ломается.

Запуск:  python lab/release_body.py v1.9.1 > release_body.md
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def extract(changelog_text, version):
    """Секция версии без заголовка; None, если секции нет."""
    m = re.search(r"^## \[%s\][^\n]*\n" % re.escape(version),
                  changelog_text, re.MULTILINE)
    if not m:
        return None
    nxt = re.search(r"^## \[", changelog_text[m.end():], re.MULTILINE)
    body = changelog_text[m.end():m.end() + nxt.start()] if nxt \
        else changelog_text[m.end():]
    lines = [ln for ln in body.splitlines()
             if not ln.startswith("Установщик:")]
    return "\n".join(lines).strip()


def main():
    tag = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    version = tag[1:] if tag.startswith("v") else tag
    changelog = io.open(os.path.join(ROOT, "CHANGELOG.md"),
                        encoding="utf-8").read()
    body = extract(changelog, version) if version else None
    if not body:
        print("Смотри CHANGELOG.md — для %s отдельной секции нет." %
              (tag or "этой версии"))
        return 0
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
