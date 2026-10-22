# -*- coding: utf-8 -*-
"""Найти смешение алфавитов: японские знаки рядом с кириллицей."""
import io
import os
import re

ROOT = os.environ["AV_ROOT"]
CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
CYR = re.compile(r"[\u0400-\u04ff]")
HAN = re.compile(r"[\u4e00-\u9fff]")


def suspicious(line):
    # токен из японских знаков, в котором есть кириллица
    for tok in re.findall(r"[\w\u3040-\u30ff\u3400-\u9fff\[\]]+", line):
        if CJK.search(tok) and CYR.search(tok):
            return tok
    return None


for base, dirs, files in os.walk(ROOT):
    dirs[:] = [d for d in dirs
               if d not in (".git", "pyruntime", "dist", "build", "__pycache__",
                            ".venv", "venv", "голоса")]
    for name in files:
        if not name.endswith(".md"):
            continue
        p = os.path.join(base, name)
        rel = os.path.relpath(p, ROOT)
        try:
            lines = io.open(p, encoding="utf-8").read().split("\n")
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            tok = suspicious(line)
            if tok:
                bad = "".join(ch for ch in tok if CYR.match(ch))
                print("  %s:%d  %s   (кириллица: %s)" % (rel, i, tok, bad))
