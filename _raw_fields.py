# -*- coding: utf-8 -*-
"""Точные поля карточек с катаканными терминами."""
import json
import os
import sys
import urllib.request

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
for n in notes:
    f = n.get("fields") or {}
    print("--- %s" % n["noteId"])
    for k in ("Sentence", "Expression", "ExpressionFurigana"):
        v = (f.get(k) or {}).get("value")
        if v is not None:
            print("   %-18s %r" % (k, v))
