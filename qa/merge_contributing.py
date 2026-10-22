# -*- coding: utf-8 -*-
"""Перенести разделы «Разработка» и «Структура репозитория» в CONTRIBUTING.

Исходники берём из последнего коммита — в рабочем дереве их уже нет.
"""
import io
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.environ["AV_ROOT"]


def read(p):
    return io.open(os.path.join(ROOT, p), encoding="utf-8").read()


def write(p, s):
    io.open(os.path.join(ROOT, p), "w", encoding="utf-8", newline="\n").write(s)
    print("  записан", p)


def git_show(path):
    out = subprocess.run(["git", "-C", ROOT, "show", "HEAD:" + path],
                         capture_output=True)
    return out.stdout.decode("utf-8")


def between(text, start_marker, end_marker):
    i = text.index(start_marker)
    j = text.index(end_marker, i)
    return text[i:j].strip()


def section_body(doc, heading_prefix):
    """Тело раздела по префиксу заголовка (до следующего '## ')."""
    i = doc.index(heading_prefix)
    j = doc.index("\n## ", i + len(heading_prefix))
    return doc[i + len(heading_prefix):j].strip()


def replace_section(doc, heading_prefix, new_body):
    i = doc.index(heading_prefix)
    j = doc.index("\n## ", i + len(heading_prefix))
    return doc[:i + len(heading_prefix)] + "\n\n" + new_body.strip() + "\n\n" + doc[j:].lstrip("\n")


def insert_after(doc, heading_prefix, block):
    i = doc.index(heading_prefix)
    j = doc.index("\n## ", i + len(heading_prefix))
    return doc[:j] + "\n\n" + block.strip() + "\n" + doc[j:]


def build(ru_old, en_old, ru_head, en_head, quick, tests, buildblock, layout,
          layout_head):
    """Собрать новый CONTRIBUTING из существующего и перенесённых кусков."""
    s = read(ru_head)
    s = replace_section(s, "## Быстрый старт", quick)
    s = replace_section(s, "## Проверки перед pull request", tests)
    s = replace_section(s, "## Сборка", buildblock)
    s = insert_after(s, "## Сборка", "## Структура репозитория\n\n" + layout)
    write(ru_head, s)

    s = read(en_head)
    s = replace_section(s, "## Quick start", quick_en)
    s = replace_section(s, "## Checks before opening a pull request", tests_en)
    s = replace_section(s, "## Building", build_en)
    s = insert_after(s, "## Building", "## Repository layout\n\n" + layout_en)
    write(en_head, s)


# ---------------------------------------------------------------- RU --------
ru_old = git_show("README.md")
en_old = git_show("README.en.md")

ru_quick = between(ru_old, "```bash\ngit clone", "**exe** (нужен Python")
ru_build = between(ru_old, "**exe** (нужен Python", "**тесты** (Python")
ru_tests = between(ru_old, "**тесты** (Python", "\n## ")
ru_layout = between(ru_old, "| Файл | Что это |", "\n## ")

en_quick = between(en_old, "```bash\ngit clone", "**exe** (needs the Python")
en_build = between(en_old, "**exe** (needs the Python", "**tests** (Python")
en_tests = between(en_old, "**tests** (Python", "\n## ")
en_layout = between(en_old, "| File | What it is |", "\n## ")

# «Быстрый старт» в CONTRIBUTING уже содержит clone — оставляем клон из README
ru_quick = ru_quick.replace("git clone", "git clone", 1)

s = read("CONTRIBUTING.md")
s = replace_section(s, "## Быстрый старт", ru_quick)
s = replace_section(s, "## Проверки перед pull request", ru_tests)
s = replace_section(s, "## Сборка", ru_build)
s = insert_after(s, "## Сборка", "## Структура репозитория\n\n" + ru_layout)
write("CONTRIBUTING.md", s)

e = read("CONTRIBUTING.en.md")
e = replace_section(e, "## Quick start", en_quick)
e = replace_section(e, "## Checks before opening a pull request", en_tests)
e = replace_section(e, "## Building", en_build)
e = insert_after(e, "## Building", "## Repository layout\n\n" + en_layout)
write("CONTRIBUTING.en.md", e)

print("готово: CONTRIBUTING обновлён")
