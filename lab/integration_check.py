"""Интеграционный тест _check_audio внутри voice_pipeline (без TTS).

Собирает ogg через ffmpeg (валидный: тишинa / речеподобный сигнал) плюс
битые байты. Проверяем, что:
  * речь проходит как годная,
  * тишина отбраковывается с подписью причины,
  * невалидные байты не декодируются и тоже отбраковываются,
  * без ffmpeg детектор честно молчит, но не ломает работу.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "app"))
os.chdir(ROOT)
import voice_pipeline as vp  # noqa: E402
import numpy as np  # noqa: E402

FF = vp._ffmpeg_exe()
assert FF, "ffmpeg не найден"

rng = np.random.default_rng(3)


def to_ogg(x: np.ndarray) -> bytes:
    """float32 mono 16k -> ogg через ffmpeg."""
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2").tobytes()
    r = subprocess.run(
        [FF, "-v", "error", "-f", "s16le", "-ar", "16000", "-ac", "1",
         "-i", "pipe:0", "-c:a", "libvorbis", "-q:a", "3",
         "-f", "ogg", "pipe:1"],
        input=pcm, capture_output=True, timeout=120)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[:300]
    return r.stdout


def speech(n_s: float) -> np.ndarray:
    n = int(n_s * 16000)
    t = np.arange(n) / 16000
    env = np.zeros(n, dtype="float32")
    pos = 0
    while pos < n:
        ln = min(int(0.18 * 16000 * float(rng.uniform(0.7, 1.4))), n - pos)
        env[pos:pos + ln] = (np.sin(2 * np.pi * 170 * t[pos:pos + ln])
                             * np.hanning(ln) * float(rng.uniform(0.6, 1.0)))
        pos += ln + int(0.04 * 16000 * float(rng.uniform(0.2, 1.6)))
    x = env * 0.3 + rng.standard_normal(n).astype("float32") * 0.02
    return x.astype("float32")


CASES = [
    ("речь 3 с -> годен",
     to_ogg(speech(3.0)), "きょうはあめです。", True),
    ("речь 2 с + хвост 0.5 -> годен",
     to_ogg(np.concatenate([speech(2.0),
                            np.zeros(int(0.5 * 16000), "float32")])),
     "とうきょうへいきます。", True),
    ("полная тишина -> брак",
     to_ogg(np.zeros(16000, "float32")), "つゆ", False),
    ("тишина 25 с + речь -> брак",
     to_ogg(np.concatenate([np.zeros(25 * 16000, "float32"), speech(1.5)])),
     "きょうはあめです。", False),
    ("битые байты -> брак",
     b"OggS" + bytes(range(256)) * 20, "きょう", False),
]

bad = 0
for name, blob, text, want in CASES:
    sigs, ok = vp._check_audio(blob, "ogg", text)
    good = ok == want
    bad += not good
    print("  %s  %-32s -> %-5s %s"
          % ("OK " if good else "FAIL", name,
             "годен" if ok else "брак", "; ".join(sigs)))

# путь без lab/quality_v2 (например, собранный .exe без исходников):
# детектор падает на простой критерий, не мешая работе
orig_get = vp._qc_v2_module
try:
    vp._qc_v2_module = lambda: None
    sigs, ok = vp._check_audio(b"\x00" * 100, "ogg", "きょうはあめです。")
    print("  %s  %-32s -> %s (сигналы: %s)"
          % ("OK " if ok else "FAIL", "нет quality_v2 -> не мешаем",
             "годен" if ok else "брак", sigs))
    bad += not ok
    # а вот настоящая тишина и на простом критерии должна ловиться
    sigs, ok = vp._check_audio(to_ogg(np.zeros(16000, "float32")), "ogg",
                               "きょうはあめです。")
    print("  %s  %-32s -> %s"
          % ("OK " if not ok else "FAIL", "тишина ловится и без quality_v2",
             "брак" if not ok else "годен"))
    bad += bool(ok)
finally:
    vp._qc_v2_module = orig_get

print("\nошибок: %d/%d" % (bad, len(CASES) + 2))
sys.exit(1 if bad else 0)
