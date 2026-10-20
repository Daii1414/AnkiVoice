# -*- coding: utf-8 -*-
"""README против кода: ссылки, файлы, команды, картинки, якоря.

Запускается в CI: если README разошёлся с репозиторием — падает.

    python lab/readme_check.py
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILURES = []
CHECKED = [0]


def fail(msg):
    FAILURES.append(msg)


def ok(msg):
    CHECKED[0] += 1
    print("OK   " + msg)


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def main():
    ru = read("README.md")
    en = read("README.en.md")

    # ---- 1. файлы, упомянутые в таблице структуры ----
    for doc, name in ((ru, "README.md"), (en, "README.en.md")):
        for m in re.finditer(r"^\|\s*`([^`]+)`", doc, re.M):
            rel = m.group(1).strip()
            if rel in (".github", "lab"):
                continue
            if rel.startswith("lab/"):
                target = os.path.join(ROOT, rel)
                if not os.path.exists(target):
                    fail("%s: нет файла %s" % (name, rel))
                else:
                    ok("%s: файл %s есть" % (name, rel))
            elif "/" in rel or rel.endswith((".py", ".md", ".iss", ".json", ".zip", ".bat", ".exe", ".svg", ".png")):
                target = os.path.join(ROOT, rel)
                if not os.path.exists(target):
                    fail("%s: нет файла %s" % (name, rel))
                else:
                    ok("%s: файл %s есть" % (name, rel))

    # ---- 2. картинки из README ----
    for doc, name in ((ru, "README.md"), (en, "README.en.md")):
        for m in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", doc):
            rel = m.group(1).strip()
            if rel.startswith("http"):
                continue
            if not os.path.exists(os.path.join(ROOT, rel)):
                fail("%s: нет картинки %s" % (name, rel))
            else:
                ok("%s: картинка %s есть" % (name, rel))

    # ---- 3. оглавление: якоря совпадают с заголовками ----
    def anchors(doc):
        out = set()
        for m in re.finditer(r"^#{2,6}\s+(.+)$", doc, re.M):
            t = m.group(1).strip().lower()
            t = re.sub(r"[`*]", "", t)
            t = re.sub(r"[^\w\s-]", "", t, flags=re.U)
            out.add(re.sub(r"\s+", "-", t))
        return out

    for doc, name in ((ru, "README.md"), (en, "README.en.md")):
        have = anchors(doc)
        for m in re.finditer(r"^\- \[[^\]]+\]\(#([^)]+)\)", doc, re.M):
            a = m.group(1).strip()
            if a not in have:
                fail("%s: якорь #%s в оглавлении не найден среди заголовков" % (name, a))
            else:
                ok("%s: якорь #%s есть" % (name, a))

    # ---- 4. команды консоли существуют ----
    pipeline = read("voice_pipeline.py")
    cmds = set(re.findall(r'add_parser\("([^"]+)"', pipeline))
    gui = read("anki_gui.py")
    gui_cmds = set(re.findall(r'add_parser\("([^"]+)"', gui))
    for doc, name in ((ru, "README.md"), (en, "README.en.md")):
        for m in re.finditer(r"pipeline\.bat\s+([a-z][a-z-]+)", doc):
            c = m.group(1)
            if c not in cmds:
                fail("%s: команда pipeline.bat %s не существует" % (name, c))
            else:
                ok("%s: команда %s есть" % (name, c))
        for m in re.finditer(r"AnkiVoice\.exe\s+([a-z][a-z-]+)", doc):
            c = m.group(1)
            if c not in gui_cmds:
                fail("%s: команда AnkiVoice.exe %s не существует" % (name, c))
            else:
                ok("%s: команда exe %s есть" % (name, c))

    # ---- 5. обе версии README описывают одни и те же разделы ----
    ru_heads = re.findall(r"^##\s+(.+)$", ru, re.M)
    en_heads = re.findall(r"^##\s+(.+)$", en, re.M)
    if len(ru_heads) != len(en_heads):
        fail("разделов в README.md — %d, в README.en.md — %d" % (len(ru_heads), len(en_heads)))
    else:
        ok("разделов в обоих README поровну (%d)" % len(ru_heads))

    # ---- 6. установщик везёт те же модули, что перечислены в README ----
    iss = read("AnkiVoice.iss")
    shipped = set(re.findall(r'Source:\s*"lab\\([^"]+)"', iss))
    claimed = set(re.findall(r"7 \u043c\u043e\u0434\u0443\u043b\u0435\u0439", ru))
    if len(shipped) != 7:
        fail("установщик везёт %d модулей lab/, а README говорит о 7: %s"
             % (len(shipped), ", ".join(sorted(shipped))))
    else:
        ok("установщик везёт 7 модулей lab/ (%s)" % ", ".join(sorted(shipped)))
    if not claimed:
        fail("в README нет упоминания про 7 модулей установщика")

    # ---- 7. режимов чтения ровно два, и оба описаны в README ----
    page = read("anki_web_page.py")
    modes = re.findall(r'<option value="(mix|asis)">', page)
    if sorted(set(modes)) != ["asis", "mix"]:
        fail("в интерфейсе ожидались режимы mix и asis, найдено: %s" % sorted(set(modes)))
    else:
        ok("в интерфейсе два режима чтения: mix и asis")
    for mode in ("mix", "asis"):
        if ("--reading %s" % mode) not in ru and mode not in ru:
            fail("режим %s не описан в README.md" % mode)
        else:
            ok("режим %s описан в README.md" % mode)

    # ---- 8. упоминания av_suspect в README не обещают метку, которой нет ----
    if "av_suspect" in ru:
        bad = re.search(r"av_suspect[^\n]{0,80}(помеча|метк)", ru)
        if bad:
            fail("README обещает метку av_suspect, а проверка её больше не ставит")
        else:
            ok("README не обещает метку av_suspect")

    print("\n\u043f\u0440\u043e\u0432\u0435\u0440\u043e\u043a: %d, \u043f\u0440\u043e\u0432\u0435\u0440\u043e\u043a: %d" % (CHECKED[0], len(FAILURES)))
    for f in FAILURES:
        print("  FAIL " + f)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
