# -*- coding: utf-8 -*-
"""Английские версии трёх картинок: та же вёрстка, английский текст."""
import io
import os

ROOT = os.environ["AV_ROOT"]
D = os.path.join(ROOT, "qa", "design", "c")

TR = {
    # --- hero ---
    "Озвучка японских карточек Anki — на своём компьютере":
        "Japanese audio for your Anki cards — on your own computer",
    "GPU NVIDIA ≥ 6 ГБ": "GPU NVIDIA ≥ 6 GB",
    "Офлайн, без аккаунтов": "Offline, no accounts",
    "AGPL-3.0, бесплатно": "AGPL-3.0, free",
    "Японские карточки Anki": "Japanese Anki cards",
    "начинают говорить": "start talking",
    "Нейросетевая модель синтеза речи читает иероглифы сама — в контексте":
        "A neural speech model reads the kanji itself — in context",
    "предложения, а чтение редкого термина берётся из фуриганы карточки.":
        "of the sentence, while a rare term is read from the card's furigana.",
    "Звук ложится прямо в поля Anki. Всё считается на вашем компьютере.":
        "The sound lands straight in the Anki fields. Everything runs on your computer.",
    "GPT-SoVITS — свой голос из весов. IndexTTS 2.5 — хватит референса 3–10 с":
        "GPT-SoVITS — your own voice from weights. IndexTTS 2.5 — a 3–10 s reference is enough",
    "Качество проверяется по нескольким независимым сигналам — брак перегенерируется сам":
        "Quality is checked by several independent signals — bad takes are redone automatically",
    "Приложение слушает свой звук и сверяет его с текстом — это совет, решение твоё":
        "The app listens to its own sound and compares it with the text — advice, your call",
    "Скачать AnkiVoice": "Download AnkiVoice",
    "Windows · 125 МБ · установщик": "Windows · 125 MB · installer",
    "Что нужно перед установкой →": "What you need first →",
    "движок 6–10 ГБ ставится отдельно — мастер подскажет":
        "the 6–10 GB engine installs separately — the wizard points the way",
    "Карточки никуда не уходят: телеметрии нет, аккаунтов нет, сеть нужна только чтобы скачать.":
        "Cards never leave your machine: no telemetry, no accounts, the network is only used to download.",
    "Карточка Anki · колода «Архитектура»": "Anki card · deck “Architecture”",
    "фуригана: てんぐん": "furigana: てんぐん",
    "звука нет": "no sound yet",
    "на вход движка:": "engine input:",
    "На вход движка:": "Engine input:",
    "Нейросетевая модель синтеза речи": "Neural speech synthesis model",
    "GPT-SoVITS · IndexTTS 2.5 — на вашей видеокарте":
        "GPT-SoVITS · IndexTTS 2.5 — on your GPU",
    "127.0.0.1 · интернет не нужен · 6–10 ГБ на диске":
        "127.0.0.1 · no internet needed · 6–10 GB on disk",
    "поле звука": "sound field",
    "озвучено": "voiced",
    "Одна карточка — один проход движка: текст на кандзи, чтение термина — из фуриганы.":
        "One card — one engine pass: kanji text, term reading from the furigana.",
    # --- как это работает ---
    "Что происходит с карточкой": "What happens to a card",
    "Три шага, которые делает приложение, когда нажимаешь «Начать озвучку».":
        "The three steps the app runs when you press “Start dubbing”.",
    "Карточка": "The card",
    "Лицевая сторона карточки": "Front of the card",
    "Лицевая сторона карточки — та же самая": "Front of the card — the very same",
    "Из колоды читаются два поля:": "Two fields are read from the deck:",
    "предложение и основное слово.": "the sentence and the main term.",
    "К слову прилагается фуригана —": "The furigana comes with the term —",
    "если она в карточке есть.": "when the card has one.",
    "Пустое поле фуриганы — значит «читай сам».":
        "An empty furigana field means “read it yourself”.",
    "Поля настраиваются один раз на колоду.": "Fields are set once per deck.",
    "Движок читает сам": "The engine reads",
    "слово заменено чтением из фуриганы,": "the term is replaced by its furigana reading,",
    "остальное — кандзи, в контексте": "the rest stays kanji, in context",
    "В движок уходит предложение кандзи,": "The engine gets the kanji sentence,",
    "целиком: модель читает иероглифы сама,": "whole: the model reads the kanji itself,",
    "в контексте — звук связный, а не набор": "in context — the sound is connected, not a set of",
    "отдельных слов.": "separate words.",
    "GPT-SoVITS или IndexTTS 2.5 — на своей GPU,": "GPT-SoVITS or IndexTTS 2.5 — on your GPU,",
    "через 127.0.0.1, без интернета.": "over 127.0.0.1, no internet.",
    "Звук в поле": "Sound in the field",
    "На выходе .ogg в поле звука.": "The result is an .ogg in the sound field.",
    "Файл проверяется по нескольким": "The file is checked by several",
    "независимым сигналам, и брак": "independent signals, and a bad take is",
    "движок перегенерирует сам.": "redone by the engine.",
    "Не помогло — карточка остаётся": "If that fails — the card stays",
    "неозвученной и попадает в отчёт.": "unvoiced and lands in the report.",
    "А если всё-таки прозвучало не то?": "And if it still sounds wrong?",
    "Отдельно можно включить проверку произношения: приложение слушает собственный звук":
        "A pronunciation check can be turned on separately: the app listens to its own sound",
    "и сверяет его с текстом — показывает, где фраза разошлась. Это совет, а не приговор:":
        "and compares it with the text — showing where the phrase drifted. It is advice, not a verdict:",
    "на 27 размеченных карточках подтверждённых браков было 2, а ложных срабатываний — 25.":
        "on 27 marked cards there were 2 confirmed defects and 25 false alarms.",
    # --- до и после ---
    "Одна карточка — до и после": "One card — before and after",
    "Приложение не трогает текст карточки. Оно добавляет звук — в два поля.":
        "The app does not touch the card text. It adds sound — to two fields.",
    "Без AnkiVoice": "Without AnkiVoice",
    "поле пустое": "field empty",
    "Карточка молчит. Иероглифы читаются глазами, а не ухом.":
        "The card is silent. The kanji are read with the eyes, not the ear.",
    "нажал": "pressed",
    "«Начать озвучку»": "“Start dubbing”",
    "всё локально": "all local",
    "После AnkiVoice": "After AnkiVoice",
    "Тот же текст, тот же термин, тот же голос — плюс звук.":
        "Same text, same term, same voice — plus sound.",
    "Текст карточки не меняется": "The card text is never changed",
    "Приложение пишет только в поля звука.": "The app writes only into the sound fields.",
    "Разметка, теги и карточки — без изменений.": "Formatting, tags and cards stay untouched.",
    "Отменить озвучку нельзя": "A dub cannot be undone",
    "Старый .ogg остаётся в папке медиа Anki,": "The old .ogg stays in the Anki media folder,",
    "но ссылка на него в карточке теряется.": "but the card loses the link to it.",
    "Лимит — это объём работы": "The limit is the amount of work",
    "«Озвучить 20 карточек» — это 20 карточек": "“Voice 20 cards” means 20 cards",
    "без звука, а не первые 20 в колоде.": "without sound, not the first 20 in the deck.",
}

FILES = [("hero.svg", "hero.en.svg"),
         ("block-how-it-works.svg", "block-how-it-works.en.svg"),
         ("block-before-after.svg", "block-before-after.en.svg")]

missing = set(TR)
for src, dst in FILES:
    s = io.open(os.path.join(D, src), encoding="utf-8").read()
    # длинные строки — раньше коротких, иначе короткая съедает начало длинной
    for ru in sorted(TR, key=len, reverse=True):
        en = TR[ru]
        if ru in s:
            s = s.replace(ru, en)
            missing.discard(ru)
    io.open(os.path.join(D, dst), "w", encoding="utf-8", newline="\n").write(s)
    print("  ok", dst)

if missing:
    print("НЕ НАЙДЕНЫ в исходниках:")
    for m in sorted(missing):
        print("  -", m)
else:
    print("все строки переведены")
