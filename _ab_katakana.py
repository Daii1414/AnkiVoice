# -*- coding: utf-8 -*-
"""A/B: режим «Авто» (фуригана) против «только кандзи» на катаканных карточках.

Меряем покрытие/CER распознавания (нормализованное: кана и катакана — одно)
и длительность. Голос тот же, что у пользователя.
"""
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
OUT = os.path.join(os.environ["TEMP"], "av_ab")
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

# берём карточки, где в чтении термина есть транслитерация/точка/цифры
def hard(furi):
    r = re.sub(r"^.*\[|\]$", "", furi)
    return bool(re.search(r"[0-9A-Za-z]|[ぁぃぅぇぉゃゅょァィゥェォャュョ]", r))


picked = []
for n in notes:
    f = n.get("fields") or {}
    furi = (f.get("ExpressionFurigana") or {}).get("value", "")
    sent = (f.get("Sentence") or {}).get("value", "")
    if not furi or "[" not in furi:
        continue
    picked.append({"id": n["noteId"], "sent": sent,
                   "expr": (f.get("Expression") or {}).get("value", ""),
                   "furi": furi})
hardcards = [p for p in picked if hard(p["furi"])]
easy = [p for p in picked if not hard(p["furi"])]
sel = hardcards[:6] + easy[:3]
print("карточек: сложных %d, простых %d; беру %d"
      % (len(hardcards), len(easy), len(sel)))

voice = vp.get_voice("narrator")
fields = {"sentence_src": "Sentence", "sentence_audio": "SentenceAudio",
          "word_src": "Expression", "word_audio": "ExpressionAudio",
          "furigana_src": "ExpressionFurigana", "reading": ""}

checker = vp._pron_verifier(force=True)
if checker is None:
    raise SystemExit("нет ASR: " + str(vp._pron_verifier(force=False)))

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
        blob, ext, _ = vp.synth(voice, text, seed=42, speed=1.0)
        dt = time.time() - t0
        pth = os.path.join(OUT, "%d_%s.%s" % (p["id"], mode, ext))
        with open(pth, "wb") as f2:
            f2.write(blob)
        res = checker.check(blob, ext, text)
        rows.append({"id": p["id"], "expr": p["expr"], "mode": mode,
                     "text": text, "cov": res.get("coverage"),
                     "cer": res.get("cer"), "heard": res.get("heard", ""),
                     "dur": round(dt, 1)})
        print("\n[%d] %s  режим=%s  %.1f c" % (p["id"], p["expr"], mode, dt))
        print("   текст:  %s" % text)
        print("   услышали: %s" % res.get("heard", ""))
        print("   покрытие %.2f  ошибка %.2f" % (res.get("coverage") or 0,
                                                res.get("cer") or 0))
    rows_sum = [r for r in rows if r["id"] == p["id"]]
    if len(rows_sum) == 2:
        a, b = rows_sum
        print("   >>> mix %.2f против asis %.2f  %s"
              % (a["cov"] or 0, b["cov"] or 0,
                 "mix лучше" if (a["cov"] or 0) > (b["cov"] or 0) else
                 ("asis лучше" if (b["cov"] or 0) > (a["cov"] or 0) else "ровно")))

out = os.path.join(OUT, "result.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
print("\nитог: %s" % out)
