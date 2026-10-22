# -*- coding: utf-8 -*-
"""Обновить оглавление под новые рубрики."""
import io
import os
import re

ROOT = os.environ["AV_ROOT"]


def fix(path, pairs, add_after=None, add_block=None):
    p = os.path.join(ROOT, path)
    s = io.open(p, encoding="utf-8").read()
    for a, b in pairs:
        if a not in s:
            print("  ! нет:", path, a[:60])
            continue
        s = s.replace(a, b, 1)
        print("  ok", path, ":", a[:48])
    if add_after and add_block and add_block not in s:
        if add_after in s:
            s = s.replace(add_after, add_after + "\n" + add_block, 1)
            print("  ok", path, ": добавлен пункт", add_block[:44])
        else:
            print("  ! якорь для вставки не найден:", path, add_after[:50])
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)


fix("README.md",
    [("- [Требования](#требования)", "- [Что нужно до установки](#что-нужно-до-установки)")],
    add_after="- [Если что-то не работает](#если-что-то-не-работает)",
    add_block="- [Что перезаписывается, что уходит в сеть](#что-перезаписывается-что-уходит-в-сеть)")

fix("README.en.md",
    [("- [Requirements](#requirements)", "- [What you need before installing](#what-you-need-before-installing)")],
    add_after="- [Troubleshooting](#troubleshooting)",
    add_block="- [What gets overwritten, what goes over the network](#what-gets-overwritten-what-goes-over-the-network)")
print("готово")
