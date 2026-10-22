# -*- coding: utf-8 -*-
"""Перестроить страницу проекта по разбору: герой-баннер, блок «до и после»,
честное имя раздела про первый звук, версии и дубли бейджей — в RU и EN."""
import io
import os
import shutil

ROOT = os.environ["AV_ROOT"]
FAIL = []


def patch(path, pairs):
    p = os.path.join(ROOT, path)
    s = io.open(p, encoding="utf-8").read()
    for old, new in pairs:
        if old not in s:
            FAIL.append("%s: не найдено -> %s" % (path, old.strip()[:70]))
            continue
        s = s.replace(old, new, 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("  ok", path)


# ---------------------------------------------------------------- картинки ---
shots = os.path.join(ROOT, "doc", "shots")
for src, dst in (("_r_hero.png", "hero.png"),
                 ("_r_ba.png", "before-after.png"),
                 ("_r_how.png", "how-it-works.png")):
    shutil.copyfile(os.path.join(ROOT, "qa", "design", "c", src),
                    os.path.join(shots, dst))

# -------------------------------------------------------------------- RU ----
patch("README.md", [
    # 1. верхняя строка бейджей: оставляем релиз и лицензию
    ("""<p align="center">
  <a href="https://github.com/Daii1414/AnkiVoice/actions/workflows/checks.yml">
    <img alt="CI" src="https://github.com/Daii1414/AnkiVoice/actions/workflows/checks.yml/badge.svg">
  </a>
  <a href="https://github.com/Daii1414/AnkiVoice/releases/latest">
    <img alt="Release" src="https://img.shields.io/github/v/release/Daii1414/AnkiVoice?label=release&color=8B9BFF">
  </a>
  <a href="https://github.com/Daii1414/AnkiVoice/blob/main/LICENSE">
    <img alt="AGPL-3.0" src="https://img.shields.io/badge/license-AGPL--3.0-4F46E5.svg">
  </a>
  <img alt="Windows 10/11" src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white">
  <img alt="No cloud" src="https://img.shields.io/badge/data-off%20line%2C%20no%20cloud-12A150">
</p>""",
     """<p align="center">
  <a href="https://github.com/Daii1414/AnkiVoice/releases/latest">
    <img alt="Release" src="https://img.shields.io/github/v/release/Daii1414/AnkiVoice?label=release&color=8B9BFF">
  </a>
  <a href="https://github.com/Daii1414/AnkiVoice/blob/main/LICENSE">
    <img alt="AGPL-3.0" src="https://img.shields.io/badge/license-AGPL--3.0-4F46E5.svg">
  </a>
</p>"""),
    # 2. вторая строка бейджей дублировала первую — убираем
    ("""<p align="center">
  <img alt="Windows 10/11" src="https://img.shields.io/badge/Windows%2010%2F11-0078D6?logo=windows&logoColor=white">
  <img alt="GPU NVIDIA от 6 ГБ" src="https://img.shields.io/badge/GPU%20NVIDIA%20%E2%89%A5%206%20%D0%93%D0%91-0078D6">
  <img alt="Бесплатно" src="https://img.shields.io/badge/%D0%B1%D0%B5%D1%81%D0%BF%D0%BB%D0%B0%D1%82%D0%BD%D0%BE-12A150">
  <img alt="Без облака и телеметрии" src="https://img.shields.io/badge/%D0%B1%D0%B5%D0%B7%20%D0%BE%D0%B1%D0%BB%D0%B0%D0%BA%D0%B0%20%D0%B8%20%D1%82%D0%B5%D0%BB%D0%B5%D0%BC%D0%B5%D1%82%D1%80%D0%B8%D0%B8-12A150">
  <img alt="AGPL-3.0" src="https://img.shields.io/badge/license-AGPL--3.0-4F46E5.svg">
</p>

""", ""),
    # 3. герой-баннер сразу после кнопки
    ("""  <a href="#что-нужно-до-установки">Что нужно перед установкой →</a>
</p>
""",
     """  <a href="#что-нужно-до-установки">Что нужно перед установкой →</a>
</p>

<p align="center">
  <img src="doc/shots/hero.png" alt="Как AnkiVoice озвучивает карточку Anki: иероглифы читает нейросетевая модель синтеза речи, чтение термина берётся из фуриганы, звук ложится в поле карточки" width="1000">
</p>
"""),
    # 4. блок «до и после» — сразу после «кому это нужно»
    ("## Что умеет\n",
     "![Одна карточка до и после: AnkiVoice не трогает текст карточки и добавляет звук в два поля](doc/shots/before-after.png)\n\n## Что умеет\n"),
    # 5. схема «что происходит с карточкой»
    ("![Как это работает](doc/how-it-works.svg)",
     "![Что происходит с карточкой: фуригана из карточки → иероглифы читает модель → звук в поле карточки](doc/shots/how-it-works.png)"),
    # 6. раздел «что нового в 1.8» — история живёт в CHANGELOG
    ("""## Что нового в 1.8

- **Корень репозитория разобран по папкам:** код — в `app/`, тяжёлые архивы
  (встроенный Python и словарь Sudachi) — в `bundled/`, лаборатория — в `lab/`,
  проверки интерфейса — в `qa/`.
- **`AnkiVoice.exe` больше не в репозитории** — это артефакт сборки.

""", ""),
    # 7. «первый звук за 60 секунд» — обещание, которое страница сама опровергала
    ("## Первый звук за 60 секунд\n",
     "## Первый звук\n\n"
     "Движок синтеза ставится отдельно — это самая долгая часть установки "
     "(6–10 ГБ, его нужно скачать один раз). Когда движок на месте, от выбора "
     "колоды до первого звука проходит около минуты: выбрал колоду, выбрал "
     "голос, нажал «Начать озвучку».\n"),
    ("- [Первый звук за 60 секунд](#первый-звук-за-60-секунд)",
     "- [Первый звук](#первый-звук)"),
    ("[Первый звук за 60 секунд](#первый-звук-за-60-секунд)",
     "[Первый звук](#первый-звук)"),
    ('<a href="#первый-звук-за-60-секунд">Установка</a>',
     '<a href="#первый-звук">Установка</a>'),
    # 8. номер версии в имени файла
    ("`AnkiVoice-Setup-1.9.exe`", "`AnkiVoice-Setup-x.y.exe`"),
    # 9. ссылка на замеры — теперь там лежат все числа страницы
    ("""Подробные замеры — в
[doc/reports/](doc/reports).""",
     """Подробные замеры — в
[doc/reports/](doc/reports); все числа, которые приводит эта страница, собраны
в [doc/reports/MEASUREMENTS.md](doc/reports/MEASUREMENTS.md)."""),
    # 10. бейдж CI — вниз, к разработчикам
    ("""## Лицензия""",
     """<p align="center">
  <a href="https://github.com/Daii1414/AnkiVoice/actions/workflows/checks.yml">
    <img alt="CI" src="https://github.com/Daii1414/AnkiVoice/actions/workflows/checks.yml/badge.svg">
  </a>
</p>

## Лицензия"""),
])

# -------------------------------------------------------------------- EN ----
patch("README.en.md", [
    ("""<p align="center">
  <a href="https://github.com/Daii1414/AnkiVoice/actions/workflows/checks.yml">
    <img alt="CI" src="https://github.com/Daii1414/AnkiVoice/actions/workflows/checks.yml/badge.svg">
  </a>
  <a href="https://github.com/Daii1414/AnkiVoice/releases/latest">
    <img alt="Release" src="https://img.shields.io/github/v/release/Daii1414/AnkiVoice?label=release&color=8B9BFF">
  </a>
  <a href="https://github.com/Daii1414/AnkiVoice/blob/main/LICENSE">
    <img alt="AGPL-3.0" src="https://img.shields.io/badge/license-AGPL--3.0-4F46E5.svg">
  </a>
  <img alt="Windows 10/11" src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white">
  <img alt="No cloud" src="https://img.shields.io/badge/data-off%20line%2C%20no%20cloud-12A150">
</p>""",
     """<p align="center">
  <a href="https://github.com/Daii1414/AnkiVoice/releases/latest">
    <img alt="Release" src="https://img.shields.io/github/v/release/Daii1414/AnkiVoice?label=release&color=8B9BFF">
  </a>
  <a href="https://github.com/Daii1414/AnkiVoice/blob/main/LICENSE">
    <img alt="AGPL-3.0" src="https://img.shields.io/badge/license-AGPL--3.0-4F46E5.svg">
  </a>
</p>"""),
    ("""<p align="center">
  <img alt="Windows 10/11" src="https://img.shields.io/badge/Windows%2010%2F11-0078D6?logo=windows&logoColor=white">
  <img alt="NVIDIA GPU from 6 GB" src="https://img.shields.io/badge/NVIDIA%20GPU%20%E2%89%A5%206%20GB-0078D6">
  <img alt="Free" src="https://img.shields.io/badge/free-12A150">
  <img alt="No cloud, no telemetry" src="https://img.shields.io/badge/no%20cloud%2C%20no%20telemetry-12A150">
  <img alt="AGPL-3.0" src="https://img.shields.io/badge/license-AGPL--3.0-4F46E5.svg">
</p>

""", ""),
    ("""  <a href="#what-you-need-before-installing">What you need before installing →</a>
</p>
""",
     """  <a href="#what-you-need-before-installing">What you need before installing →</a>
</p>

<p align="center">
  <img src="doc/shots/hero.png" alt="How AnkiVoice voices an Anki card: a neural speech model reads the kanji, the reading of the term comes from the card furigana, the sound lands in the card field" width="1000">
</p>
"""),
    ("## Features\n",
     "![One card before and after: AnkiVoice does not change the card text and adds sound to two fields](doc/shots/before-after.png)\n\n## Features\n"),
    ("![How it works](doc/how-it-works.svg)",
     "![What happens to a card: furigana from the card → the model reads the kanji → sound in the card field](doc/shots/how-it-works.png)"),
    ("""## What's new in 1.8

""", """## What's new

"""),
    ("## Your first sound in 60 seconds\n",
     "## Your first sound\n\n"
     "The speech engine is a separate download - that is the slow part of the "
     "setup (6-10 GB, once). With the engine in place it takes about a minute "
     "from picking the deck to the first sound: choose the deck, choose the "
     "voice, press \"Start dubbing\".\n"),
    ("- [Your first sound in 60 seconds](#your-first-sound-in-60-seconds)",
     "- [Your first sound](#your-first-sound)"),
    ("[Your first sound in 60 seconds](#your-first-sound-in-60-seconds)",
     "[Your first sound](#your-first-sound)"),
    ('<a href="#your-first-sound-in-60-seconds">Install</a>',
     '<a href="#your-first-sound">Install</a>'),
    ("`AnkiVoice-Setup-1.9.exe`", "`AnkiVoice-Setup-x.y.exe`"),
    ("""Detailed measurements live in
[doc/reports/](doc/reports).""",
     """Detailed measurements live in
[doc/reports/](doc/reports); every number quoted on this page is collected in
[doc/reports/MEASUREMENTS.md](doc/reports/MEASUREMENTS.md)."""),
    ("""## License""",
     """<p align="center">
  <a href="https://github.com/Daii1414/AnkiVoice/actions/workflows/checks.yml">
    <img alt="CI" src="https://github.com/Daii1414/AnkiVoice/actions/workflows/checks.yml/badge.svg">
  </a>
</p>

## License"""),
])

if FAIL:
    print("НЕ НАЙДЕНО:")
    for f in FAIL:
        print("  -", f)
else:
    print("все правки применены")
