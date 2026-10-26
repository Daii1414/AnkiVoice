#!/usr/bin/env bash
# ============================================================
#  pipeline.sh — консольная точка входа AnkiVoice на Linux
#  (аналог pipeline.bat). Без аргументов — интерактивное меню.
#    ./pipeline.sh list
#    ./pipeline.sh make-deck --voice madara --query "deck:Arhitektura" --limit 20
#  Папка движка ищется так же, как в pipeline.bat: GPT_SOVITS_ROOT ->
#  app/gptsovits_path.txt -> ~/.config/AnkiVoice/config.json. Пайплайн
#  работает в Python движка (gsv-venv, его собирает install.sh) или в
#  GPT_SOVITS_PYTHON, если он задан.
# ============================================================
set -euo pipefail
HERE="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8

PYRT="$HERE/pyruntime/bin/python"
[ -x "$PYRT" ] || PYRT="$(command -v python3)"

# движок и его Python — тем же кодом, что и у самого пайплайна (engines.py)
mapfile -t RES < <("$PYRT" - "$HERE/app" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import av_state, engines  # noqa: F401  (engines резолвит движок при импорте)
print(av_state.ENGINE or "")
print(av_state.PYTHON or "")
PY
)
ENGINE="${RES[0]:-}"
ENGINE_PY="${RES[1]:-}"

if [ -z "$ENGINE" ] || [ -z "$ENGINE_PY" ]; then
    cat >&2 <<'EOF'

 GPT-SoVITS не найден (или для него не собран Python). Сделай одно из:
   * ./install.sh --engine /путь/к/GPT-SoVITS
   * ./install.sh --download-engine
   * export GPT_SOVITS_ROOT=/путь/к/GPT-SoVITS GPT_SOVITS_PYTHON=/путь/к/python

EOF
    exit 1
fi

# дочерний процесс резолвит движок так же
export GPT_SOVITS_ROOT="$ENGINE"
exec "$ENGINE_PY" -u "$HERE/app/voice_pipeline.py" "$@"
