# -*- coding: utf-8 -*-
"""Подъём версии одной командой: версия живёт в трёх местах.

    python lab/bump_version.py 1.9.3

Правит: APP_VERSION в app/anki_gui.py, MyAppVersion и OutputBaseFilename
в AnkiVoice.iss, добавляет заголовок секции в CHANGELOG.md (существующая
«Не выпущено» переименовывается; если её нет — создаётся пустая новая
секция, список изменений дописываешь руками). После скрипта — коммит,
тег vX.Y.Z, CI соберёт и опубликует релиз.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sub(path, old, new, label):
    s = io.open(path, encoding="utf-8").read()
    if old not in s:
        raise SystemExit("НЕ НАЙДЕНО в %s: %r (%s)" % (path, old, label))
    io.open(path, "w", encoding="utf-8", newline="").write(s.replace(old, new, 1))
    print("  %s: %s" % (path, label))


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"\d+\.\d+(\.\d+)?", sys.argv[1]):
        raise SystemExit("Использование: python lab/bump_version.py X.Y[.Z]")
    ver = sys.argv[1]

    sub(os.path.join(ROOT, "app", "anki_gui.py"),
        'APP_VERSION = "1.9.2"', 'APP_VERSION = "%s"' % ver, "APP_VERSION")
    sub(os.path.join(ROOT, "AnkiVoice.iss"),
        '#define MyAppVersion "1.9.2"', '#define MyAppVersion "%s"' % ver,
        "MyAppVersion")
    sub(os.path.join(ROOT, "AnkiVoice.iss"),
        "OutputBaseFilename=AnkiVoice-Setup-1.9.2",
        "OutputBaseFilename=AnkiVoice-Setup-%s" % ver, "OutputBaseFilename")

    p = os.path.join(ROOT, "CHANGELOG.md")
    s = io.open(p, encoding="utf-8").read()
    if "## [Не выпущено]" in s:
        s = s.replace("## [Не выпущено]",
                      "## [%s] — TODO-дата\n\nУстановщик: `AnkiVoice-Setup-%s.exe`"
                      % (ver, ver), 1)
        print("  CHANGELOG: «Не выпущено» -> %s (впишешь дату)" % ver)
    else:
        head = "# Changelog\n"
        assert head in s
        section = ("\n## [%s] — TODO-дата\n\nУстановщик: `AnkiVoice-Setup-%s.exe`\n\n"
                   "### Добавлено\n\n- ...\n" % (ver, ver))
        s = s.replace(head, head + section, 1)
        print("  CHANGELOG: создана пустая секция %s" % ver)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("Готово. Дальше: заполни CHANGELOG, закоммить, тег v%s — CI опубликует." % ver)


if __name__ == "__main__":
    main()
