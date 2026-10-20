# -*- coding: utf-8 -*-
"""Сколько карточек в основной колоде страдало от удвоения чтения."""
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import voice_pipeline as vp  # noqa: E402

URL = "http://127.0.0.1:8765"
DECK = "Архитектура"


def ac(action, **params):
    body = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    req = urllib.request.Request(URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        out = json.loads(r.read().decode("utf-8"))
    if out.get("error"):
        raise SystemExit("AnkiConnect: %s" % out["error"])
    return out.get("result")


def old_furiga_pair(text):
    """Старый разбор (до исправления) — для сравнения."""
    if "[" not in text:
        return None, None
    parts = re.split(r"\[([^\[\]]*)\]", text)
    last = len(parts) - 1
    surf, read = [], []
    i = 0
    while i < len(parts):
        if i % 2 == 1:
            i += 1
            continue
        if i == last:
            surf.append(parts[i])
            read.append(parts[i])
        else:
            surf.append(parts[i])
            read.append(vp._base_reading(parts[i], parts[i + 1]))
            i += 1
        i += 1
    return "".join(surf), "".join(read).replace("\u30fb", "")


ids = ac("findNotes", query='deck:"%s"' % DECK)
print("карточек в основной колоде: %d" % len(ids))
sample = ids[:400]
notes = ac("notesInfo", notes=sample)
bad = 0
shown = 0
for n in notes:
    f = n.get("fields") or {}
    furi = (f.get("ExpressionFurigana") or {}).get("value", "")
    if "[" not in furi:
        continue
    o = old_furiga_pair(furi)
    nw = vp.furiga_pair(furi)
    if o == nw:
        continue
    bad += 1
    if shown < 12:
        shown += 1
        print("  %-28s было %r -> стало %r" % ((f.get("Expression") or {}).get("value", "")[:28],
                                                o[1], nw[1]))
print("\nразбор изменился у %d карточек из %d проверенных" % (bad, len(notes)))
print("оценка на всю колоду: ~%d" % int(bad * len(ids) / max(1, len(notes))))
