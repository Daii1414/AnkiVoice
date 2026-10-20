# -*- coding: utf-8 -*-
"""Что реально сказано в озвучке: ASR по сохранённым файлам."""
import json
import os
import sys
import urllib.request

DECK = "Архитектура::BIM и цифровое проектирование::Новое в цифровом строительстве"
URL = "http://127.0.0.1:8765"
OUT = os.path.join(os.environ["TEMP"], "av_asr")
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

items = []
for n in notes:
    f = n.get("fields") or {}
    snd = (f.get("SentenceAudio") or {}).get("value") or ""
    if "[sound:" not in snd:
        continue
    fn = snd.split("[sound:", 1)[1].split("]", 1)[0]
    items.append({
        "id": n["noteId"],
        "sentence": (f.get("Sentence") or {}).get("value", ""),
        "expr": (f.get("Expression") or {}).get("value", ""),
        "furi": (f.get("ExpressionFurigana") or {}).get("value", ""),
        "file": fn,
    })
print("озвученных карточек: %d" % len(items))

media = {}
names = [it["file"] for it in items]
for nm in names:
    blob = ac("retrieveMediaFile", filename=nm)
    if blob:
        media[nm] = blob
print("скачано файлов: %d" % len(media))

for it in items:
    blob = media.get(it["file"])
    if not blob:
        continue
    if isinstance(blob, str):
        import base64
        blob = base64.b64decode(blob)
    p = os.path.join(OUT, it["file"])
    with open(p, "wb") as f:
        f.write(blob)

# ---- ASR ----
from faster_whisper import WhisperModel  # noqa: E402

model = WhisperModel("mobiuslabsgmbh/faster-whisper-large-v3-turbo", device="cuda",
                      compute_type="float16")
import re  # noqa: E402


def norm(s):
    s = re.sub(r"[\s、。,.!「」『』・:：]+", "", s)
    return s


print("\n=== что сказано ===")
for it in items:
    p = os.path.join(OUT, it["file"])
    if not os.path.isfile(p):
        continue
    segs, info = model.transcribe(p, language="ja", beam_size=5,
                                   condition_on_previous_text=False)
    heard = "".join(s.text for s in segs).strip()
    # ожидаем: предложение, где термин = чтение из фуриганы
    exp = it["sentence"]
    m = re.match(r"^(.*?)\[(.+?)\](.*)$", it["furi"])
    if m:
        exp = exp.replace(m.group(1), m.group(2))
    a, b = norm(exp), norm(heard)
    cov = 0.0
    if a:
        common = 0
        for ch in set(a):
            common += min(a.count(ch), b.count(ch))
        cov = common / len(a)
    print("\n[%d] %s" % (it["id"], it["expr"]))
    print("  ждали: %s" % exp)
    print("  услышали: %s" % heard)
    print("  покрытие ~%.2f" % cov)
