# -*- coding: utf-8 -*-
"""Перенести забытый скрипт в репозиторий и применить правки макетов."""
import io
import os
import shutil
import glob

root = os.environ["AV_ROOT"]

# 1. найти забытый файл в других каталогах E:\TTS*
stray = None
for d in glob.glob("E:\\TTS*"):
    if os.path.isdir(d) and os.path.abspath(d) != os.path.abspath(root):
        p = os.path.join(d, "qa", "apply_best2.py")
        if os.path.isfile(p):
            stray = p
            break
if stray:
    shutil.copyfile(stray, os.path.join(root, "qa", "apply_best2.py"))
    shutil.rmtree(os.path.dirname(stray), ignore_errors=True)
    # убрать и пустой E:\TTS-папку, если она осталась
    parent = os.path.dirname(os.path.dirname(stray))
    try:
        if not os.listdir(parent):
            os.rmdir(parent)
    except OSError:
        pass
    print("  ok: скрипт перенесён из", stray)
else:
    print("  ! забытый скрипт не найден")

# 2. применить правки
code = io.open(os.path.join(root, "qa", "apply_best2.py"), encoding="utf-8").read()
exec(compile(code, "apply_best2.py", "exec"))
