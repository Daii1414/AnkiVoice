# -*- coding: utf-8 -*-
"""Таблица «Если не работает»: добавить колонку «Причина» и новые строки."""
import io
import os

ROOT = os.environ["AV_ROOT"]

ROWS = [
    ("Не найдена папка GPT-SoVITS", "путь не указан или указывает не туда",
     "Указать путь: `gptsovits_path.txt`, env `GPT_SOVITS_ROOT` или кнопкой «Обзор…» в программе"),
    ("`AnkiConnect недоступен`", "Anki закрыта или дополнения нет",
     "Открыть Anki; Инструменты → Дополнения → Получить дополнения, код `2055492159`, перезапустить Anki"),
    ("Мастер просит папку движка", "движок ставится отдельно, в установщике его нет",
     "поставить движок и указать его папку"),
    ("Готовых голосов: 0 из 5", "веса или референс не в папке движка",
     "«Обновить веса в движке» или указать верный путь"),
    ("`Референс X с — API требует 3–10 с`", "клип вне диапазона",
     "Перерезать клип под 3–10 секунд"),
    ("`Не получилось переключить... Перезапуск`", "не хватило видеопамяти",
     "Норма: пайплайн сам перезапустит сервер и повторит"),
    ("`Сервер вернул пустой звук`", "видеопамять занята браузером или игрой",
     "Закрыть тяжёлые программы или перезапустить сервер: `pipeline.bat serve --voice <голос>`"),
    ("`Пайплайн уже запущен другим процессом`", "уже идёт другая работа",
     "Дождаться её конца (защита от двойной работы)"),
    ("Первый звук идёт минутами", "включена проверка произношения",
     "выключить «Проверять произношение» — без неё звук за секунды"),
    ("Звук старый, хочу заново", "лимит берёт только карточки без звука",
     "«Пересобрать всё заново» — спросит подтверждение"),
    ("Windows: «Защитил ваш компьютер»", "exe не подписан",
     "«Подробнее» → «Всё равно запустить»"),
]

EN_ROWS = [
    ("`GPT-SoVITS folder not found`", "the path is not set or points nowhere",
     "Set the path: `gptsovits_path.txt`, the `GPT_SOVITS_ROOT` environment variable, or the \"Browse…\" button in the app"),
    ("`AnkiConnect unavailable`", "Anki is closed or the add-on is missing",
     "Open Anki; Tools → Add-ons → Get Add-ons, code `2055492159`, then restart Anki"),
    ("The wizard asks for an engine folder", "the engine is a separate download",
     "install the engine and point to its folder"),
    ("Ready voices: 0 of 5", "the weights or the reference are not in the engine folder",
     "\"Refresh engine weights\" or fix the path"),
    ("`Reference X s - the API wants 3-10 s`", "the clip is out of range",
     "Trim the clip to 3-10 seconds"),
    ("`Could not switch... Restarting`", "not enough video memory",
     "Normal: the pipeline restarts the server and retries"),
    ("`The server returned an empty sound`", "VRAM is occupied by a browser or a game",
     "Close heavy programs or restart the server: `pipeline.bat serve --voice <voice>`"),
    ("`The pipeline is already running`", "another job is in progress",
     "Wait for it to finish (protection against double work)"),
    ("The first sound takes minutes", "the pronunciation check is on",
     "turn off \"Check pronunciation\" - without it the sound takes seconds"),
    ("The sound is old, I want it again", "the limit only takes cards without sound",
     "\"Rebuild everything\" - it will ask for confirmation"),
    ("Windows: \"Your PC has been protected\"", "the exe is not signed",
     "\"More info\" → \"Run anyway\""),
]


def rebuild(path, header, rows, ncol_old):
    p = os.path.join(ROOT, path)
    lines = io.open(p, encoding="utf-8").read().split("\n")
    out, i, changed = [], 0, False
    while i < len(lines):
        line = lines[i]
        if line.startswith(header):
            out.append("| %s |" % " | ".join(["Что происходит", "Почему", "Что делать"]
                                           if "Что происходит" in header
                                           else ["Message", "Why", "What to do"]))
            out.append("|---|---|---|")
            for r in rows:
                out.append("| %s | %s | %s |" % r)
            # пропускаем старую таблицу до пустой строки
            i += 1
            while i < len(lines) and lines[i].startswith("|"):
                i += 1
            changed = True
            continue
        out.append(line)
        i += 1
    if changed:
        io.open(p, "w", encoding="utf-8", newline="\n").write("\n".join(out))
        print("  ok", path, ": таблица пересобрана")
    else:
        print("  ! заголовок не найден в", path)


rebuild("README.md", "| Сообщение |", ROWS, 2)
rebuild("README.en.md", "| Message |", EN_ROWS, 2)
print("готово")
