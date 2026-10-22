# -*- coding: utf-8 -*-
"""Ещё две идеи из макетов: таблица «что проверяет приложение» и
«первый звук за 60 секунд» с картинкой мастера."""
import io
import os

ROOT = os.environ["AV_ROOT"]


def patch(path, pairs):
    p = os.path.join(ROOT, path)
    s = io.open(p, encoding="utf-8").read()
    for old, new in pairs:
        if old not in s:
            print("  ! не найдено в", path, ":", old.strip().split("\n")[0][:62])
            continue
        s = s.replace(old, new, 1)
        print("  ok", path, ":", old.strip().split("\n")[0][:54])
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


RU_QC_OLD = """**Проверяем по предложению, не по слову.** Изолированное слово
распознаётся ненадёжно: зоны «настоящий брак» и «ложное срабатывание»
пересекаются полностью. Слово ловит акустический QC (тишина, темп, длина)."""

RU_QC_NEW = """### Что приложение проверяет само

| Что проверяет | Как | Итог |
|---|---|---|
| Тишина, обрезка, дубль | QC v2 по нескольким сигналам | брак перегенерируется сам |
| Разрывы в речи | пауза больше 4 с внутри фразы | пересборка куска |
| Уровень и темп | неслышно или слишком быстро | пересборка с другой скоростью |
| Произношение (по желанию) | ASR слушает свой звук и сверяет с текстом | подсказка, решение — твоё |

**Проверяем по предложению, не по слову.** Изолированное слово
распознаётся ненадёжно: зоны «настоящий брак» и «ложное срабатывание»
пересекаются полностью. Слово ловит акустический QC (тишина, темп, длина)."""

EN_QC_OLD = """**We check the sentence, not the word.** An isolated word is recognised
unreliably: the "real reject" and "false alarm" zones overlap completely. The
word is caught by the acoustic QC (silence, speed, length)."""

EN_QC_NEW = """### What the app checks on its own

| What it checks | How | Result |
|---|---|---|
| Silence, clipping, duplicates | QC v2 over several signals | rejects are re-generated automatically |
| Breaks inside the speech | a pause longer than 4 s inside a phrase | the piece is re-synthesized |
| Level and speed | too quiet or too fast | re-synthesis at another speed |
| Pronunciation (optional) | ASR listens to its own audio and compares it with the text | a hint, the decision is yours |

**We check the sentence, not the word.** An isolated word is recognised
unreliably: the "real reject" and "false alarm" zones overlap completely. The
word is caught by the acoustic QC (silence, speed, length)."""

patch("README.md", [(RU_QC_OLD, RU_QC_NEW)])
patch("README.en.md", [(EN_QC_OLD, EN_QC_NEW)])

# --- «первый звук за 60 секунд»: картинка мастера в «Быстром старте» -------
for name, anchor, block in (
        ("README.md", "## Быстрый старт",
         "## Первый звук за 60 секунд\n\n"
         "![Мастер настройки: выбор движка, папка, AnkiConnect, тестовая фраза]"
         "(doc/shots/wizard-dark.png)\n"),
        ("README.en.md", "## Quick start",
         "## Your first sound in 60 seconds\n\n"
         "![The setup wizard: engine, folder, AnkiConnect, test phrase]"
         "(doc/shots/wizard-dark.png)\n")):
    p = os.path.join(ROOT, name)
    s = io.open(p, encoding="utf-8").read()
    if anchor not in s:
        print("  ! якорь не найден:", name, anchor)
        continue
    new_anchor = block.split("\n")[0]
    s = s.replace(anchor, new_anchor, 1)
    # картинку ставим после первого абзаца раздела
    i = s.find(new_anchor)
    j = s.find("\n\n", i)
    s = s[:j] + "\n\n" + block.split("\n", 2)[2].strip() + s[j:]
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("  ok", name, ": первый звук за 60 секунд + картинка")
print("готово")
