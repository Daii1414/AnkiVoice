"""Юнит-тест многосигнального детектора (lab/quality_v2).

Сигналы генерируются синтетически — тест не зависит от GPT-SoVITS и
прогоняется за секунды. Проверяем, что детектор:

  ГОДНОЕ:
   - чистая речь (шум с огибающей, как у японского высказывания)
   - короткое слово с хвостовой тишиной
   - речь с двумя естественными паузами (<= 1 с)
   - тихая, но слышимая речь (-30 дБ)

  БРАК:
   - полная тишина (файлы madara, 1 с нулей)
   - 25-40 с тишины + крошечный кусочек речи в конце (главный сбой GPT-SoVITS)
   - молчание в начале 5 с, потом речь
   - разрыв внутри речи 8 с
   - застрявшее повторение (один кусок зациклен)
   - обрезка по верхам (клиппинг)
   - речь в 20 раз медленнее нормы (растянутая генерация)
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quality_v2 import metrics_from_pcm, verdict, mora_count  # noqa: E402

SR = 16000
rng = np.random.default_rng(7)


def speech(n_s: float, level: float = 0.3, syllable: float = 0.18) -> np.ndarray:
    """Похожая на речь последовательность: чередование «слогов» и микро-пауз."""
    n = int(n_s * SR)
    t = np.arange(n) / SR
    env = np.zeros(n, dtype="float32")
    pos = 0
    while pos < n:
        ln = int(syllable * SR * float(rng.uniform(0.7, 1.4)))
        ln = min(ln, n - pos)
        seg = np.sin(2 * np.pi * 180 * t[pos:pos + ln]) * \
            np.hanning(ln) * float(rng.uniform(0.6, 1.0))
        env[pos:pos + ln] = seg.astype("float32")
        pos += ln
        gap = int(0.04 * SR * float(rng.uniform(0.2, 1.6)))
        pos += gap
    noise = rng.standard_normal(n).astype("float32") * 0.02
    x = (env * level + noise)
    return np.clip(x, -0.99, 0.99).astype("float32")


def silence(n_s: float, noise: float = 1e-4) -> np.ndarray:
    n = int(n_s * SR)
    return (rng.standard_normal(n).astype("float32") * noise).astype("float32")


CASES = [
    # (имя, сигнал, текст, ожидание)
    ("чистая речь 3 с",
     speech(3.0), "きょうはあめです。", True),
    ("короткое слово + хвост 0.6 с",
     np.concatenate([speech(0.6, level=0.35), silence(0.6)]), "つゆ", True),
    ("речь с двумя паузами 0.6 с",
     np.concatenate([speech(1.5), silence(0.6), speech(1.5),
                     silence(0.3), speech(1.5)]),
     "しょくにんはいたのしんしゅくにそなえあいじゃくりをほどこしてばった。",
     True),
    ("тихая, но слышимая речь -30 дБ",
     speech(3.0, level=0.03), "きょうはいけばなをならった。", True),
    ("хвост 0.7 с (норма, не трогаем)",
     np.concatenate([speech(2.0), silence(0.7)]),
     "きょうはいけばなをならった。", True),

    # ---- брак ----
    ("тихая запись: 0.18 с речи на 4 знака",
     np.concatenate([silence(1.7), speech(0.18), silence(1.4)]),
     "ｶﾞｷｮｳ", False),
    ("полная тишина 1 с (madara)",
     silence(1.0), "", False),
    ("тишина 25 с + речь 1.5 с в конце",
     np.concatenate([silence(25.0), speech(1.5), silence(1.0)]),
     "きょうはあめです。", False),
    ("тишина 30 с + речь 1 с (合釘-класс)",
     np.concatenate([silence(30.0), speech(1.0), silence(2.0)]),
     "いたはぎにあいくぎをうちこんでていねいにめんをそろえた。", False),
    ("молчание 5 с в начале",
     np.concatenate([silence(5.0), speech(2.5)]),
     "きょうはいけばなをならった。", False),
    ("разрыв внутри речи 8 с",
     np.concatenate([speech(2.0), silence(8.0), speech(2.0)]),
     "しょくにんはいたのしんしゅくにそなえあいじゃくりをほどこしてばった。",
     False),
    ("зацикленное повторение 8 с",
     np.tile(speech(1.2), 7), "きょうはあめです。", False),
    ("обрезка по верхам",
     np.clip(speech(3.0, level=0.3) * 4.0, -1.0, 1.0),
     "きょうはいけばなをならった。", False),
    ("растянутая генерация: 12 с на короткое слово",
     np.concatenate([speech(0.8), silence(0.9), speech(0.6),
                     silence(0.9), speech(0.5), silence(0.9),
                     speech(0.4), silence(0.9), speech(0.4),
                     silence(0.9), speech(0.4), silence(0.9),
                     speech(0.3)]),
     "つゆ", False),
]


def main():
    bad = 0
    for name, x, text, want in CASES:
        m = metrics_from_pcm(x, SR)
        sigs, is_bad = verdict(m, text)
        ok = (not is_bad) == want
        bad += not ok
        print("  %s  %-34s %5.1f с речь %4.1f  хвост %.1f  разрыв %.1f "
              "цикл %.2f дуб %2.1f | %s"
              % ("OK " if ok else "FAIL", name, m["dur"], m["sounding"],
                 m["tail"], m["gap_max"], m["loop"], m.get("dup", -1),
                 ("брак: " + "; ".join(sigs)) if is_bad else "годен"))
    print("\nошибок: %d/%d" % (bad, len(CASES)))

    # мор/с на реальном тексте
    for t in ("きょうはあめです。", "つゆ", "ぷらとー",
              "しょくにんはいたのしんしゅくにそなえあいじゃくりをほどこしてばった。"):
        print("  мор: %-22s -> %d" % (t, mora_count(t)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
