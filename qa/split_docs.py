# -*- coding: utf-8 -*-
"""Разнести длинный хвост README по документам.

Что уходит из README.md / README.en.md:
  «Как текст превращается в хирагану» -> doc/reading.md
  «Поля карточек»                       -> doc/fields.md
  «Консоль»                             -> doc/cli.md
  «Второй движок: IndexTTS 2.5» (хвост) -> doc/engines.md
  «Разработка», «Структура репозитория» -> CONTRIBUTING.md

В README остаётся раздел «Документация» со ссылками на всё это.
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.environ["AV_ROOT"]


def read(p):
    return io.open(os.path.join(ROOT, p), encoding="utf-8").read()


def write(p, s):
    full = os.path.join(ROOT, p)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    io.open(full, "w", encoding="utf-8", newline="\n").write(s)
    print("  записан", p)


def cut(doc, heading):
    """Вырезать раздел целиком. Возвращает (вырезанное, остаток)."""
    marker = heading + "\n"
    i = doc.index(marker)
    j = doc.find("\n## ", i + len(marker))
    if j < 0:
        j = len(doc)
    block = doc[i:j].rstrip() + "\n"
    rest = (doc[:i].rstrip() + "\n\n" + doc[j:].lstrip("\n"))
    return block, rest


def body(block):
    """Текст раздела без заголовка."""
    lines = block.split("\n")
    return "\n".join(lines[1:]).strip() + "\n"


def head(block):
    return block.split("\n", 1)[0].strip()


def as_title(block):
    """«## Заголовок» -> «# Заголовок»."""
    return "#" + block.split("\n", 1)[0]


# --------------------------------------------------------------------------
# RU
# --------------------------------------------------------------------------
ru = read("README.md")

blk_reading, ru = cut(ru, "## Как текст превращается в хирагану")
blk_fields, ru = cut(ru, "## Поля карточек")
blk_cli, ru = cut(ru, "## Консоль")
blk_dev, ru = cut(ru, "## Разработка")
blk_layout, ru = cut(ru, "## Структура репозитория")

# хвост раздела про второй движок: от «Поставить IndexTTS 2.5:»
mark = "Поставить IndexTTS 2.5:"
i = ru.index(mark)
j = ru.index("\n## ", i)
eng_tail = ru[i:j].rstrip() + "\n"
ru = ru[:i].rstrip() + """

Подробности — установка, мост и чего в этом режиме нет — в
[doc/engines.md](doc/engines.md).

""" + ru[j:].lstrip("\n")

# раздел «Документация» — вместо трёх ушедших разделов
doc_section = """## Документация

| Документ | О чём |
|---|---|
| [doc/reading.md](doc/reading.md) | как текст превращается в хирагану: конвейер чтения, латиница, цифры, g2p |
| [doc/fields.md](doc/fields.md) | поля карточек: откуда брать текст и куда писать звук |
| [doc/cli.md](doc/cli.md) | консоль: все команды `pipeline.bat` и `AnkiVoice.exe` |
| [doc/engines.md](doc/engines.md) | второй движок IndexTTS 2.5: установка, мост, ограничения |
| [CONTRIBUTING.md](CONTRIBUTING.md) | разработка: сборка, проверки, структура репозитория |

"""
ru = ru.replace("## Обновления", doc_section + "## Обновления", 1)

# оглавление
for line in ("- [Как текст превращается в хирагану](#как-текст-превращается-в-хирагану)\n",
             "- [Поля карточек](#поля-карточек)\n",
             "- [Консоль](#консоль)\n",
             "- [Разработка](#разработка)\n",
             "- [Структура репозитория](#структура-репозитория)\n"):
    if line not in ru:
        print("  ! нет пункта оглавления:", line.strip())
    ru = ru.replace(line, "", 1)
ru = ru.replace("- [Обновления](#обновления)",
                "- [Документация](#документация)\n- [Обновления](#обновления)", 1)

write("README.md", ru)

# --- документы ---
write("doc/reading.md", as_title(blk_reading) + "\n\n" + body(blk_reading) +
      "\n---\n\n← [На главную страницу проекта](../README.md) · "
      "[English](reading.en.md)\n")
