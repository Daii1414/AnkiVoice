"""Что реально выдаёт kanaize на полукатакане и проблемных текстах.

Если нормализация работает, ｶﾞｷｮｳ -> がきょう (осмысленно, но модель всё
равно проваливается). Если нет -> остаётся мусор из съёмных знаков.
"""
import os
import sys

sys.path.insert(0, r"E:\TTS-проект")
os.chdir(r"E:\TTS-проект")
import voice_pipeline as vp  # noqa: E402

CASES = ["ｶﾞｷｮｳ", "ﾊﾟﾋﾟｰ", "ｼﾞｮｳﾔ", "ｶｯﾁｮｳ",
         "ｶﾞｷｮｳ", "ﾊﾟﾋﾟｰ",
         "今日", "板矧ぎ", "IEC規格", "！？…"]

for t in CASES:
    n = vp.normalize_text(t)
    k = vp.kanaize(t)
    print("%-12s -> normalize %-14s -> kanaize %-14s (звуковых знаков: %d)"
          % (t, n, k, vp._qc_v2_module().sound_chars(k)))
