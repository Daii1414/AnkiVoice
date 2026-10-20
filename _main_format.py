# -*- coding: utf-8 -*-
"""Формат фуриганы в основной колоде: разбор до и после."""
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import voice_pipeline as vp  # noqa: E402

URL = "http://127.0.0.1:8765"


def ac(action, **params):
    body = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    req = urllib.request.Request(URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        out = json.loads(r.read().decode("utf-8"))
    return out.get("result")


print("KANJI_RE =", vp.KANJI_RE.pattern)
for term in ("\u30a2\u30a4\u30b9\u30b9\u30b1\u30fc\u30c8\u5834", "\u70b9\u7fa4\u30c7\u30fc\u30bf",
              "\u30a2\u30a4\u30ea\u30f3\u30b0\u30fb\u30cc\u30fc\u30c8\u30bb\u30f3\u306e\u6b8b\u97ff\u5f0f"):
    print("%-20s kanji? %s rest=%r" % (term, bool(vp.KANJI_RE.search(term)),
                                        vp.KANJI_RE.sub("", term)))

ids = ac("findNotes", query='deck:"Архитектура"')
notes = ac("notesInfo", notes=ids[:60])
for n in notes[:12]:
    f = n.get("fields") or {}
    expr = (f.get("Expression") or {}).get("value", "")
    furi = (f.get("ExpressionFurigana") or {}).get("value", "")
    if "[" not in furi:
        continue
    print("\n%-26s фуригана=%r" % (expr[:26], furi))
    print("   разбор: %r" % (vp.furiga_pair(furi),))