write("doc/fields.md", as_title(blk_fields) + "\n\n" + body(blk_fields) +
      "\n---\n\n← [На главную страницу проекта](../README.md) · "
      "[English](fields.en.md)\n")
write("doc/cli.md", as_title(blk_cli) + "\n\n" + body(blk_cli) +
      "\n---\n\n← [На главную страницу проекта](../README.md) · "
      "[English](cli.en.md)\n")
write("doc/engines.md", "# IndexTTS 2.5: установка, мост и ограничения\n\n"
      "Раздел README описывает, чем движок отличается от GPT-SoVITS. Здесь — "
      "как его поставить и как он подключён.\n\n" + eng_tail +
      "\n---\n\n← [На главную страницу проекта](../README.md) · "
      "[English](engines.en.md)\n")

# --------------------------------------------------------------------------
# EN
# --------------------------------------------------------------------------
en = read("README.en.md")

e_reading, en = cut(en, "## How text becomes hiragana")
e_fields, en = cut(en, "## Card fields")
e_cli, en = cut(en, "## Console")
e_dev, en = cut(en, "## Development")
e_layout, en = cut(en, "## Repository layout")

mark = "To install IndexTTS 2.5:"
if mark not in en:
    # английская формулировка может отличаться — ищем по установке
    import re
    m = re.search(r"^To (?:install|set up) IndexTTS.*$", en, re.M)
    mark = m.group(0) if m else None
if mark:
    i = en.index(mark)
    j = en.index("\n## ", i)
    e_eng_tail = en[i:j].rstrip() + "\n"
    en = en[:i].rstrip() + """

The details - installation, the bridge and what is missing in this mode - are
in [doc/engines.en.md](doc/engines.en.md).

""" + en[j:].lstrip("\n")
else:
    print("  ! не нашёл «To install IndexTTS 2.5» в README.en.md")
    e_eng_tail = ""

doc_section_en = """## Documentation

| Document | What it covers |
|---|---|
| [doc/reading.en.md](doc/reading.en.md) | how text becomes hiragana: the reading pipeline, latin, digits, g2p |
| [doc/fields.en.md](doc/fields.en.md) | card fields: where the text comes from and where the sound goes |
| [doc/cli.en.md](doc/cli.en.md) | the console: every `pipeline.bat` and `AnkiVoice.exe` command |
| [doc/engines.en.md](doc/engines.en.md) | the second engine, IndexTTS 2.5: installation, bridge, limits |
| [CONTRIBUTING.en.md](CONTRIBUTING.en.md) | development: build, checks, repository layout |

"""
en = en.replace("## Updates", doc_section_en + "## Updates", 1)

for line in ("- [How text becomes hiragana](#how-text-becomes-hiragana)\n",
             "- [Card fields](#card-fields)\n",
             "- [Console](#console)\n",
             "- [Development](#development)\n",
             "- [Repository layout](#repository-layout)\n"):
    if line not in en:
        print("  ! нет пункта оглавления (EN):", line.strip())
    en = en.replace(line, "", 1)
en = en.replace("- [Updates](#updates)",
                "- [Documentation](#documentation)\n- [Updates](#updates)", 1)

write("README.en.md", en)

write("doc/reading.en.md", as_title(e_reading) + "\n\n" + body(e_reading) +
      "\n---\n\n← [Back to the project page](../README.en.md) · "
      "[Русский](reading.md)\n")
write("doc/fields.en.md", as_title(e_fields) + "\n\n" + body(e_fields) +
      "\n---\n\n← [Back to the project page](../README.en.md) · "
      "[Русский](fields.md)\n")
write("doc/cli.en.md", as_title(e_cli) + "\n\n" + body(e_cli) +
      "\n---\n\n← [Back to the project page](../README.en.md) · "
      "[Русский](cli.md)\n")
write("doc/engines.en.md", "# IndexTTS 2.5: installation, bridge and limits\n\n"
      "The README section explains how this engine differs from GPT-SoVITS. "
      "This file covers how to install it and how it is wired in.\n\n" + e_eng_tail +
      "\n---\n\n← [Back to the project page](../README.en.md) · "
      "[Русский](engines.md)\n")

print("готово: разделы вырезаны, документы созданы")
