# -*- coding: utf-8 -*-
"""Ядро чтения иероглифов: Haqumei (основной движок AnkiVoice).

Запускается отдельным встроенным Python (папка pyruntime) — так же, как
sudachi_g2p.py, потому что Haqumei требует свежий Python и своё окружение.

Ключевое отличие от Sudachi-цепочки: слово читается В КОНТЕКСТЕ ПРЕДЛОЖЕНИЯ.
Haqumei разбирает текст целиком и для каждого слова отдаёт готовое чтение
из словаря (символьные позиции позволяют вставить его обратно в текст).

Протокол обмена со скриптом voice_pipeline.py (строки JSON, UTF-8):
  пайплайн -> помощник:  {"id": <номер>, "text": "<текст>"}
  помощник -> пайплайн:  {"id": <номер>, "words": [[поверхность, чтение,
                            начало, конец, неизвестно], ...]}
  первый ответ — приветствие готовности:
                          {"ok": true, "engine": "haqumei", "version": "..."}

Чтение собирается из поля read (нотация とうきょう/せい — та же, что у
Sudachi, и её понимает любой японский фронтенд TTS). Если для слова с
иероглифами чтение не нашлось — помощник сам перечитывает слово отдельно
(Haqumei умеет давать чтение даже неизвестным иероглифам); если и это не
вышло — отдаёт пустое чтение, и пайплайн уводит всё предложение в
запасную цепочку Sudachi.
"""
import json
import os
import sys

CODE = os.path.dirname(os.path.abspath(__file__))


def _valid_read(read):
    """Пригодно ли чтение: непустое, без «?»/«*» и без иероглифов в самом чТЕНИИ."""
    return bool(read) and read not in ("?", "*") and not _KANJI.search(read)


_KANJI = None


def _init_kanji():
    global _KANJI
    import re
    _KANJI = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\U00020000-\U0002FA1f]")


def _kana_only(s):
    """Оставить только кана-символы (иー/ヴ/・/кана-расширения), выкинуть мусор.

    У pron бывают хвостовые маркеры тона (デス' с апострофом). Если после
    чистки чтение пустое или содержит иероглифы — не берём его.
    """
    out = []
    for c in s:
        o = ord(c)
        if (0x3041 <= o <= 0x309F or  # хирагана
                0x30A1 <= o <= 0x30FF or  # катакана и ー
                0x31F0 <= o <= 0x31FF or  # катакана-расширения (ㇰ…ㇿ)
                0xFF71 <= o <= 0xFF9D):  # полукатакана (для надёжности)
            out.append(c)
    return "".join(out)


def main():
    _init_kanji()
    try:
        from importlib.metadata import version as _pkgver
        from haqumei import Haqumei
        ver = _pkgver("haqumei")
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}), flush=True)
        return
    # revert_long_vowels: ー -> う/い-нотация (トーキョー -> トウキョО) — та же
    # нотация, что у Sudachi и у корпуса ROHAN; иначе сравнение и кэш конвейера
    # получают два разных стиля записи одного звука.
    # revert_yotsugana: нормализация づ/ぢ под корпус (четыре варианта знака).
    h = Haqumei(revert_long_vowels=True, revert_yotsugana=True)
    print(json.dumps({"ok": True, "engine": "haqumei", "version": ver}),
          flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            words = []
            for w in h.g2p_mapping_detailed(req["text"]):
                s, e = w.char_span
                read = w.read if w.read and w.read != "*" else ""
                # Иероглифы: берём ПРОИЗНОСИТЕЛЬНУЮ форму pron — она
                # контекстная (六百 -> ロッピャク, 殿 -> ドノ, частица
                # は -> ワ), а read — словарная (ロクヒャク, トノ).
                # У слова без иероглифов (частицы, знаки) кана проходит
                # мимо: их pron портит частицу を (ヲ вместо «о»).
                if _KANJI.search(w.word):
                    clean = _kana_only(w.pron or "")
                    if _valid_read(clean):
                        read = clean
                    elif not _valid_read(read):
                        # чтение не нашлось (слова нет даже в словаре
                        # Haqumei) — пробуем прочитать слово отдельно,
                        # там он подставит чтение по он'ёму/по модели
                        try:
                            read = h.g2k(w.word).strip()
                        except Exception:
                            read = ""
                words.append([w.word, read, s, e, bool(w.is_unknown)])
            out = {"id": req.get("id"), "words": words}
        except Exception as e:
            out = {"id": None, "error": str(e)}
        print(json.dumps(out, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
