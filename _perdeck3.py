# -*- coding: utf-8 -*-
"""Режим чтения — только профиль колоды; общий дефолт не перетирается."""
import os

ROOT = os.environ["AV_ROOT"]


def rep(path, old, new, label=""):
    p = os.path.join(ROOT, path)
    src = open(p, encoding="utf-8").read()
    if old not in src:
        print("!! ne najdeno: " + label)
        return
    open(p, "w", encoding="utf-8", newline="").write(src.replace(old, new, 1))
    print("obnovlen", path, label)


rep("anki_web.py",
"""            for k in ("gptsovits_path", "theme", "deck", "voice", "mode",
                      "sentence_src", "sentence_audio", "word_src",
                      "word_audio", "furigana_src", "reading", "limit",
                      "verify_pronunciation", "asr_model", "lang"):
                if k in b:
                    cfg[k] = b[k]""",
"""            # \u0440\u0435\u0436\u0438\u043c \u0447\u0442\u0435\u043d\u0438\u044f \u2014 \u043d\u0430\u0441\u0442\u043e\u0439\u043a\u0430 \u043a\u043e\u043b\u043e\u0434\u044b (\u043f\u0440\u043e\u0444\u0438\u043b\u044c), \u043f\u043e\u044d\u0442\u043e\u043c\u0443
            # \u043e\u0431\u0449\u0438\u0439 \u0434\u0435\u0444\u043e\u043b\u0442 \u043d\u0435 \u043f\u0435\u0440\u0435\u0442\u0438\u0440\u0430\u0435\u043c
            top_keys = ("gptsovits_path", "theme", "deck", "voice", "mode",
                        "sentence_src", "sentence_audio", "word_src",
                        "word_audio", "furigana_src", "limit",
                        "verify_pronunciation", "asr_model", "lang")
            if "reading" in b and not (b.get("profile_deck") or "").strip():
                top_keys = top_keys + ("reading",)
            for k in top_keys:
                if k in b:
                    cfg[k] = b[k]""",
"backend: reading tolko v profil")
