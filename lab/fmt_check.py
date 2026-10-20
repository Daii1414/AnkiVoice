# -*- coding: utf-8 -*-
"""Проверка формат-строк: сколько плейсхолдеров в строке — столько аргументов.

Ловит класс ошибок «not all arguments converted during string formatting»:
один %s и два аргумента (или наоборот) — такая строка падает только в момент
выполнения, часто в самом конце работы.

    python lab/fmt_check.py
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__", "pyruntime", ".venv", "dist", "build", "lab\\pylibs"}


def spec_count(fmt):
    """Сколько спецификаторов в строке формата (%% не считается)."""
    n = 0
    i = 0
    while i < len(fmt):
        if fmt[i] == "%":
            if i + 1 < len(fmt) and fmt[i + 1] == "%":
                i += 2
                continue
            # %s %d %f %.2f %-10s %(name)s
            j = i + 1
            while j < len(fmt) and fmt[j] in "-+ #0123456789.":
                j += 1
            if j < len(fmt) and fmt[j] in "sdfgexr":
                n += 1
            i = j + 1
            continue
        i += 1
    return n


def arg_count(node):
    if isinstance(node, ast.Tuple):
        return len(node.elts)
    return 1


def check_file(path):
    problems = []
    try:
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src, path)
    except Exception:
        return problems
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = ""
        if isinstance(f, ast.Name):
            name = f.id
        elif isinstance(f, ast.Attribute):
            name = f.attr
        if name not in ("print", "warn", "info", "error"):
            continue
        for arg in node.args:
            if not isinstance(arg, ast.BinOp) or not isinstance(arg.op, ast.Mod):
                continue
            left = arg.left
            if not (isinstance(left, ast.Constant) and isinstance(left.value, str)):
                continue
            want = spec_count(left.value)
            have = arg_count(arg.right)
            if want != have:
                problems.append("%s:%d  «%s» — плейсхолдеров %d, аргументов %d"
                                % (os.path.relpath(path, ROOT), node.lineno,
                                   left.value[:70], want, have))
    return problems


def main():
    problems = []
    checked = 0
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(base, fn)
            checked += 1
            problems += check_file(path)
    print("проверено файлов: %d" % checked)
    if problems:
        print("расхождений: %d" % len(problems))
        for p in problems:
            print("  " + p)
        return 1
    print("расхождений нет")
    return 0


if __name__ == "__main__":
    sys.exit(main())
