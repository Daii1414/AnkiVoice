# -*- coding: utf-8 -*-
"""Сервис IndexTTS: ускоряющие правки движка (шаги диффузии + fp16).

На слабых картах (GTX 16xx/20xx, без bf16) IndexTTS 2.5 считает почти всё
в fp32 и с 25 шагами диффузии: фраза звучит 3-4 минуты. Две правки дают
x6-x8: 12 шагов вместо 25 и fp16 вместо fp32.

Правка идемпотентна и делается на лету; исходник сохраняется рядом
(infer_v2_5.py.orig), поэтому её легко откатить.
"""
import io
import os
import shutil


def apply_speedups(index_root):
    """Патчим установленный IndexTTS. Возвращает список сделанного."""
    if not index_root:
        return []
    p = os.path.join(index_root, "indextts", "infer_v2_5.py")
    if not os.path.isfile(p):
        return []
    try:
        src = io.open(p, encoding="utf-8").read()
    except Exception:
        return []
    bak = p + ".orig"
    if not os.path.exists(bak):
        try:
            shutil.copy2(p, bak)
        except OSError:
            pass
    out = src
    done = []
    if "diffusion_steps = 25" in out:
        out = out.replace("diffusion_steps = 25", "diffusion_steps = 12", 1)
        done.append("шагов диффузии 25 -> 12")
    if "                dtype = None\n" in out:
        out = out.replace("                dtype = None\n",
                          "                dtype = torch.float16\n", 1)
        done.append("fp16 вместо fp32")
    if out != src:
        try:
            io.open(p, "w", encoding="utf-8", newline="").write(out)
        except Exception as e:
            return ["не удалось записать: %r" % e]
    return done
