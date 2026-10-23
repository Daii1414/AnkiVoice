# -*- coding: utf-8 -*-
"""Скачать транскрипт ROHAN (CC0) для bench_rohan.py.

Корпус: mmorise/rohan4600 — морально-сбалансированный японский корпус чтений,
лицензия CC0 (public domain). Файл кладётся в lab/rohan/transcript.txt — путь,
который ждёт bench_rohan.py. В репозиторий корпус не входит (1.1 МБ) и в CI
не скачивается: бенчмарк запускается вручную.

Запуск:  python lab/fetch_rohan.py
"""
import os
import sys
import urllib.request

URL = ("https://raw.githubusercontent.com/mmorise/rohan4600/"
       "master/Rohan4600_transcript_utf8.txt")
DST = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "rohan", "transcript.txt")


def main():
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    if os.path.isfile(DST) and os.path.getsize(DST) > 500000:
        print("уже скачан:", DST)
        return 0
    print("скачиваю ROHAN (CC0) ...\n ", URL)
    with urllib.request.urlopen(URL, timeout=120) as r:
        data = r.read()
    n_lines = data.decode("utf-8").count("\n")
    if n_lines < 4000:
        print("подозрительно мало строк (%d) — файл не сохраняю" % n_lines,
              file=sys.stderr)
        return 1
    with open(DST, "wb") as f:
        f.write(data)
    print("готово: %s (%d предложений)" % (DST, n_lines))
    print("дальше: python lab/bench_rohan.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
