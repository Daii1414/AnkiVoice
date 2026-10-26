#!/usr/bin/env bash
# ============================================================
#  run.sh — запуск AnkiVoice на Linux из папки проекта.
#  Работает без PATH и без команды ankivoice: достаточно install.sh.
#
#    ./run.sh                 — веб-интерфейс (откроется в браузере)
#    ./run.sh --no-open       — то же, без открытия браузера
#    ./run.sh pipeline list   — консольные команды (как pipeline.sh)
#    ./run.sh doctor          — диагностика
#    ./run.sh classic         — старое окно tkinter
# ============================================================
set -euo pipefail
HERE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PY="$HERE/pyruntime/bin/python"
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

if [ ! -x "$PY" ]; then
    echo "AnkiVoice ещё не установлен: сначала запусти  $HERE/install.sh" >&2
    exit 1
fi

case "${1:-}" in
    pipeline|cli) shift; exec "$HERE/pipeline.sh" "$@" ;;
    doctor)       shift; exec "$PY" "$HERE/app/anki_gui.py" doctor "$@" ;;
    classic)      shift; exec "$PY" "$HERE/app/anki_gui.py" --classic "$@" ;;
    -h|--help)    sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)            exec "$PY" "$HERE/app/anki_gui.py" "$@" ;;
esac
