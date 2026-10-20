# -*- coding: utf-8 -*-
"""Что реально лежит в карточках и что говорит модель."""
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
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.loads(r.read().decode("utf-8"))
    if out.get("error"):
        raise SystemExit("AnkiConnect: %s" % out["error"])
    return out.get("result")


ids = ac("findNotes", query='deck:"%s"' % DECK)
print("карточек в колоде: %d" % len(ids))

notes = ac("notesInfo", notes=ids[:40])
for n in notes[:6]:
    print("=== noteId %s ===" % n["noteId"])
    for name in ("Sentence", "Expression", "ExpressionFurigana",
                 "SentenceAudio", "ExpressionAudio"):
        v = (n.get("fields") or {}).get(name, {}).get("value")
        if v:
            print("  %-18s = %s" % (name, v.replace("\n", " | ")[:150]))

# сколько карточек уже озвучено
done = 0
withaudio = 0
for n in notes:
    v = (n.get("fields") or {}).get("SentenceAudio", {}).get("value") or ""
    if "[sound:" in v:
        withaudio += 1
print("из первых %d карточек озвучено: %d" % (len(notes), withaudio))
