# -*- coding: utf-8 -*-
"""Сброс состояния под «нового пользователя»: движок ещё не выбран.

Мастер тогда показывает первый шаг с выбором движка — как при первой
установке. Конфиг пишем без BOM (через json.dump), как требует проект.
"""
import io
import json
import os
import sys

cfg_path = os.path.join(os.environ["APPDATA"], "AnkiVoice", "config.json")
with io.open(cfg_path, encoding="utf-8") as f:
    cfg = json.load(f)
cfg["engine_confirmed"] = False
with io.open(cfg_path, "w", encoding="utf-8", newline="\n") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
print("engine_confirmed -> False; limit=%s deck=%s" % (cfg.get("limit"), cfg.get("deck")))
