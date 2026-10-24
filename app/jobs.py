# -*- coding: utf-8 -*-
"""Задания озвучки: что синтезировать для каждой карточки.

build_jobs() решает режим чтения карточки (asis/mix), подставляет чтение
термина из фуриганы (inject_reading*, с границами слова) и возвращает
(nid, поле, текст, исходник) на каждую операцию. Здесь же — разбор
фуриганных пар и защита от задвоения окуриганы.
"""
import re

from anki_api import plain
from fields_config import DEFAULT_FIELDS, audio_fields
from kana_reading import (KANJI_RE, _parse_furigana, furiga_pair, kanaize,
                          kanaize_card, inject_reading_lenient, kata2hira,
                          replace_term)
from tts import _qc_v2_module

# ----------------------------------------------------- операции с колодами
def word_text(note, word_src, reading=""):
    """Текст слова из поля word_src.

    word_src == 'Expression' учитывает режим источника reading:
      * "off"/"" — написание без разметки, движок читает его само;
      * имя поля — готовое чтение строго из этого поля (простое чтение
        либо фуриганная разметка); поле пустое — как при off.
    Для произвольного поля word_src — просто текст поля."""
    if word_src == "Expression":
        if reading and reading != "off":
            v = plain(note["fields"].get(reading, {}).get("value", ""))
            if "[" in v:                      # поле с фуриганой -> кана целиком
                _, v = furiga_pair(v)
                v = (v or "").strip()
            if v:
                return v
        return re.sub(r"\[[^\[\]]*\]", "",
                      plain(note["fields"].get("Expression", {})
                            .get("value", ""))).strip()
    return plain(note["fields"].get(word_src, {}).get("value", ""), strip_media=True)


def _speakable(text):
    """Есть ли в тексте хотя бы один звуковой знак.

    «！？…» или поле, состоящее из ссылок на медиа, — синтезировать нечего:
    сервер откажет, а 6 попыток и FAIL в отчёте будут лишь шумом. Если
    quality_v2 недоступен (собранный .exe), возвращаем True — не мешаем.
    """
    q2 = _qc_v2_module()
    if q2 is None:
        return True
    return q2.sound_chars(text) > 0


def term_has_latin(note, fields):
    """Есть ли в термине латиница или цифры (3D, PLATEAU, BIM/CIM, 2.0).

    Такие термины движок читает лучше сам: собственная транслитерация
    («3D» -> «すりーでぃー») звучит хуже и вводит модель в цикл
    (замер: 96 секунд и покрытие 0.89 против 4 секунд и 1.00).
    """
    f = (note.get("fields") or {})
    for name in (fields.get("furigana_src") or "ExpressionFurigana",
                 fields.get("word_src") or "Expression"):
        val = plain(f.get(name, {}).get("value", ""))
        if "[" in val:
            val = val.split("[", 1)[0]
        if re.search(r"[0-9A-Za-z]", val):
            return True
    return False


def reading_mode(fields, note, reading=""):
    """Режим чтения для этой карточки.

    Замер на карточках с редкими кандзи-терминами (движок IndexTTS 2.5):
    с подстановкой чтения из фуриганы покрытие распознавания выше
    (0.92-0.97 против 0.88-0.90 у «только кандзи»), поэтому «авто» и для
    IndexTTS берёт чтение из фуриганы. Синтаксис-аннотация самого IndexTTS
    (<base|reading>) примерили — хуже (0.64-0.92), в конвейер не вошёл.

    * "asis" — всегда кандзи, движок читает сам;
    * "mix" — термин всегда по фуригане;
    * пусто (авто) — если в поле с фуриганой что-то есть, берём термин — по фуригане; если поля пустое — всё кандзи.

    Решение принимается на каждую карточку: у чей есть фуригана — чтение по фуригане, а где ее нет — движок читает кандзи.

    Режим переключается на карточку: у других колод фуригана есть — смешание кандзи, а где пусто — кандзи.
    """
    r = (reading or "").strip().lower()
    if r == "asis":
        return "asis"
    if r == "mix":
        return "mix"
    name = fields.get("furigana_src") or "ExpressionFurigana"
    val = plain(((note.get("fields") or {}).get(name) or {}).get("value", ""))
    return "mix" if val.strip() else "asis"


def build_jobs(notes, mode, force, fields=None):
    fields = fields or DEFAULT_FIELDS
    jobs = []
    for n in notes:
        f = n["fields"]

        def tgt(name):
            return plain(f.get(name, {}).get("value", ""))

        def tgt_text(name):
            # текст на синтез: [sound:...] внутри поля вырезаем
            return plain(f.get(name, {}).get("value", ""), strip_media=True)

        src_text = ""
        # Режим для этой карточки. Термины с латиницей или цифрами
        # (3D, PLATEAU, BIM/CIM, 2.0) оставляем как есть: собственная
        # транслитерация («3D» -> «すりーでぃー») читается хуже и вводит
        # модель в цикл — замер: 96 с и покрытие 0.89 против 4 с и 1.00.
        rmode = reading_mode(fields, n, fields.get("reading", ""))
        if rmode == "mix" and term_has_latin(n, fields):
            rmode = "asis"
        if mode in ("sentence", "both"):
            text = tgt_text(fields["sentence_src"])
            if text and (force or not tgt(fields["sentence_audio"])):
                # режим «как есть»: движок получает кандзи и читает сам —
                # без подстановки чтения из фуриганы
                if rmode == "mix":
                    # кандзи + чтение термина из фуриганы:
                    # обычный текст читается в кандзи (контекст сохраняется),
                    # а термин читается ровно по фуригане
                    text = inject_reading_lenient(
                        text, n,
                        reading_field=fields.get("furigana_src", "ExpressionFurigana"))
                else:
                    # «только кандзи»: текст остаётся кандзи,
                    # движок читает сам в контексте
                    pass
                src_text = text          # исходный текст: во что будет прознесено
                if not _speakable(text):        # только пунктуация и медиа
                    continue
                jobs.append((n["noteId"], fields["sentence_audio"], text, src_text))
        if mode in ("expression", "both"):
            asis = rmode == "asis"
            text = word_text(n, fields["word_src"],
                             reading=("off" if asis else fields.get("reading", "")))
            src_text = text           # исходник: в нём ещё есть латиница
            if text and (force or not tgt(fields["word_audio"])):
                # Фуригана для основного слова — из настраиваемого поля
                furigana = plain(f.get(fields.get("furigana_src", "ExpressionFurigana"),
                                       {}).get("value", ""))
                expression = plain(f.get(fields.get("word_src", "Expression"),
                                         {}).get("value", ""))
                if not asis:
                    text = kanaize_card(text, expression=expression, furigana=furigana)
                if not _speakable(text):        # только пунктуация и медиа
                    continue
                jobs.append((n["noteId"], fields["word_audio"], text, src_text))
    return jobs


def _plural(n, one, few, many):
    """Правильное окончание: 1 операция, 2 операции, 5 операций."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return few
    return many


def _human_dur(sec):
    """Секунды -> «45 с» / «7 мин»."""
    sec = int(max(0, sec))
    if sec < 90:
        return "%d с" % sec
    return "%d мин" % round(sec / 60)
