# -*- coding: utf-8 -*-
"""Раздел «кому это нужно» и картинка «до и после» — выше оглавления:
читатель должен понять, что это и для кого, раньше длинного списка."""
import io
import os

ROOT = os.environ["AV_ROOT"]


def move(path, sec_head, toc_head, img_line, toc_item):
    p = os.path.join(ROOT, path)
    s = io.open(p, encoding="utf-8").read()

    i = s.find(sec_head)
    if i < 0:
        print("  ! раздел не найден:", path)
        return
    j = s.find("\n## ", i + len(sec_head))
    if j < 0:
        j = len(s)
    block = s[i:j].strip() + "\n\n"

    # убрать блок из старого места
    s = s[:i] + s[j:].lstrip("\n")
    # убрать картинку из старого места
    if img_line in s:
        s = s.replace(img_line + "\n\n", "", 1)
    # убрать пункт из оглавления
    if toc_item in s:
        s = s.replace(toc_item, "", 1)

    k = s.find(toc_head)
    if k < 0:
        print("  ! оглавление не найдено:", path)
        return
    s = s[:k] + block + img_line + "\n\n" + s[k:]
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("  ok", path, ": раздел поднят над оглавлением")


move("README.md",
     "## Что это и для кого",
     "## Оглавление",
     "![Одна карточка до и после: AnkiVoice не трогает текст карточки и добавляет звук в два поля](doc/shots/before-after.png)",
     "- [Что это и для кого](#что-это-и-для-кого)\n")

move("README.en.md",
     "## What this is and who it is for",
     "## Table of contents",
     "![One card before and after: AnkiVoice does not change the card text and adds sound to two fields](doc/shots/before-after.en.png)",
     "- [What this is and who it is for](#what-this-is-and-who-it-is-for)\n")
print("готово")
