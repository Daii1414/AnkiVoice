# -*- coding: utf-8 -*-
"""Встроенный «читатель» иероглифов: SudachiPy 0.7 (движок sudachi.rs) + словарь UniDic.

Запускается отдельным встроенным Python (папка pyruntime), потому что
движку GPT-SoVITS хватает Python 3.9, а свежий SudachiPy 0.7 требует 3.10+.

Протокол обмена со скриптом voice_pipeline.py (строки JSON, UTF-8):
  пайплайн -> помощник:  {"id": <номер>, "text": "<текст>"}
  помощник -> пайплайн:  {"id": <номер>, "tokens": [[поверхность,
                          нормализация, чтение], ...]}
Первый ответ после запуска — приветствие готовности:
                          {"ok": true, "version": "...", "dict": "..."}

Словарь 20261015 лежит в репозитории упакованным (sudachidict.zip, сам файл
193 МБ не влезает в GitHub) — при первом запуске распаковывается один раз.
"""
import json
import os
import sys
import zipfile

CODE = os.path.dirname(os.path.abspath(__file__))


def ensure_dictionary():
    """Распаковать свежий словарь Sudachi, если его ещё нет на месте."""
    import sudachidict_core
    res_dir = os.path.join(os.path.dirname(sudachidict_core.__file__), "resources")
    dic = os.path.join(res_dir, "system.dic")
    if os.path.isfile(dic) and os.path.getsize(dic) > 100 * 1024 * 1024:
        return
    z = os.path.join(CODE, "sudachidict.zip")
    if not os.path.isfile(z):
        raise SystemExit("Нет словаря Sudachi: нет ни %s, ни sudachidict.zip рядом "
                         "со скриптом." % dic)
    print("Распаковываю словарь Sudachi (один раз)...", file=sys.stderr, flush=True)
    os.makedirs(res_dir, exist_ok=True)
    with zipfile.ZipFile(z) as zf:
        zf.extractall(res_dir)
    if not (os.path.isfile(dic) and os.path.getsize(dic) > 100 * 1024 * 1024):
        raise SystemExit("sudachidict.zip повреждён — удали папку pyruntime, "
                         "заново разверни репозиторий и запусти инструмент.")


def main():
    ensure_dictionary()
    import sudachipy
    from importlib.metadata import version as _pkgver
    tk = sudachipy.Dictionary().tokenizer()
    try:
        dict_ver = _pkgver("sudachidict_core")
    except Exception:
        dict_ver = "?"
    print(json.dumps({"ok": True, "version": sudachipy.__version__,
                      "dict": dict_ver}), flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            toks = [[m.surface(), m.normalized_form(), m.reading_form()]
                    for m in tk.tokenize(req["text"], sudachipy.SplitMode.C)]
            out = {"id": req.get("id"), "tokens": toks}
        except Exception as e:
            out = {"id": None, "error": str(e)}
        print(json.dumps(out, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
