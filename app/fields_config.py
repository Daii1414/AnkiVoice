# -*- coding: utf-8 -*-
"""Поля карточки: имена по умолчанию и профили.

DEFAULT_FIELDS — какие поля читать (текст) и куда писать (звук);
resolve_fields() накладывает переопределения (пустые значения игнорируются);
audio_fields() — какие аудио-поля чистить при клоне и проверять.
"""
DEFAULT_FIELDS = {
    "sentence_src": "Sentence",        # поле с текстом предложения
    "sentence_audio": "SentenceAudio",  # поле, куда писать звук предложения
    "word_src": "Expression",          # поле со словом (основное слово карточки)
    "furigana_src": "ExpressionFurigana",  # поле с фуриганой к основному слову
    "word_audio": "ExpressionAudio",   # поле, куда писать звук слова
    "reading": "",                        # источник чтения: "" — авто (есть фуригана — чтение по ней, нет — кандзи;
                                        # читает сам (звучит целое); "mix" — кандзи +
                                        # чтение термина из фуриганы; "off" — всё кана;
                                        # имя поля — строго из него
}


def resolve_fields(**over):
    """DEFAULT_FIELDS + переопределения (пустые значения игнорируются)."""
    f = dict(DEFAULT_FIELDS)
    for k, v in (over or {}).items():
        if v:
            f[k] = v
    return f


def audio_fields(fields):
    """Список аудио-полей, которые нужно очищать при клоне и проверять."""
    return [fields["sentence_audio"], fields["word_audio"]]
