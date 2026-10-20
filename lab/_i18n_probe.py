# -*- coding: utf-8 -*-
"""Разбор: какие видимые тексты страницы не переведены."""
import io
import os
import re
import sys
from html.parser import HTMLParser

ROOT = os.environ["AV_ROOT"]
sys.path.insert(0, ROOT)
from i18n_en import I18N_EN

src = io.open(os.path.join(ROOT, "anki_web_page.py"), encoding="utf-8").read()
i = src.index('HTML = r"""') + len('HTML = r"""')
j = src.index('"""', i)
html = src[i:j]
script = ""
sparts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)
for sp in sparts:
    script += sp + "\n"

CYR = re.compile(r"[А-Яа-яЁё]")


class T(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.skip = 0
        self.texts = []

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
        if t and CYR.search(t):
            self.texts.append(t)


p = T()
p.feed(html)
print("== видимые тексты HTML: %d (с кириллицей) ==" % len(p.texts))
missing = []
for t in p.texts:
    if t not in I18N_EN:
        missing.append(t)
print("нет в словаре: %d" % len(missing))
for t in missing:
    print("   -", t[:120])

# ключи словаря, которых нет в исходнике
stale = [k for k in I18N_EN if k not in html]
print("\n== ключи словаря без соответствия в странице: %d ==" % len(stale))
for k in stale:
    print("   -", k[:120])

# динамические строки в JS
lits = re.findall(r'"((?:[^"\\]|\\.)*)"', script) + re.findall(r"'((?:[^'\\]|\\.)*)'", script)
dyn = sorted(set(x for x in lits if CYR.search(x) and len(x) > 3))
print("\n== строк с кириллицей в JS: %d ==" % len(dyn))
nodict = [x for x in dyn if x not in I18N_EN]
print("нет в словаре: %d" % len(nodict))
for x in nodict:
    print("   -", x[:120])
