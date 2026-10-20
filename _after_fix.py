# -*- coding: utf-8 -*-
"""Проверка после исправлений: те же карточки, что жаловались."""
import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.environ.setdefault("GPT_SOVITS_ROOT", r"D:\DOWNLOAD\GPT-SoVITS-v2pro-20250604")

import voice_pipeline as vp  # noqa: E402

DECK = "Архитектура::BIM и цифровое проектирование::Новое в цифровом строительстве"
URL = "http://127.0.0.1:8765"
OUT = os.path.join(os.environ["TEMP"], "av_after")
os.makedirs(OUT, exist_ok=True)


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
          "furigana_src": "ExpressionFurigana", "reading": ""}
checker = vp._pron_verifier(force=True)
if checker is None:
    raise SystemExit("нет ASR")
voice = vp.get_voice("narrator")

WATCH = ("点群データ", "ビュー審査", "デジタル審査", "施工のオートメーション化",
         "データ連携のオートメーション化", "3D都市モデル", "PLATEAU",
         "i-Construction 2.0", "BIM/CIM", "TIN", "デジタルツイン")
rows = []
for n in notes:
    f = n.get("fields") or {}
    expr = (f.get("Expression") or {}).get("value", "")
    if expr not in WATCH:
        continue
    sent = (f.get("Sentence") or {}).get("value", "")
    furi = (f.get("ExpressionFurigana") or {}).get("value", "")
    note = {"noteId": n["noteId"], "fields": {
        "Sentence": {"value": sent}, "Expression": {"value": expr},
        "ExpressionFurigana": {"value": furi}}}
    jobs = vp.build_jobs([note], "sentence", True, fields=fields)
    text = jobs[0][2] if jobs else ""
    t0 = time.time()
    try:
        blob, ext, _ = vp.synth(voice, text, seed=42, speed=1.0)
    except SystemExit as e:
        print("  синтез не удался: %s" % e)
        continue
    dt = time.time() - t0
    pth = os.path.join(OUT, "%d.%s" % (n["noteId"], ext))
    with open(pth, "wb") as f2:
        f2.write(blob)
    res = checker.check(blob, ext, text)
    rows.append({"id": n["noteId"], "expr": expr, "text": text,
                 "cov": res.get("coverage"), "cer": res.get("cer"),
                 "heard": res.get("heard", ""), "dur": round(dt, 1),
                 "file": pth})
    with open(os.path.join(OUT, "result.json"), "w", encoding="utf-8") as f2:
        json.dump(rows, f2, ensure_ascii=False, indent=1)
    print("%-24s %5.1f c  покрытие %.2f  ошибка %.2f" % (expr, dt,
          res.get("coverage") or 0, res.get("cer") or 0))
    print("   текст: %s" % text)
    print("   услышали: %s" % res.get("heard", ""))
print("\nготово")
