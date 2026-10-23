# -*- coding: utf-8 -*-
"""Честное сравнение движков чтения на ROHAN — одном размеченном корпусе.

ROHAN4600: 4600 предложений, написанных людьми под диктовку условий
(все常用漢字, редкие моры), с проверенной катакановой транскрипцией.
Лицензия CC0. Это тот же корпус, на котором авторы Haqumei измеряли
KER=0.78% — цифры сравнимы с их отчётом.

Каждая строка:  ID:текст_с_фуриганой,эталонная_катакана
Метрика — KER (katakana error rate): расстояние Левенштейна по символам
к между ответом движка и эталоном, делённое на длину эталона.
Считается две версии: целиком и «только кана» (без пунктуации —
движки по-разному отдают знаки, это не чтение).

Варианты сравниваются РАЗДЕЛЬНО, не объединяются:
  1. sudachi-цепочка  — текущий конвейер AnkiVoice (kanaize)
  2. haqumei          — Haqumei 0.12 g2k
  3. pyoj-plus        — pyopenjtalk-plus 0.4.1 (улучшенный словарь)
  4. pyoj+tsqyomi     — pyopenjtalk-plus с контекстной моделью выбора
"""
import io
import os
import re
import sys
import time
import unicodedata

LAB = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(LAB)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "app"))   # voice_pipeline (kanaize) живёт в app/
sys.path.insert(0, ROOT)

TRANSCRIPT = os.path.join(LAB, "rohan", "transcript.txt")
RUBY = re.compile(r"\([^)]*\)")
KANA_ONLY = re.compile(r"[^ァ-ヶー・]")
HIRA2KATA = lambda s: "".join(
    chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)

# --- выравнивание нотации долгих гласных -------------------------------
# ROHAN пишет «トウゲンキョウ» (через う), движки — «トーゲンキョー» (через ー).
# Это РАЗЛИЧИЕ НОТАЦИИ, а не чтения. Чтобы сравнивать честно, обе стороны
# (эталон и ответ движка) прогоняются через одно преобразование:
#   обе стороны прогоняются через одно симметричное правило — collapse_long().
_ROW_VOWEL = {}


def _build_rows():
    rows = (("アイウエオ", "aiueo"), ("カキクケコ", "aiueo"),
            ("サシスセソ", "aiueo"), ("タチツテト", "aiueo"),
            ("ナニヌネノ", "aiueo"), ("ハヒフヘホ", "aiueo"),
            ("マミムメモ", "aiueo"), ("ヤユヨ", "auo"),
            ("ラリルレロ", "aiueo"), ("ワヲ", "ao"),
            ("ガギグゲゴ", "aiueo"), ("ザジズゼゾ", "aiueo"),
            ("ダヂヅデド", "aiueo"), ("バビブベボ", "aiueo"),
            ("パピプペポ", "aiueo"))
    for kana, vows in rows:
        for c, v in zip(kana, vows):
            _ROW_VOWEL[c] = v
    for c, v in (("ァ", "a"), ("ィ", "i"), ("ゥ", "u"), ("ェ", "e"),
                 ("ォ", "o"), ("ャ", "a"), ("ュ", "u"), ("ョ", "o"),
                 ("ヮ", "a"), ("ヴ", "u")):
        _ROW_VOWEL[c] = v
    for c in list(_ROW_VOWEL):          # хирагана — та же карта, сдвиг 0x60
        h = chr(ord(c) - 0x60)
        if "ぁ" <= h <= "ゖ":
            _ROW_VOWEL[h] = _ROW_VOWEL[c]


_build_rows()
# Чем схлопывается длинная запись: после о/у-ряда — う, после е/и-ряда — い
_LONG_AFTER = {"o": set("うウ"), "u": set("うウ"),
               "e": set("いイ"), "i": set("いイ")}


def collapse_long(kata):
    """Мягкая нормализация долгих гласных (применяется к ОБЕИМ сторонам).

    Убрать ー; убрать い/う, стоящие после гласной или малой кана.
    Тогда «トウゲンキョウ» (нотация ROHAN) = «トーゲンキョー/トーゲンキョ» (нотация
    движка) = «トゲンキョ». Правило симметрично — это не подгонка под движок,
    а снятие различий записи одного и того же звука.
    """
    out = []
    for c in kata:
        if c == "ー":
            continue                    # знак долгого — гласная предыдущего
        if c in _LONG_AFTER.get(_ROW_VOWEL.get(out[-1] if out else ""), ()):
            continue                    # «トウ/トー» — одна и та же запись
        out.append(c)
    return "".join(out)


