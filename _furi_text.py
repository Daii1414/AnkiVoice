# -*- coding: utf-8 -*-
"""Текст, который уходит в синтез, для карточек с чтением."""
import json
import os
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
    return out.get("result")


ids = ac("findNotes", query='deck:"%s"' % DECK)
notes = ac("notesInfo", notes=ids)
fields = {"sentence_src": "Sentence", "sentence_audio": "SentenceAudio",
          "word_src": "Expression", "word_audio": "ExpressionAudio",
          "furigana_src": "ExpressionFurigana", "reading": "mix"}
for n in notes:
    f = n.get("fields") or {}
    expr = (f.get("Expression") or {}).get("value", "")
    if expr not in ("ビュー審査", "デジタル審査", "データ連携のオートメーション化",
                    "点群データ", "施工のオートメーション化", "遠隔監督・検査",
                    "3D都市モデル"):
        continue
    sent = (f.get("Sentence") or {}).get("value", "")
    furi = (f.get("ExpressionFurigana") or {}).get("value", "")
    note = {"noteId": n["noteId"], "fields": {
        "Sentence": {"value": sent}, "Expression": {"value": expr},
        "ExpressionFurigana": {"value": furi}}}
    jobs = vp.build_jobs([note], "sentence", True, fields=fields)
    print("\n=== %s" % expr)
    print("  фуригана: %s" % furi)
    print("  в карточке: %s" % sent)
    print("  на синтез:  %s" % (jobs[0][2] if jobs else "—"))
    if "[" in furi:
        print("  разбор:    %r" % (vp.furiga_pair(furi),))
