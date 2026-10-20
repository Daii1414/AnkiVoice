# -*- coding: utf-8 -*-
"""Разбор фуриганы на всех карточках колоды: где чтение задваивается."""
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import voice_pipeline as vp  # noqa: E402

DECK = "Архитектура::BIM и цифровое проектирование::Новое в цифровом строительстве"
URL = "http://127.0.0.1:8765"


def ac(action, **params):
    body = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    req = urllib.request.Request(URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read().decode("utf-8"))
    if out.get("error"):
        raise SystemExit("AnkiConnect: %s" % out["error"])
    return out.get("result")


ids = ac("findNotes", query='deck:"%s"' % DECK)
notes = ac("notesInfo", notes=ids)
fields = {"sentence_src": "Sentence", "sentence_audio": "SentenceAudio",
          "word_src": "Expression", "word_audio": "ExpressionAudio",
          "furigana_src": "ExpressionFurigana", "reading": "mix"}
bad = 0
for n in notes:
    f = n.get("fields") or {}
    sent = (f.get("Sentence") or {}).get("value", "")
    expr = (f.get("Expression") or {}).get("value", "")
    furi = (f.get("ExpressionFurigana") or {}).get("value", "")
    if not furi:
        continue
    note = {"noteId": n["noteId"], "fields": {
        "Sentence": {"value": sent}, "Expression": {"value": expr},
        "ExpressionFurigana": {"value": furi}}}
    jobs = vp.build_jobs([note], "sentence", True, fields=fields)
    text = jobs[0][2] if jobs else ""
    surf, read = vp.furiga_pair(furi) if "[" in furi else (None, None)
    # задвоение: основа повторяется в чтении
    dup = ""
    if surf and read:
        base = surf
        for i in range(len(base)):
            if base[i] not in "\u3040-\u30ff":
                continue
        # простая эвристика: кусок основы длиной>=2 есть и в начале чтения
        for k in range(len(base), 1, -1):
            frag = base[:k]
            if frag in read and len(frag) >= 2:
                dup = frag
                break
    flag = "ЗАДВОЕНО" if dup else ("ок" if text != sent else "без подстановки")
    if dup:
        bad += 1
    print("%-34s %-12s %s" % (expr[:34], flag,
                               ("дубль: %r -> %r" % (dup, read[:40])) if dup else ""))
print("\nзадвоений: %d из %d" % (bad, len(notes)))
