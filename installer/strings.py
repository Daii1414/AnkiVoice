# -*- coding: utf-8 -*-
"""Тексты установщика Windows (страница «Что нужно для работы»).

Источник — русский; английский — здесь же; остальные языки собирает
lab/build_locales.py в installer/messages.iss ([CustomMessages] Inno Setup).
%1, %2 — подстановки FmtMessage, их нельзя терять при переводе.
"""

RU = {
    "DepTitle": "Что нужно для работы",
    "DepSub": "Установщик проверил компьютер. Отметь, что скачать и установить, — или укажи папку, если программа уже стоит в другом месте (например, на другом диске).",
    "DepFound": "Найдено: %1",
    "DepMissing": "Не найдено",
    "DepOptional": "необязательно",
    "DepInstall": "Скачать и установить",
    "DepHaveDir": "Уже установлено — папка:",
    "DepBrowse": "Обзор…",
    "DepAnki": "Anki — программа с карточками",
    "DepAnkiHint": "AnkiVoice записывает звук прямо в карточки Anki. Папка — та, где лежит anki.exe.",
    "DepConnect": "AnkiConnect — дополнение Anki (код 2055492159)",
    "DepConnectHint": "Через него AnkiVoice разговаривает с Anki. Папка — данные Anki (Anki2, внутри addons21).",
    "DepEngine": "GPT-SoVITS — движок синтеза голоса",
    "DepEngineHint": "Около 7 ГБ на диске. Папка — та, где лежит api_v2.py.",
    "DepGpu": "Драйвер видеокарты NVIDIA",
    "DepGpuHint": "Необязательно: без видеокарты NVIDIA голос синтезируется на процессоре, в несколько раз медленнее.",
    "DepGpuOpen": "Открыть страницу драйверов NVIDIA",
    "DepBadDir": "В папке «%1» нет нужных файлов (%2). Выбери другую папку или отметь «Скачать и установить».",
    "DepEmptyDir": "Укажи папку для «%1» или отметь «Скачать и установить».",
    "DepPlanTitle": "Перед установкой",
    "DepPlan": "Будет скачано и установлено:",
    "DepPlanNone": "Ничего докачивать не нужно — всё найдено.",
    "DepPlanSkip": "Пропущено (можно поставить позже, AnkiVoice подскажет как):",
    "DepRunning": "Запускаю установщик «%1» — заверши его, затем установка продолжится.",
    "DepExtracting": "Распаковываю «%1» — это может занять несколько минут…",
    "DepFailed": "Не удалось установить «%1»: %2. Его можно поставить позже — AnkiVoice подскажет, как.",
    "DepNeedTar": "Не удалось распаковать архив движка. Распакуй его вручную 7-Zip'ом в «%1».",
}

EN = {
    "DepTitle": "What AnkiVoice needs",
    "DepSub": "Setup has checked this computer. Tick what to download and install — or point to a folder if the program is already installed elsewhere (for example, on another drive).",
    "DepFound": "Found: %1",
    "DepMissing": "Not found",
    "DepOptional": "optional",
    "DepInstall": "Download and install",
    "DepHaveDir": "Already installed — folder:",
    "DepBrowse": "Browse…",
    "DepAnki": "Anki — the flashcard program",
    "DepAnkiHint": "AnkiVoice writes audio straight into Anki cards. The folder is the one with anki.exe.",
    "DepConnect": "AnkiConnect — Anki add-on (code 2055492159)",
    "DepConnectHint": "AnkiVoice talks to Anki through it. The folder is Anki's data folder (Anki2, with addons21 inside).",
    "DepEngine": "GPT-SoVITS — the voice synthesis engine",
    "DepEngineHint": "About 7 GB on disk. The folder is the one with api_v2.py.",
    "DepGpu": "NVIDIA graphics driver",
    "DepGpuHint": "Optional: without an NVIDIA GPU the voice is synthesized on the CPU, several times slower.",
    "DepGpuOpen": "Open the NVIDIA driver page",
    "DepBadDir": "The folder “%1” lacks the required files (%2). Pick another folder or tick “Download and install”.",
    "DepEmptyDir": "Choose a folder for “%1” or tick “Download and install”.",
    "DepPlanTitle": "Before installing",
    "DepPlan": "Will be downloaded and installed:",
    "DepPlanNone": "Nothing to download — everything was found.",
    "DepPlanSkip": "Skipped (can be installed later, AnkiVoice will explain how):",
    "DepRunning": "Starting the “%1” installer — finish it and setup will continue.",
    "DepExtracting": "Extracting “%1” — this may take a few minutes…",
    "DepFailed": "Could not install “%1”: %2. It can be installed later — AnkiVoice will explain how.",
    "DepNeedTar": "Could not extract the engine archive. Extract it manually with 7-Zip into “%1”.",
}
