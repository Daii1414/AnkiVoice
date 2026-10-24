# -*- coding: utf-8 -*-
"""
Английский интерфейс: словарь русский -> английский.

Словарь подставляется в страницу как I18N, а переводчик (translateDom)
меняет текст в готовом DOM. Так переводится и статическая разметка, и всё,
что появляется позже (тосты, баннеры, мастер).

Ключ — точный текст узла (обрезанный по краям). Значение — перевод.
"""
I18N_EN = {
    # --- шапка и навигация ---
    "Озвучка": "Dubbing",
    "Поля колоды": "Deck fields",
    "Голос": "Voice",
    "Приложение": "App",
    "◐ Тема": "◐ Theme",
    "Сменить тему": "Switch theme",
    "Anki: подключена": "Anki: connected",
    "Anki: не подключена": "Anki: not connected",
    "Сервер: запущен": "Server: running",
    "Сервер: не запущен": "Server: not running",
    "Выполняется": "Running",
    "Anki: …": "Anki: …",
    "Сервер: …": "Server: …",
    "Программа": "Program",
    "Версия": "Version",
    "Конфиг": "Config",

    # --- вкладка «Озвучка» ---
    "Озвучка колоды": "Deck dubbing",
    "Основное слово читается строго по фуригане, всё остальное — автоматически.":
        "The engine reads the kanji itself, the main word keeps the card's furigana. "
    "Reading mode and fields are in \u201cDeck fields\u201d.",
    "Колода": "Deck",
    "⟳ Обновить": "⟳ Refresh",
    "Загружаю колоды из Anki…": "Loading decks from Anki…",
    "Что озвучивать": "What to voice",
    "слово + предложение": "word + sentence",
    "предложение": "sentence",
    "слово": "word",
    "Лимит карточек": "Card limit",
    "0 = все": "0 = all",
    "Пересобрать всё заново": "Rebuild everything",
    "Проверять произношение": "Check pronunciation",
    "Проверять произношение (в 10 раз дольше)": "Check pronunciation (10× longer)",
    "С этой проверкой первая карточка идёт минуты вместо секунд. "
    "Приложение не зависает — журнал и полоса прогресса продолжают обновляться.":
        "With this check the first card takes minutes instead of seconds. "
        "The app does not freeze — the log and the progress bar keep updating.",
    "▶ Начать озвучку": "▶ Start dubbing",
    "■ Остановить": "■ Stop",
    "✚ Озвучить новые": "✚ Voice new cards",
    "⟳ Перепробовать": "⟳ Retry failed",
    "Предпросмотр": "Preview",
    "Ансамбль (необязательно)": "Ensemble (optional)",
    "Зажми Ctrl и выбери 2+ голоса: карточки колоды распределятся между ними случайно, "
    "каждая будет озвучена целиком одним голосом, а партии пойдут друг за другом — "
    "переключений весов будет по одному на голос, не на карточку. Уже озвученные карточки "
    "сохраняют свой прежний голос.":
        "Ctrl-click to pick 2+ voices: deck cards are split between them at "
        "random, each card is voiced entirely by one voice, and parts run one "
        "after another — weights switch once per voice, not per card. Cards "
        "already voiced keep their previous voice.",
    "Проверить колоду": "Check deck",
    "Самопроверка": "Self-test",
    "Проверить произношение": "Check pronunciation",
    "Переделать подозрительные": "Re-do doubtful ones",
    "Готов к запуску": "Ready to run",
    "Журнал": "Log",
    "Следить": "Follow",
    "Очистить": "Clear",
    "Лог появится после запуска.": "The log appears after a run.",
    "Голосов нет — нажми «Добавить голос».": "No voices — press “Add voice”.",
    "У голоса не найдены файлы gpt/sovits/ref.":
        "The voice has no gpt/sovits/ref files.",
    "Не запустилось:": "Could not start:",
    "Озвучивать было нечего.": "There was nothing to voice.",
    "Остановлено.": "Stopped.",
    "Проверка нашла проблемы.": "The check found problems.",
    "Завершилось с ошибкой (код ": "Finished with an error (code ",
    "Посмотри журнал ниже.": "See the log below.",
    "Готово.": "Done.",
    "Готово": "Done",
    "Результат записан в колоду.": "The result is in the deck.",
    "Проверка завершена — сомнительные в журнале ниже.":
        "Check finished — the doubtful ones are in the log below.",
    "Проблемы:": "Problems:",

    # --- вкладка «Поля колоды» ---
    "Поля выбранной колоды": "Fields of the selected deck",
    "Выбери колоду и нажми «Поля выбранной колоды».":
        "Pick a deck and press “Fields of the selected deck”.",
    "Роль": "Role",
    "Поле карточки": "Card field",
    "Текст предложения": "Sentence text",
    "Звук предложения →": "Sentence audio →",
    "Основное слово": "Main word",
    "Звук слова →": "Word audio →",
    "Фуригана слова ← поле": "Word furigana ← field",
    "основное слово читается строго по нему": "the main word is read strictly from it",
    "Источник чтения": "Reading source",
    "если не «Не подставлять» — переопределяет чтение": "if not “Do not substitute” it overrides the reading",
    "всего предложения": "of the whole sentence",
    "Что чем читается.": "What is read from what.",
    "— не используется —": "— not used —",
    "Сохранить настройки полей": "Save field settings",
    "✓ сохранено": "✓ saved",
    "Не удалось прочитать поля:": "Could not read the fields:",

    # --- вкладка «Голос» ---
    "Референс, текст промпта и параметры чтения выбранного голоса.":
        "Reference audio, prompt text and reading parameters of the selected voice.",
    "▶ Прослушать тест": "▶ Play test",
    "➕ Добавить голос": "➕ Add voice",
    "Обновить веса в движке": "Refresh engine weights",
    "Тест играет": "Playing test",
    "Без текста референса": "Without reference text",
    "Доп. файлы (aux)": "Extra files (aux)",
    "＋ добавить файл": "＋ add file",
    "Сохранить голос": "Save voice",
    "Новый голос": "New voice",
    "Имя (латиницей)": "Name (Latin)",
    "Как показывать": "How to show it",
    "Добавить": "Add",
    "Отмена": "Cancel",
    "Референс 3–10 с": "Reference 3–10 s",
    "что говорит голос в референсе": "what the voice says in the reference",
    "Текст референса": "Reference text",
    "Язык промпта": "Prompt language",
    "Температура": "Temperature",
    "ниже — ровнее и спокойнее": "lower — even and calmer",
    "широта выбора слов": "breadth of word choice",
    "из скольких слов выбирать": "how many words to choose from",
    "Скорость": "Speed",
    "1.0 — как в оригинале": "1.0 — as in the original",
    "файл .wav/.mp3": ".wav/.mp3 file",

    # --- вкладка «Приложение» ---
    "Папка движка, диагностика и внешний вид.":
        "Engine folder, diagnostics and appearance.",
    "Проверяю движок, Anki и голоса…": "Checking the engine, Anki and voices…",
    "Мастер настройки": "Setup wizard",
    "Открыть мастер": "Open wizard",
    "Пройти заново": "Start over",
    "Обновление": "Update",
    "Проверить обновления": "Check for updates",
    "Релизы на GitHub": "Releases on GitHub",
    "Нажми «Проверить обновления» — покажу changelog и предложу установщик.":
        "Press “Check for updates” — I will show the changelog and offer the installer.",
    "Проверить": "Check",
    "Сохранить папку": "Save folder",
    "Диагностика": "Diagnostics",
    "Нажми «Запустить диагностику».": "Press “Run diagnostics”.",
    "Запустить диагностику": "Run diagnostics",
    "Закрыть AnkiVoice": "Quit AnkiVoice",
    "Где лежат файлы": "Where the files are",
    "Всё в порядке ✓": "Everything is fine ✓",
    "Папка в порядке": "The folder is fine",
    "Папка не подходит": "The folder does not fit",
    "Папка сохранена": "Folder saved",
    "Ошибка: ": "Error: ",

    # --- мастер ---
    "Проверяю настройку…": "Checking the setup…",
    "Назад": "Back",
    "Далее": "Next",
    "Готово": "Done",
    "1. Движок GPT-SoVITS": "1. GPT-SoVITS engine",
    "2. AnkiConnect": "2. AnkiConnect",
    "3. Сервер GPT-SoVITS": "3. GPT-SoVITS server",
    "4. Тестовая фраза": "4. Test phrase",
    "Что не так:": "What is wrong:",
    "Проверить и сохранить": "Check and save",
    "Подставить найденную": "Use the found one",
    "Скачать GPT-SoVITS": "Download GPT-SoVITS",
    "Куда класть.": "Where to put it.",
    "Что сделать:": "What to do:",
    "Открыть AnkiConnect": "Open AnkiConnect",
    "Скачать Anki": "Download Anki",
    "Запускаю…": "Starting…",
    "Запустить сервер": "Start the server",
    "Открыть журнал": "Open the log",
    "Можно пропустить.": "You can skip this.",
    "не закрывай мастер, первый старт небыстрый.":
        "do not close the wizard, the first start is slow.",
    "Открыть вкладку «Голос»": "Open the “Voice” tab",
    "Проверим весь путь: голос → сервер → звук. Это последний шаг мастера.":
        "Let us check the whole path: voice → server → sound. This is the last step.",
    "Фраза": "Phrase",
    "Синтезирую…": "Synthesizing…",
    "Синтезировать тестовую фразу": "Synthesize the test phrase",
    "Тестовый звук готов ✓": "Test sound ready ✓",
    "Это тест от прошлого запуска. Синтезируй фразу заново, чтобы завершить настройку.":
        "This is a test from an earlier run. Synthesize the phrase again to finish the setup.",
    "Настройка завершена. Можно закрывать мастер.":
        "The setup is complete. You can close the wizard.",
    "Проверить снова": "Check again",

    # --- обновления ---
    "Установлено": "Installed",
    "Страница релиза": "Release page",
    "Открыть релизы": "Open releases",
    "Не удалось проверить обновления: ": "Could not check for updates: ",

    # --- файловый выбор ---
    "Выбор файла": "File picker",
    "↑ Вверх": "↑ Up",
    "Выбрать": "Choose",
    "Загрузка…": "Loading…",
    "Папка пуста": "The folder is empty",
    "… вверх": "… up",

    # --- диагностика (тексты) ---
    "Анки: ": "Anki: ",
    "Сервер: ": "Server: ",
    "Голосов: ": "Voices: ",
    "Проблемы: ':esc(bad.join(\" · \"))+": "Problems: ' + esc(bad.join(\" · \")) +",
    "Не запустилось:": "Could not start:",
    "открой Anki": "open Anki",
    ". Заметок в выбранной:": ". Cards in the selected deck:",
    "Сервер не отвечает:": "The server does not respond:",
    "Папка GPT-SoVITS:": "GPT-SoVITS folder:",
    "не подключена": "not connected",
    "не запущен (поднимется сам)": "not running (will start itself)",
    "подключена": "connected",
    "запущен": "running",
    "АнкиVoice закрыт. Можно закрыть вкладку.": "AnkiVoice is closed. You can close the tab.",
    "AnkiVoice закрыт. Можно закрыть вкладку.": "AnkiVoice is closed. You can close the tab.",
    "Не удалось прочитать настройку: ": "Could not read the setup: ",
    "Папка проверена:": "Folder checked:",
    "Папка не найдена или в ней не хватает файлов": "Folder not found or files are missing",
    "AnkiConnect отвечает — Anki запущена.": "AnkiConnect answers — Anki is running.",
    "AnkiConnect не отвечает.": "AnkiConnect does not answer.",
    "Сервер уже запущен и отвечает.": "The server is already running.",
    "Сервер пока не запущен.": "The server is not running yet.",
    "Нет ни одного голоса с полным набором файлов.": "Not a single voice has the full set of files.",
    "Файлы весов на месте.": "The weight files are in place.",
    "Сначала выбери колоду": "Pick a deck first",
    "Сначала выбери голос": "Pick a voice first",
    "Скачиваем установщик…": "Downloading the installer…",    # --- добавленные строки (покрытие интерфейса) ---
    "Папка в порядке ✓": "The folder is fine ✓",
    "нет — слово прочитается автоматически": "none - the word is read automatically",
    "✓ файлы на месте": "✓ files in place",
    "✗ нет gpt/sovits/ref": "✗ no gpt/sovits/ref",
    "Внутри должны быть": "It must contain",
    "Фуригана:": "Furigana:",
    "Конфиг:": "Config:",
    "Сервер:": "Server:",
    "Голосов:": "Voices:",
    "Не подставлять": "Do not substitute",
    "Как есть (кандзи, без фуриганы)":
        "As is (kanji, no furigana)",
    "Авто: есть фуригана — чтение по ней, нет — кандзи":
        "Auto: furigana present - use it, otherwise kanji",
    "Только кандзи (движок читает сам)":
        "Kanji only (the engine reads it)",
    "Собрать колоду «Брак»":
        "Build the “Брак” deck",
    "Сводка по вердиктам":
        "Verdict summary",
    "Первый запуск грузит веса и CUDA — это может занять 1–2 минуты.":
        "The first start loads the weights and CUDA — it may take 1-2 minutes.",
    "SHA256 будет проверен после скачивания.":
        "The SHA256 will be checked after the download.",
    "Проверяю SHA256…": "Checking the SHA256…",
    "Проверяю релиз на GitHub…": "Checking the release on GitHub…",
    "Проверяю настройку…": "Checking the setup…",
    "Проверяю движок, Anki и голоса…": "Checking the engine, Anki and voices…",
    "Начинаю скачивание…": "Starting the download…",
    "Новых версий нет.": "No new versions.",
    "Доступно обновление ": "Update available ",
    "Скачай вручную со страницы релиза.":
        "Download it manually from the release page.",
    "В релизе нет установщика или SHA256. ": "The release has no installer or SHA256. ",
    "Вставь код": "Paste the code",
    "Запустить установщик": "Run the installer",
    "Инструменты → Дополнения → Получить дополнения":
        "Tools → Add-ons → Get Add-ons",
    "Если Anki не установлена — сначала скачай её.":
        "If Anki is not installed, download it first.",
    "Открой Anki.": "Open Anki.",
    "Перезапусти Anki и вернись сюда.": "Restart Anki and come back here.",
    "Попробовать снова": "Try again",
    "Посмотри журнал ниже.": "See the log below.",
    "Пустой выбор в колонке «→» = звук не записывать.":
        "An empty choice in the «→» column means: do not record the sound.",
    "Распознать уже озвученные карточки и найти те, где модель потеряла кусок фразы":
        "Recognize the cards you have already voiced and find the ones where the "
        "model lost a chunk of the sentence",
    "Распознаём собственный звук и сверяем с текстом: ловим «модель потеряла кусок фразы»":
        "We recognize our own sound and compare it with the text: this catches "
        "«the model lost a chunk of the sentence»",
    "Переделать только те карточки, которые проверка признала подозрительными (тег av_suspect)":
        "Re-do only the cards the check called doubtful (tag av_suspect)",
    "Открой вкладку «Голос»: добавь голос (GPT .ckpt, SoVITS .pth и референс) ":
        "Open the «Voice» tab: add a voice (GPT .ckpt, SoVITS .pth and a reference) ",
    "или нажми «Новый голос».": "or press «New voice».",
    "Сначала выбери колоду": "Pick a deck first",
    "Сначала выбери голос": "Pick a voice first",
    "Обзор…": "Browse…",
    "Подставить найденную: ": "Use the found one: ",
    "Сервер не отвечает:": "The server does not respond:",
    "Папка GPT-SoVITS:": "GPT-SoVITS folder:",
    "АнкиConnect не отвечает.": "AnkiConnect does not answer.",
    "AnkiConnect отвечает — Anki запущена.": "AnkiConnect answers — Anki is running.",
    "Сервер уже запущен и отвечает.": "The server is already running.",
    "Сервер пока не запущен.": "The server is not running yet.",
    "Папка проверена:": "Folder checked:",
    "Настройка завершена. Можно закрывать мастер.":
        "The setup is complete. You can close the wizard.",
    "Синтезирую…": "Synthesizing…",
    "Синтезировать тестовую фразу": "Synthesize the test phrase",
    "Завершилось с ошибкой (код ": "Finished with an error (code ",
    "Проблемы: ": "Problems: ",
    "Не удалось прочитать настройку: ": "Could not read the setup: ",
    "Не удалось проверить обновления: ": "Could not check for updates: ",
    "· последний релиз": "· latest release",
    "Загружаю колоды из Anki…": "Loading decks from Anki…",
    "Не подключена": "Not connected",
    "НЕ подключена": "NOT connected",
    "не запущен": "not running",
    "запущен": "running",
    "подключена": "connected",
    "не подключена": "not connected",
    "Загрузка…": "Loading…",
    "Папка пуста": "The folder is empty",
    "… вверх": "… up",
    "↑ Вверх": "↑ Up",
    "Выбрать": "Choose",
    "Ошибка: ": "Error: ",
    "✓ сохранено": "✓ saved",
    "Папка сохранена": "Folder saved",
    "Папка не подходит": "The folder does not fit",
    "Всё в порядке ✓": "Everything is fine ✓",
    "Проверить и сохранить": "Check and save",
    "Скачать GPT-SoVITS": "Download GPT-SoVITS",
    "Скачать Anki": "Download Anki",
    "Открыть AnkiConnect": "Open AnkiConnect",
    "Запустить сервер": "Start the server",
    "Открыть журнал": "Open the log",
    "Можно пропустить.": "You can skip this.",
    "не закрывай мастер, первый старт небыстрый.":
        "do not close the wizard, the first start is slow.",
    "Что не так:": "What is wrong:",
    "Что сделать:": "What to do:",
    "Куда класть.": "Where to put it.",
    "Фраза": "Phrase",
    "Тестовый звук готов ✓": "Test sound ready ✓",
    "Открыть вкладку «Голос»": "Open the «Voice» tab",
    "Закрыть AnkiVoice": "Quit AnkiVoice",
    "Где лежат файлы": "Where the files are",
    "Релизы на GitHub": "Releases on GitHub",
    "Открыть релизы": "Open releases",
    "Установлено": "Installed",
    "Страница релиза": "Release page",
    "Английский интерфейс": "English interface",
    "Русский интерфейс": "Russian interface",
    "не подключена ": "not connected ",
    "Подключена ": "Connected ",
    "не запущен (поднимется сам)": "not running (will start itself)",
    "Файл: ": "File: ",
    "Причина: ": "Reason: ",
    "Стратегия: ": "Strategy: ",
    "Карточка: ": "Card: ",
    "Покрытие: ": "Coverage: ",
    "Проблемный участок: ": "Problem span: ",
    "Вердикт: ": "Verdict: ",
    "Как было: ": "As it was: ",
    "Вариант ": "Variant ",
    "Можно пропустить": "You can skip this",
    "Проверка нашла проблемы.": "The check found problems.",
    "Проверка завершена — сомнительные в журнале ниже.":
        "Check finished — the doubtful ones are in the log below.",
    "Результат записан в колоду.": "The result is in the deck.",
    "Не запустилось:": "Could not start:",
    "Озвучивать было нечего.": "There was nothing to voice.",
    "Остановлено.": "Stopped.",
    "Готово.": "Done.",    "Колод в Anki: ": "Decks in Anki: ",
    "Голос по умолчанию: ": "Default voice: ",
    "Доступна: ": "Available: ",
    ". Каждый кусок распознаём и сверяем с текстом — мусор переделаем сами.":
        ". Every chunk is recognized and compared with the text — we redo the rubbish ourselves.",
    "Движок": "Engine",
    "Сервер": "Server",
    "Тест голоса": "Voice test",
    "голос: ": "voice: ",
    "Закрыть": "Close",
    "Установлено ": "Installed ",
    "Папка в порядке.": "The folder is fine.",
    # --- правки 1.3: режим чтения, поля колоды, мастер, оформление ---
    "Движок читает иероглифы сам, а чтение слова — ровно по фуригане карточки. Режим чтения и поля — в «Полях колоды».":
        "The engine reads the kanji itself, and the main word follows the card's "
        "furigana. The reading mode and the fields are in “Deck fields”.",
    "Что каким полем читать и куда класть звук. Значения подставляются автоматически — поправь, если колода называет поля иначе.":
        "Which field to read from and where to put the audio. The values are filled "
        "in automatically - fix them if your deck names its fields differently.",
    "Как это читается.": "How this is read.",
    "Движок читает иероглифы сам, в контексте предложения. Режим":
        "The engine reads the kanji itself, in the context of the sentence. The",
    "«Авто»": "“Auto”",
    "(по умолчанию) читает основное слово строго по строке «Фуригана слова»; если фуриганы нет — кандзи, как есть. Режим":
        "(by default) reads the main term strictly from the “Furigana” field; with "
        "no furigana it is read as kanji, as it is. The",
    "«Только кандзи»": "“Kanji only”",
    "— всегда кандзи: чтение движок подбирает сам.":
        "- always kanji: the engine picks the reading itself.",
    "Режим сохраняется в профиле колоды — у каждой колоды свой.":
        "The mode is stored in the deck profile - every deck has its own.",
    "как читать основное слово: по фуригане, если она есть; нет фуриганы — кандзи":
        "how the main term is read: from the furigana if there is one; without a "
        "furigana - kanji",
    "Папка GPT-SoVITS": "GPT-SoVITS folder",
    "Закрывает приложение и локальный сервер. Карточки в Anki не трогаются.":
        "Closes the app and the local server. Your Anki cards are not touched.",
    "Полей в колоде:": "Fields in the deck:",
    "Готово ✓": "Ready ✓",
    "Кубота Хитоси": "Hitoshi Kubota",
    "и": "and",
    # --- выбор движка (1.3) ---
    "Движок синтеза": "Synthesis engine",
    "GPT-SoVITS — голос из весов .ckpt и .pth":
        "GPT-SoVITS — a voice from .ckpt and .pth weights",
    "IndexTTS 2.5 — голос из одного референса":
        "IndexTTS 2.5 — a voice from a single reference",
    "Папка IndexTTS 2.5": "IndexTTS 2.5 folder",
    "Папка IndexTTS": "IndexTTS folder",
    "Движок с весами: у каждого голоса свои файлы .ckpt и .pth.":
        "Engine with weights: every voice has its own .ckpt and .pth files.",
    "Zero-shot движок: голос — это один референс, веса общие у модели.":
        "Zero-shot engine: a voice is a single reference, the weights are shared.",
    "Движок: IndexTTS 2.5": "Engine: IndexTTS 2.5",
    "Движок: GPT-SoVITS": "Engine: GPT-SoVITS",
    # --- выбор движка на главном экране (1.5) ---
    "Голос задаётся весами .ckpt и .pth. Синтез быстрее, голосов можно много.":
        "A voice is defined by .ckpt and .pth weights. Synthesis is faster, you can have many voices.",
    "Голос — это один референс. Японские термины читает точнее, но синтез медленнее.":
        "A voice is a single reference. Japanese terms are read more accurately, but synthesis is slower.",
    "Папка движка": "Engine folder",
    "Сохранить": "Save",
    "Папка в порядке ✓": "Folder is fine ✓",
    "папка в порядке ✓": "folder is fine ✓",
    "папка не указана": "folder is not set",
    "папка не подходит": "folder doesn't fit",
    "Готовых голосов: ": "Voices ready: ",
    "Сервис синтеза на 127.0.0.1:9881": "Synthesis service on 127.0.0.1:9881",
    "Сервер синтеза на 127.0.0.1:9880": "Synthesis server on 127.0.0.1:9880",
    "Кто будет читать текст. Движок можно поменять в любой момент — такие же кнопки есть на главном экране, вверху.":
        "Who will read the text. You can switch the engine at any time — the same buttons are on the main screen, at the top.",
    "✓ выбран": "✓ selected",
    "Куда класть.": "Where to put it.",
    "Скачать движок": "Download the engine",
    "Укажи папку движка": "Point to the engine folder",
    "Сервер синтеза": "Synthesis server",
    "Сервис IndexTTS слушает только": "The IndexTTS service listens only on",
    "Мастер настройки, обновление, диагностика и файлы. Движок синтеза выбирается на главном экране.":
        "Setup wizard, updates, diagnostics and files. The synthesis engine is chosen on the main screen.",
    # --- разбор первых пользователей (1.6) ---
    "пусто — вся колода": "empty — the whole deck",
    "Пропустить": "Skip",
    "Медиа Anki (куда падает звук)": "Anki media (where the audio lands)",
    "Журнал и отчёт о сбоях": "Log and crash report",
    "Подтверждение": "Confirm",
    "Да": "Yes",
    "Озвучить всё": "Voice everything",
    "Переозвучить": "Re-record",
    "Собрать": "Build",
    "Сбросить": "Reset",
    "Перезаписывает звук в выбранных карточках заново. Старые файлы останутся в папке медиа, отмены нет":
        "Re-records the audio in the selected cards. The old files stay in the media folder, there is no undo",
    "Внимание: проверка замедляет озвучку примерно в 10 раз.":
        "Note: the check makes the dubbing about 10 times slower.",
    "Звук пишется прямо в поля карточек Anki:":
        "The audio is written straight into the Anki card fields:",
    "готовый звук перезаписывается":
        "an existing sound is overwritten",
    ", старые файлы остаются в папке медиа коллекции. Отмены нет — переозвучить можно через «Пересобрать всё заново». Всё считается на этом компьютере, карточки никуда не отправляются.":
        ", the old files stay in the collection's media folder. There is no undo — you can re-record with “Rebuild everything”. Everything runs on this computer; your cards are never sent anywhere.",
    "Закрывает приложение и локальный сервер. Карточки и звук в Anki остаются как есть.":
        "Closes the app and the local server. Your cards and their audio stay as they are.",
    "Папка не подходит — не сохранил": "Folder doesn't fit — not saved",
    "Папка не подходит": "Folder doesn't fit",
    "не нашли": "not found",
    "Лимит карточек должен быть целым числом больше нуля. Чтобы озвучить всю колоду, оставь поле пустым":
        "The card limit must be a whole number greater than zero. Leave it empty to voice the whole deck",
    "Лимит карточек — целое число не меньше нуля. Пусто или 0 — вся колода":
        "The card limit must be a whole number not below zero. Empty or 0 means the whole deck",
    "Лимит карточек должен быть целым числом не меньше нуля.":
        "The card limit must be a whole number not below zero.",
    "Лимит карточек должен быть не меньше нуля. Пусто или 0 — вся колода.":
        "The card limit must not be below zero. Empty or 0 means the whole deck.",
    "Лимит карточек должен быть больше нуля. Чтобы озвучить всю колоду, оставь поле пустым и подтверди запуск.":
        "The card limit must be greater than zero. Leave it empty and confirm to voice the whole deck.",
    "■ остановлено": "■ stopped",
    "Начинаю озвучку: колода": "Starting dubbing: deck",
    "Сходит в сеть на GitHub и покажет changelog": "Goes online to GitHub and shows the changelog",
    "Нажми «Проверить обновления» — покажу changelog и предложу установщик. Эта кнопка ходит в интернет на GitHub; сама озвучка работает офлайн.":
        "Press \"Check for updates\" and I will show the changelog and offer the installer. This button goes online to GitHub; the dubbing itself works offline.",

    # --- мастер и шапки (аудит интерфейса) ---
    ". Фуригана:":
        ". Furigana:",
    "движок":
        "engine",
    "сервер":
        "server",
    "голоса":
        "voices",
    "тест":
        "test",
    "(необязательно)":
        "(optional)",
    "AnkiConnect":
        "AnkiConnect",
    "AnkiVoice — оболочка. Синтез делает отдельный движок GPT-SoVITS; он весит несколько гигабайт и ставится один раз.":
        "AnkiVoice is a shell. A separate GPT-SoVITS engine does the synthesis; it weighs several gigabytes and is installed once.",
    "Скачай Windows-пакет GPT-SoVITS v2Pro, распакуй в папку без кириллицы (например,":
        "Download the Windows package of GPT-SoVITS v2Pro and unpack it into a folder without Cyrillic (for example,",
    ") и укажи её здесь. Внутри должны быть":
        ") and point to it here. Inside there must be",
    "Через AnkiConnect программа читает колоды и записывает звук в карточки. Без него озвучка не начнётся.":
        "Through AnkiConnect the app reads the decks and writes the audio into the cards. Without it the dubbing will not start.",
    "и нажми «ОК».":
        "and press “OK”.",
    "Сервер слушает только":
        "The server listens only on",
    ". Первый запуск грузит веса и CUDA — это может занять 1–2 минуты.":
        ". The first start loads the weights and CUDA - it may take 1-2 minutes.",
    "Если сервер ещё не поднят, тестовая фраза запустит его автоматически. Этот шаг нужен, чтобы заранее увидеть ошибки движка.":
        "If the server is not up yet, the test phrase starts it automatically. This step lets you see the engine problems in advance.",
    "Открой вкладку «Голос»: добавь голос (GPT .ckpt, SoVITS .pth и референс) или нажми «Обновить веса в движке».":
        "Open the “Voice” tab: add a voice (GPT .ckpt, SoVITS .pth and a reference) or press “Update the weights in the engine”.",
    "Колода в Anki: ":
        "Decks in Anki: ",

}