def lev(a, b):
    """Расстояние Левенштейна (два ряда, O(min) памяти)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def load():
    rows = []
    for line in io.open(TRANSCRIPT, encoding="utf-8").read().splitlines():
        if ":" not in line:
            continue
        _, rest = line.split(":", 1)
        if "," not in rest:
            continue
        text, ref = rest.split(",", 1)
        text = text.strip()
        ref = unicodedata.normalize("NFKC", ref.strip())
        if text and ref:
            rows.append((text, ref))
    return rows


def main():
    rows = load()
    print("предложений:", len(rows))

    from voice_pipeline import kanaize
    from haqumei import Haqumei
    import pyopenjtalk

    hq = Haqumei()
    # Haqumei с опциями, которыми его авторы меряли ROHAN (см. README)
    hq_rohan = Haqumei(revert_long_vowels=True, revert_yotsugana=True)
    try:
        pyopenjtalk.tsqyomi.load_model()
        has_tsq = True
        print("tsqyomi: модель загружена")
    except Exception as e:
        has_tsq = False
        print("tsqyomi недоступна:", e)

    engines = {
        "sudachi-цепочка": lambda s: HIRA2KATA(kanaize(s)),
        "haqumei": lambda s: HIRA2KATA(unicodedata.normalize("NFKC", hq.g2k(s))),
        "haqumei(рохан-опции)": lambda s: HIRA2KATA(unicodedata.normalize(
            "NFKC", hq_rohan.g2k(s))),
        "pyoj-plus": lambda s: HIRA2KATA(unicodedata.normalize(
            "NFKC", pyopenjtalk.g2p(s, kana=True))),
    }
    if has_tsq:
        engines["pyoj+tsqyomi"] = lambda s: HIRA2KATA(unicodedata.normalize(
            "NFKC", pyopenjtalk.g2p(s, kana=True, use_tsqyomi=True)))

    stats = {k: [0, 0, 0, 0] for k in engines}  # dist, n, dist_kana, dist_aligned
    worst = {k: [] for k in engines}

    t0 = time.time()
    for i, (text, ref) in enumerate(rows):
        text = RUBY.sub("", text)        # убрать фуригану (なが) — движкам чистый текст
        ref_kana = KANA_ONLY.sub("", ref)
        ref_aligned = collapse_long(ref_kana)
        for name, fn in engines.items():
            got = fn(text)
            got_kana = KANA_ONLY.sub("", got)
            got_aligned = collapse_long(got_kana)
            st = stats[name]
            st[0] += lev(got, ref)
            st[1] += len(ref)
            st[2] += lev(got_kana, ref_kana)
            st[3] += lev(got_aligned, ref_aligned)
            # худшие предложения — материал для разбора (по выровненной метрике)
            d = lev(got_aligned, ref_aligned)
            if d >= 3 and len(worst[name]) < 40:
                worst[name].append((d, text, ref_aligned, got_aligned))
        if (i + 1) % 1000 == 0:
            print(f"  ...{i + 1}/{len(rows)} ({time.time() - t0:.0f} с)")

    n = len(rows)
    kana_total = _kana_total(rows)
    kana_aligned = sum(len(collapse_long(KANA_ONLY.sub("", r))) for _, r in rows)
    print(f"\n=== ROHAN4600: {n} предложений, KER = дистанция/символы эталона ===")
    print(f"{'вариант':<22} {'KER кана (сырой)':>17} {'KER кана (нотация=)':>20}")
    for name, (dist, total, dist_k, dist_a) in stats.items():
        print(f"{name:<22} {dist_k / kana_total:>16.2%} {dist_a / kana_aligned:>19.2%}")

    for name, fl in worst.items():
        fl.sort(reverse=True)
        print(f"\n-- худшие [{name}] --")
        for d, t, r, g in fl[:4]:
            print(f"  Δ{d}: {t[:34]}")
            print(f"     эталон: {r[:34]}")
            print(f"     движок: {g[:34]}")


def _kana_total(rows):
    return sum(len(KANA_ONLY.sub("", r)) for _, r in rows)


if __name__ == "__main__":
    main()
