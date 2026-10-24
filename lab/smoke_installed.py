# -*- coding: utf-8 -*-
"""Smoke-тест установленного приложения (запускается в CI после сборки).

    python lab/smoke_installed.py "<путь установки>"

Проверяет состав файлов установки и первый запуск чтения иероглифов из
установленной папки — через свежераспакованный pyruntime (или in-process
haqumei). Ловит класс «свежая установка не работает»: не туда распакован
рантайм, не доехал модуль, сломан импорт.
"""
import os
import sys

EXPECTED = [
    "AnkiVoice.exe", "pipeline.bat", "README.md", "LICENSE",
    "app\\voice_pipeline.py", "app\\kana_reading.py", "app\\tts.py",
    "app\\jobs.py", "app\\voicing.py", "app\\engines.py", "app\\voices.py",
    "app\\anki_api.py", "app\\av_state.py", "app\\paths.py",
    "app\\fields_config.py", "app\\g2p_core.py", "app\\sudachi_g2p.py",
    "app\\en_translit.py", "app\\kana_stress.py",
    "lab\\quality_v2.py", "lab\\pron_check.py",
    "bundled\\pyruntime.zip", "bundled\\sudachidict.zip",
]


def main():
    if len(sys.argv) != 2:
        raise SystemExit("использование: smoke_installed.py <путь установки>")
    inst = os.path.abspath(sys.argv[1])
    missing = [m for m in EXPECTED if not os.path.isfile(os.path.join(inst, m))]
    if missing:
        raise SystemExit("в установленной папке нет: %s" % ", ".join(missing))
    print("файлы на месте: %d" % len(EXPECTED))

    sys.path.insert(0, os.path.join(inst, "app"))
    import voice_pipeline as vp  # noqa: E402 — импорт из установленной папки

    out = vp.kanaize("東京タワー")
    assert out, "пустой результат чтения"
    kanji = [c for c in out if "\u4e00" <= c <= "\u9fff"]
    assert not kanji, "остались иероглифы: %r" % out
    print("KANAIZE_OK", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
