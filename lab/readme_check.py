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

# Документы, между которыми сверяется страница. README — витрина, остальное
# вынесено в doc/ и CONTRIBUTING: проверка идёт по всем сразу, иначе ссылка
# из README на документ (или наоборот) может остаться мёртвой.
DOCS = [
    "README.md", "README.en.md",
    "CONTRIBUTING.md", "CONTRIBUTING.en.md",
    "doc/reading.md", "doc/reading.en.md",
    "doc/fields.md", "doc/fields.en.md",
    "doc/cli.md", "doc/cli.en.md",
    "doc/engines.md", "doc/engines.en.md",
]


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
    docs = [(read(p), p) for p in DOCS]

    # ---- 1. файлы, упомянутые в таблице структуры ----
    for doc, name in docs:
        for m in re.finditer(r"^\|\s*`([^`]+)`", doc, re.M):
            rel = m.group(1).strip()
            if rel in (".github", "lab"):
                continue
            if rel == "AnkiVoice.exe":
                # собирается скриптом, в репозитории его нет
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

    # ---- 2. картинки из всех документов ----
    for doc, name in docs:
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

    for doc, name in docs:
        have = anchors(doc)
        for m in re.finditer(r"^\- \[[^\]]+\]\(#([^)]+)\)", doc, re.M):
            a = m.group(1).strip()
            if a not in have:
                fail("%s: якорь #%s в оглавлении не найден среди заголовков" % (name, a))
            else:
                ok("%s: якорь #%s есть" % (name, a))

    # ---- 3a. все внутренние ссылки (не только оглавление) ведут куда-то ----
    # Раньше проверялись только ссылки из оглавления, поэтому мёртвая ссылка
    # в шапке или в таблице проходила CI молча.
    for doc, name in docs:
        have = anchors(doc)
        for m in re.finditer(r"\]\(#([^)]+)\)", doc):
            a = m.group(1).strip()
            if a and a not in have:
                fail("%s: ссылка #%s не ведёт ни на один заголовок" % (name, a))
            else:
                ok("%s: ссылка #%s есть" % (name, a))

    # ---- 3a2. HTML-якоря (<a href="#...">) тоже ведут на заголовки ----
    for doc, name in docs:
        have = anchors(doc)
        for m in re.finditer(r'<a href="#([^"]+)"', doc):
            a = m.group(1).strip()
            if a and a not in have:
                fail("%s: ссылка #%s не ведёт ни на один заголовок" % (name, a))
            else:
                ok("%s: ссылка #%s есть" % (name, a))

    # ---- 3b. ссылки на файлы (не якоря) ведут в существующие файлы ----
    for doc, name in docs:
        base = os.path.dirname(os.path.join(ROOT, name))
        for m in re.finditer(r"\]\(([^)#][^)]*)\)", doc):
            rel = m.group(1).strip()
            if rel.startswith("http") or rel.startswith("mailto"):
                continue
            target = os.path.normpath(os.path.join(base, rel))
            if not os.path.exists(target):
                fail("%s: ссылка на несуществующий файл %s" % (name, rel))
            else:
                ok("%s: файл %s есть" % (name, rel))

    # ---- 4. команды консоли существуют ----
    pipeline = read("app/voice_pipeline.py")
    cmds = set(re.findall(r'add_parser\("([^"]+)"', pipeline))
    gui = read("app/anki_gui.py")
    gui_cmds = set(re.findall(r'add_parser\("([^"]+)"', gui))
    for doc, name in docs:
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
    all_text = "\n".join(d for d, _ in docs)
    claimed = set(re.findall(r"10 \u043c\u043e\u0434\u0443\u043b\u0435\u0439", all_text))
    if len(shipped) != 10:
        fail("установщик везёт %d модулей lab/, а README говорит о 10: %s"
             % (len(shipped), ", ".join(sorted(shipped))))
    else:
        ok("установщик везёт 10 модулей lab/ (%s)" % ", ".join(sorted(shipped)))
    if not claimed:
        fail("в README нет упоминания про 10 модулей установщика")

    # ---- 7. режимы чтения: авто (по полю с фуриганой) и только кандзи ----
    page = read("app/anki_web_page.py")
    if '<option value="">' not in page:
        fail("в интерфейсе нет режима «авто» (пустое значение)")
    else:
        ok("в интерфейсе есть режим «авто»")
    if '<option value="asis">' not in page:
        fail("в интерфейсе нет режима «только кандзи» (asis)")
    else:
        ok("в интерфейсе есть режим «только кандзи»")
    pipe = read("app/voice_pipeline.py")
    if "def reading_mode(" not in pipe:
        fail("в voice_pipeline.py нет reading_mode() — режим не выбирается по карточке")
    else:
        ok("режим выбирается по карточке (reading_mode)")
    for token in ("авто", "asis", "--reading"):
        if token not in ru and token not in all_text:
            fail("в README.md нет упоминания: %s" % token)
        else:
            ok("в README.md описано: %s" % token)
    if "auto" not in en.lower() and "auto" not in all_text.lower():
        fail("в README.en.md не описан автоматический режим")
    else:
        ok("в README.en.md описан автоматический режим")

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
