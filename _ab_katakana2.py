# -*- coding: utf-8 -*-
"""A/B «Авто» против «только кандзи»: катаканные и кандзи-термины."""
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.environ.setdefault("GPT_SOVITS_ROOT", r"D:\DOWNLOAD\GPT-SoVITS-v2pro-20250604")

import voice_pipeline as vp  # noqa: E402

DECK = "Архитектура::BIM и цифровое проектирование::Новое в цифровом строительстве"
URL = "http://127.0.0.1:8765"
OUT = os.path.join(os.environ["TEMP"], "av_ab2")
os.makedirs(OUT, exist_ok=True)
RES = os.path.join(OUT, "result.json")


def ac(action, **params):
    body = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    req = urllib.request.Request(URL, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.loads(r.read().decode("utf-8"))
    if out.get("error"):
        raise SystemExit("AnkiConnect: %s" % out["error"])
    return out.get("result")


def save(rows):
    with open(RES, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


ids = ac("findNotes", query='deck:"%s"' % DECK)
notes = ac("notesInfo", notes=ids)
items = []
for n in notes:
    f = n.get("fields") or {}
    furi = (f.get("ExpressionFurigana") or {}).get("value", "")
    sent = (f.get("Sentence") or {}).get("value", "")
    expr = (f.get("Expression") or {}).get("value", "")
    if not furi or "[" not in furi:
        continue
    surf = furi.split("[", 1)[0]
    kind = ("latin" if re.search(r"[0-9A-Za-z]", surf) else
            "katakana" if re.search(r"[\u30a1-\u30f6]", surf) else "kanji")
    items.append({"id": n["noteId"], "sent": sent, "expr": expr,
                  "furi": furi, "kind": kind})
print("всего: %d (%s)" % (len(items), ", ".join(
    "%s=%d" % (k, sum(1 for x in items if x["kind"] == k))
    for k in ("kanji", "katakana", "latin"))))

# по две карточки каждого вида
sel = []
for kind in ("kanji", "katakana", "latin"):
    sel += [x for x in items if x["kind"] == kind][:2]
print("беру:", ", ".join("%s(%s)" % (x["expr"], x["kind"]) for x in sel))

voice = vp.get_voice("narrator")
fields = {"sentence_src": "Sentence", "sentence_audio": "SentenceAudio",
          "word_src": "Expression", "word_audio": "ExpressionAudio",
          "furigana_src": "ExpressionFurigana", "reading": ""}
checker = vp._pron_verifier(force=True)
if checker is None:
    raise SystemExit("нет ASR")

rows = []
for p in sel:
    note = {"noteId": p["id"], "fields": {
        "Sentence": {"value": p["sent"]},
        "Expression": {"value": p["expr"]},
        "ExpressionFurigana": {"value": p["furi"]}}}
    for mode in ("mix", "asis"):
        f = dict(fields)
        f["reading"] = mode
        jobs = vp.build_jobs([note], "sentence", True, fields=f)
        if not jobs:
            continue
        text = jobs[0][2]
        t0 = time.time()
        try:
            blob, ext, _ = vp.synth(voice, text, seed=42, speed=1.0)
        except SystemExit as e:
            print("  синтез не удался:", e)
            continue
        dt = time.time() - t0
        pth = os.path.join(OUT, "%d_%s.%s" % (p["id"], mode, ext))
        with open(pth, "wb") as f2:
            f2.write(blob)
        res = checker.check(blob, ext, text)
        rows.append({"id": p["id"], "expr": p["expr"], "kind": p["kind"],
                     "mode": mode, "text": text, "cov": res.get("coverage"),
                     "cer": res.get("cer"), "heard": res.get("heard", ""),
                     "dur": round(dt, 1), "file": pth})
        save(rows)
        print("[%d] %-20s %-6s %5.1f c  покрытие %.2f  ошибка %.2f"
              % (p["id"], p["expr"], mode, dt, res.get("coverage") or 0,
                 res.get("cer") or 0))
        print("     %s" % res.get("heard", ""))
    d = {r["mode"]: r for r in rows if r["id"] == p["id"]}
    if len(d) == 2:
        a, b = d["mix"], d["asis"]
        print("   >>> mix %.2f (%s c) / asis %.2f (%s c) — %s"
              % (a["cov"] or 0, a["dur"], b["cov"] or 0, b["dur"],
                 "mix" if (a["cov"] or 0) > (b["cov"] or 0) else
                 ("asis" if (b["cov"] or 0) > (a["cov"] or 0) else "ровно")))
print("\nготово: %s" % RES)
