# -*- coding: utf-8 -*-
"""Тест транслитерации английских слов и аббревиатур (en_translit)."""
import os
import sys

app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
sys.path.insert(0, app_dir)

from en_translit import transliterate_en


def test_translit():
    cases = [
        ("3D", "スリーディー"),
        ("3Dモデル", "スリーディーモデル"),
        ("2D", "ツーディー"),
        ("4K", "フォーケー"),
        ("Wi-Fi", "ワイファイ"),
        ("USBメモリ", "ユーエスビーメモリ"),
        ("IT企業", "アイティー企業"),
        ("AI技術", "エーアイ技術"),
        ("IEC規格", "アイイーシー規格"),
        ("I形グルーブ", "アイ形グルーブ"),
    ]
    for src, expected in cases:
        got = transliterate_en(src)
        assert got == expected, f"{src} -> {got} != {expected}"

    # Проверка слов через e2k (если установлен)
    try:
        import e2k  # noqa: F401 — проба доступности: нет e2k — кейсы пропускаем
        word_cases = [
            ("bus", "バス"),
            ("community", "コミュニティー"),
            ("coffee", "コーヒー"),
            ("community bus", "コミュニティー バス"),
        ]
        for src, expected in word_cases:
            got = transliterate_en(src)
            assert got == expected, f"{src} -> {got} != {expected}"
    except ImportError:
        pass

    print("OK test_en_translit")


if __name__ == "__main__":
    test_translit()
