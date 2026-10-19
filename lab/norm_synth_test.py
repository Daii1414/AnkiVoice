"""Проверка гипотезы: проваливается ли синтез на НОРМАЛИЗОВАННОМ тексте?

Бенч подавал в synth() сырую полукатакану (ｶﾞｷｮｳ), минуя kanaize. В
реальном пайплайне текст всегда идёт через kanaize -> がきょう. Если на
нормализованном виде синтез проходит, то «неспасающиеся» тексты — артефакт
стенда, а не проблемы пайплайна.
"""
from __future__ import annotations

import contextlib
import io
import os
import sys

sys.path.insert(0, r"E:\TTS-проект")
sys.path.insert(0, r"E:\TTS-проект\lab")
os.chdir(r"E:\TTS-проект")
import voice_pipeline as vp  # noqa: E402
from quality_v2 import analyze, verdict, ffmpeg_exe  # noqa: E402

FF = ffmpeg_exe(vp.ENGINE)
v = vp.get_voice("narrator")
vp.ensure_voice(v)

RAW = ["ｶﾞｷｮｳ", "ﾊﾟﾋﾟｰ", "ｼﾞｮｳﾔ", "ｶｯﾁｮｳ"]

print("=== как в бенче: СЫРОЙ текст (минуя kanaize) ===")
for t in RAW:
    buf, err = io.StringIO(), None
    with contextlib.redirect_stdout(buf):
        try:
            blob, ext = vp.synth(v, t)
        except SystemExit as e:
            err, blob = str(e), None
    log = buf.getvalue()
    if err:
        print("  FAIL %-10s %s" % (t, err[:52]))
    else:
        m = analyze(blob, FF)
        print("  ok   %-10s %5.1f с речь %4.1f (повторов: %d)"
              % (t, m["dur"], m["sounding"], log.count("брак:")))

print("\n=== как в реальном пайплайне: через kanaize ===")
for t in RAW:
    k = vp.kanaize(t)
    buf, err = io.StringIO(), None
    with contextlib.redirect_stdout(buf):
        try:
            blob, ext = vp.synth(v, k)
        except SystemExit as e:
            err, blob = str(e), None
    log = buf.getvalue()
    if err:
        print("  FAIL %-10s -> %-8s %s" % (t, k, err[:44]))
    else:
        m = analyze(blob, FF)
        print("  ok   %-10s -> %-8s %5.1f с речь %4.1f (повторов: %d)"
              % (t, k, m["dur"], m["sounding"], log.count("брак:")))
