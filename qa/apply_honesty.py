# -*- coding: utf-8 -*-
"""Таблица «что перезаписывается и что уходит в сеть» + третья колонка
«Причина» в таблице «Если что-то не работает» (по qa/REPORT.md)."""
import io
import os

ROOT = os.environ["AV_ROOT"]


def patch(name, pairs):
    p = os.path.join(ROOT, name)
    s = io.open(p, encoding="utf-8").read()
    for old, new in pairs:
        if old not in s:
            print("  ! не найдено в", name, ":", old.strip().split("\n")[0][:64])
            continue
        s = s.replace(old, new, 1)
        print("  ok", name, ":", old.strip().split("\n")[0][:56])
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


RU_OLD = """| Что происходит | Что делать |
|---|---|
| `Не найдена папка GPT-SoVITS` | Указать путь: `gptsovits_path.txt`, env `GPT_SOVITS_ROOT` или кнопкой «Обзор…» в программе |
| `AnkiConnect недоступен` | Открыть Anki; если дополнения нет — Инструменты → Дополнения → Получить дополнения, код `2055492159`, перезапустить Anki |
| `Референс X с — API требует 3–10 с` | Перерезать клип под 3–10 секунд |
| `Не получилось переключить... Перезапуск` | Норма: пайплайн сам перезапустит сервер и повторит |
| `Сервер вернул пустой звук` | Обычно видеопамять занята чужими процессами (браузер, игры). Закрыть их или перезапустить сервер: `pipeline.bat serve --voice <голос>` |
| `Пайплайн уже запущен другим процессом` | Дождаться завершения первого запуска (защита от двойной работы) |
| Windows: «Защитил ваш компьютер» | Скачанный exe не подписан: в окне SmartScreen нажми «Подробнее» → «Всё равно запустить» |"""

RU_NEW = """| Что происходит | Почему | Что делать |
|---|---|---|
| `Не найдена папка GPT-SoVITS` | путь не указан или указывает не туда | Указать путь: `gptsovits_path.txt`, env `GPT_SOVITS_ROOT` или кнопкой «Обзор…» в программе |
| `AnkiConnect недоступен` | Anki закрыта или дополнения нет | Открыть Anki; Инструменты → Дополнения → Получить дополнения, код `2055492159`, перезапустить Anki |
| `Мастер просит папку движка` | движок ставится отдельно, в установщике его нет | поставить движок и указать его папку |
| `Готовых голосов: 0 из 5` | веса или референс не в папке движка | «Обновить веса в движке» или указать верный путь |
| `Референс X с — API требует 3–10 с` | клип вне диапазона | Перерезать клип под 3–10 секунд |
| `Не получилось переключить... Перезапуск` | не хватило видеопамяти | Норма: пайплайн сам перезапустит сервер и повторит |
| `Сервер вернул пустой звук` | видеопамять занята браузером или игрой | Закрыть тяжёлые программы или перезапустить сервер: `pipeline.bat serve --voice <голос>` |
| `Пайплайн уже запущен другим процессом` | уже идёт другая работа | Дождаться её конца (защита от двойной работы) |
| Первый звук идёт минутами | включена проверка произношения | выключить «Проверять произношение» — без неё звук за секунды |
| Звук старый, хочу заново | лимит берёт только карточки без звука | «Пересобрать всё заново» — спросит подтверждение |
| Windows: «Защитил ваш компьютер» | exe не подписан | «Подробнее» → «Всё равно запустить»"""

RU_HONESTY = """
## Что перезаписывается, что уходит в сеть

Границы приложения — честно, без недосказанности.

| Действие | Что с карточкой |
|---|---|
| Озвучка | в поле звука пишется новый файл; старый остаётся в папке медиа, ссылка на него теряется |
| Текст карточки | не меняется никогда |
| Колода «Брак» | создаёт новую колоду с копиями карточек; оригиналы не трогает |
| Проверка произношения | ничего не пишет — только слушает и советует |

| Что уходит в сеть | Когда |
|---|---|
| Запрос к `api.github.com` | только по кнопке «Проверить обновления» |
| Скачивание установщика | по кнопке обновления (с проверкой SHA256) |
| Ваши карточки и тексты | **никогда** — всё считается локально |
| Телеметрия, аккаунты | **нет** |

Интернет нужен один раз: чтобы скачать установщик и движок. Сама озвучка,
проверка произношения и обновление карточек работают полностью офлайн.
"""

EN_HONESTY = """
## What gets overwritten, what goes over the network

The boundaries of the app - honestly, without hedging.

| Action | What happens to the card |
|---|---|
| Dubbing | a new file is written into the sound field; the old one stays in the media folder, and the link to it is lost |
| The card text | never changes |
| The "Брак" deck | creates a new deck with copies of the cards; the originals are not touched |
| The pronunciation check | writes nothing - it only listens and advises |

| What goes over the network | When |
|---|---|
| A request to `api.github.com` | only when you press "Check for updates" |
| Downloading the installer | from the update button (with a SHA256 check) |
| Your cards and texts | **never** - everything is computed locally |
| Telemetry, accounts | **none** |

The internet is needed once: to download the installer and the engine. The
dubbing itself, the pronunciation check and the update of your cards all run
fully offline.
"""

patch("README.md", [(RU_OLD, RU_NEW)])
patch("README.en.md", [])

# новая секция честности — вставляем перед «## Если что-то не работает» / «## Troubleshooting»
for name, anchor, block in (("README.md", "## Если что-то не работает", RU_HONESTY),
                            ("README.en.md", "## Troubleshooting", EN_HONESTY)):
    p = os.path.join(ROOT, name)
    s = io.open(p, encoding="utf-8").read()
    if anchor not in s:
        print("  ! якорь не найден в", name, anchor)
        continue
    if "Что перезаписывается" in s or "What gets overwritten" in s:
        print("  уже есть в", name)
        continue
    s = s.replace(anchor, block.strip() + "\n\n" + anchor, 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("  ok", name, ": секция честности")
print("готово")
