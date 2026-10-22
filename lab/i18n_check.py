# -*- coding: utf-8 -*-
"""Проверка английского интерфейса: видимые тексты переведены.

Переводчик в странице ищет точный текст узла в словаре (i18n_en.py).
Если текста в словаре нет — он остаётся по-русски, и в английском
интерфейсе это выглядит как ошибка. Здесь проверяется статичная разметка
страницы; тексты, которые собирает скрипт, ловит сам интерфейс: в
английском режиме он пишет в консоль всё, что осталось по-русски.

    python lab/i18n_check.py
"""
import io
import os
import re
import sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILURES = []
CHECKED = [0]

CYR = re.compile(r"[А-Яа-яЁё]")


def fail(msg):
    FAILURES.append(msg)


def ok(msg):
    CHECKED[0] += 1
    print("OK   " + msg)


def page_html():
    src = io.open(os.path.join(ROOT, "app", "anki_web_page.py"), encoding="utf-8").read()
    i = src.index('HTML = r"""') + len('HTML = r"""')
    j = src.index('"""', i)
    return src[i:j]


class Texts(HTMLParser):
    """Видимые текстовые узлы (внутри <script>/<style> — пропускаем)."""

    def __init__(self):
        HTMLParser.__init__(self)
        self.skip = 0
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if self.skip:
            return
        t = data.strip()
        if t:
            self.out.append(t)


def norm(s):
    """Та же нормализация, что в trText() страницы."""
    s = s.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", s).strip()


def translated(text, i18n, prefix_keys):
    """Повторяет логику trText(): точный ключ, нормализованный или по началу."""
    if text in i18n:
        return True
    if norm(text) in i18n:
        return True
    raw = text.replace("\u00a0", " ")
    for k in prefix_keys:
        if raw.startswith(k):
            return True
    return False


def main():
    sys.path.insert(0, ROOT)
    sys.path.insert(0, os.path.join(ROOT, "app"))
    from i18n_en import I18N_EN

    html = page_html()
    i18n = dict(I18N_EN)
    prefix_keys = sorted([k for k in i18n
                          if len(k) >= 6 and re.search(r"[\s:]$", k)],
                         key=len, reverse=True)

    # --- 1. видимые тексты статичной разметки ---
    p = Texts()
    p.feed(html)
    missing = []
    for t in p.out:
        if CYR.search(t) and not translated(t, i18n, prefix_keys):
            missing.append(t)
    if missing:
        for t in sorted(set(missing)):
            fail("нет перевода (разметка): %s"
                 % " ".join(t.split())[:110])
    else:
        ok("видимые тексты разметки переведены (%d шт.)" % len(p.out))

    # --- 2. пустые переводы ---
    empty = [k for k, v in i18n.items() if not (v or "").strip()]
    if empty:
        for k in empty:
            fail("пустой перевод: %s" % k[:110])
    else:
        ok("пустых переводов нет")

    print("\nпроверок: %d, замечаний: %d" % (CHECKED[0], len(FAILURES)))
    for f in FAILURES:
        print("  FAIL " + f)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
