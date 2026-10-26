#!/usr/bin/env bash
# =====================================================================
#  AnkiVoice — установщик для Linux (Arch, Debian/Ubuntu/Mint, Fedora/RHEL,
#  openSUSE, Void, Solus, Gentoo; NixOS и Alpine — с оговорками).
#
#  Из интернета (скачает программу, окружения и, по желанию, движок):
#    curl -fsSL https://raw.githubusercontent.com/Daii1414/AnkiVoice/main/install.sh | bash
#
#  Из уже скачанной папки:
#    ./install.sh                         # мастер: проверит, что есть, и спросит
#    ./install.sh --check                 # только показать, чего не хватает
#    ./install.sh --engine ~/GPT-SoVITS   # своя папка GPT-SoVITS
#    ./install.sh --download-engine       # скачать GPT-SoVITS v2Pro
#    ./install.sh --uninstall             # удалить программу (спросит, что именно)
#
#  Как устроено:
#    1. ПРОВЕРКА: дистрибутив, git, curl, ffmpeg, компилятор и cmake, uv,
#       видеокарта, место на диске, Anki, AnkiConnect, движок GPT-SoVITS.
#    2. ВОПРОСЫ — до любой загрузки: для каждого недостающего — поставить,
#       указать папку, где оно уже есть (например, на другом диске), или
#       пропустить (если без него можно). Затем общий план и подтверждение.
#    3. УСТАНОВКА по плану: системные пакеты одной командой менеджера
#       пакетов, окружения Python (uv), движок, команда `ankivoice`, ярлык.
#
#  Флаги: --check, --dry-run (показать план, ничего не менять), --yes
#         (всё недостающее — ставить), --engine PATH, --download-engine,
#         --no-engine (движок настроить позже),
#         --data-dir PATH (куда класть окружения и движок — ~8 ГБ),
#         --dir PATH (куда ставить программу), --cpu, --no-desktop,
#         --no-tui (вопросы текстом, без окон whiptail), --lang ru|en,
#         --uninstall, --help
# =====================================================================
set -euo pipefail

REPO_URL="${ANKIVOICE_REPO:-https://github.com/Daii1414/AnkiVoice.git}"
REPO_BRANCH="${ANKIVOICE_BRANCH:-main}"
GSV_REPO="${GSV_REPO:-https://github.com/RVC-Boss/GPT-SoVITS.git}"
GSV_REF="${GSV_REF:-20250606v2pro}"
TORCH_VER="2.5.1"
TORCH_CUDA_INDEX="https://download.pytorch.org/whl/cu124"
TORCH_CPU_INDEX="https://download.pytorch.org/whl/cpu"
ANKICONNECT_CODE="2055492159"
ANKICONNECT_URL="https://ankiweb.net/shared/download/$ANKICONNECT_CODE?v=2.1&p=250900"

DATA="${XDG_DATA_HOME:-$HOME/.local/share}/AnkiVoice"
CONF="${XDG_CONFIG_HOME:-$HOME/.config}/AnkiVoice"
BIN="${ANKIVOICE_BIN:-$HOME/.local/bin}"

ENGINE=""
DOWNLOAD_ENGINE=0
NO_ENGINE=0
FORCE_CPU=0
ASSUME_YES=0
DESKTOP=1
APP_DIR=""
MODE=install            # install | check | dry-run | uninstall
TUI=auto
UI_LANG=""

# ------------------------------------------------------------ язык
for a in "$@"; do case "$a" in --lang=*) UI_LANG="${a#*=}";; esac; done
prev=""; for a in "$@"; do [ "$prev" = --lang ] && UI_LANG="$a"; prev="$a"; done
if [ -z "$UI_LANG" ]; then
    case "${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}" in ru*|uk*|be*|kk*) UI_LANG=ru ;; *) UI_LANG=en ;; esac
fi
# t "по-русски" "in English"
t() { if [ "$UI_LANG" = ru ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }

# ------------------------------------------------------------ вывод
if [ -t 1 ]; then
    C_B=$'\e[1m'; C_D=$'\e[2m'; C_G=$'\e[32m'; C_Y=$'\e[33m'; C_R=$'\e[31m'; C_C=$'\e[36m'; C_0=$'\e[0m'
else
    C_B=""; C_D=""; C_G=""; C_Y=""; C_R=""; C_C=""; C_0=""
fi
step() { printf '\n%s==> %s%s\n' "$C_B" "$*" "$C_0"; }
ok()   { printf '  %s✓%s %s\n' "$C_G" "$C_0" "$*"; }
warn() { printf '  %s!%s %s\n' "$C_Y" "$C_0" "$*"; }
info() { printf '    %s%s%s\n' "$C_D" "$*" "$C_0"; }
die()  { printf '\n%s%s%s %s\n' "$C_R" "$(t 'Ошибка:' 'Error:')" "$C_0" "$*" >&2; exit 1; }

usage() { sed -n '2,32p' "$0" 2>/dev/null | sed 's/^# \{0,1\}//'; exit 0; }

while [ $# -gt 0 ]; do
    case "$1" in
        --engine) ENGINE="${2:?--engine PATH}"; shift 2 ;;
        --engine=*) ENGINE="${1#*=}"; shift ;;
        --download-engine) DOWNLOAD_ENGINE=1; shift ;;
        --no-engine) NO_ENGINE=1; shift ;;
        --data-dir) DATA="${2:?--data-dir PATH}"; shift 2 ;;
        --data-dir=*) DATA="${1#*=}"; shift ;;
        --cpu) FORCE_CPU=1; shift ;;
        --yes|-y) ASSUME_YES=1; shift ;;
        --no-desktop) DESKTOP=0; shift ;;
        --dir) APP_DIR="${2:?--dir PATH}"; shift 2 ;;
        --check) MODE=check; shift ;;
        --dry-run) MODE=dry-run; shift ;;
        --uninstall) MODE=uninstall; shift ;;
        --no-tui) TUI=0; shift ;;
        --lang) shift 2 ;;
        --lang=*) shift ;;
        --update) shift ;;                     # совместимость с `ankivoice update`
        -h|--help) usage ;;
        *) die "$(t 'неизвестный флаг' 'unknown flag'): $1 (--help)" ;;
    esac
done

[ "$(uname -s)" = Linux ] || die "$(t 'этот установщик — для Linux (для Windows есть AnkiVoice-Setup.exe)' 'this installer is for Linux (Windows has AnkiVoice-Setup.exe)')"
[ "$(id -u)" != 0 ] || die "$(t 'не запускай от root: всё ставится в домашнюю папку (sudo спросится только для системных пакетов)' 'do not run as root: everything goes to your home folder (sudo is asked only for system packages)')"
DATA="$(realpath -m "${DATA/#\~/$HOME}")"
ORIG_PATH="$PATH"
export PATH="$BIN:$HOME/.local/bin:$PATH"

# ------------------------------------------------------------ диалоги
# Вопросы задаём с терминала (/dev/tty) — так они работают и при
# `curl ... | bash`. Есть whiptail и терминал — окна, иначе текст.
HAVE_TTY=0; { : < /dev/tty; } 2>/dev/null && HAVE_TTY=1
if [ "$TUI" = auto ]; then
    if [ "$HAVE_TTY" = 1 ] && command -v whiptail >/dev/null 2>&1 && [ "${TERM:-dumb}" != dumb ]; then TUI=1; else TUI=0; fi
fi
interactive() { [ "$ASSUME_YES" = 0 ] && [ "$HAVE_TTY" = 1 ]; }

# ui_yesno "вопрос" [y|n] -> 0 = да
ui_yesno() {
    local q="$1" def="${2:-y}" ans=""
    if ! interactive; then [ "$def" = y ]; return; fi
    if [ "$TUI" = 1 ]; then
        local extra=(); [ "$def" = n ] && extra=(--defaultno)
        whiptail --title AnkiVoice "${extra[@]}" --yes-button "$(t 'Да' 'Yes')" --no-button "$(t 'Нет' 'No')" \
            --yesno "$q" 0 0 < /dev/tty > /dev/tty 2>&1
        return
    fi
    printf '  %s? %s%s [%s] ' "$C_Y" "$q" "$C_0" "$([ "$def" = y ] && t 'Д/н' 'Y/n' || t 'д/Н' 'y/N')" > /dev/tty
    read -r ans < /dev/tty || ans=""
    ans="${ans,,}"
    if [ -z "$ans" ]; then [ "$def" = y ]; return; fi
    [[ "$ans" =~ ^(y|yes|д|да)$ ]]
}

# ui_menu "заголовок" "текст" ключ1 "пункт1" ключ2 "пункт2" ... -> ключ в REPLY
ui_menu() {
    local title="$1" text="$2"; shift 2
    local keys=() labels=() i=0
    while [ $# -gt 0 ]; do keys+=("$1"); labels+=("$2"); shift 2; done
    if ! interactive; then REPLY="${keys[0]}"; return; fi
    if [ "$TUI" = 1 ]; then
        local items=(); for i in "${!keys[@]}"; do items+=("${keys[$i]}" "${labels[$i]}"); done
        REPLY="$(whiptail --title "$title" --notags --ok-button "$(t 'Выбрать' 'Select')" \
                 --cancel-button "$(t 'Отмена' 'Cancel')" --menu "$text" 0 0 0 "${items[@]}" \
                 3>&1 1>/dev/tty 2>&3 < /dev/tty)" || die "$(t 'установка отменена' 'installation cancelled')"
        return
    fi
    printf '\n  %s%s%s\n  %s\n' "$C_B" "$title" "$C_0" "$text" > /dev/tty
    for i in "${!keys[@]}"; do printf '    %s%d)%s %s\n' "$C_C" $((i + 1)) "$C_0" "${labels[$i]}" > /dev/tty; done
    local ans=""
    while :; do
        printf '  %s [1]: ' "$(t 'Выбор' 'Choice')" > /dev/tty
        read -r ans < /dev/tty || ans=1
        ans="${ans:-1}"
        if [[ "$ans" =~ ^[0-9]+$ ]] && [ "$ans" -ge 1 ] && [ "$ans" -le "${#keys[@]}" ]; then
            REPLY="${keys[$((ans - 1))]}"; return
        fi
    done
}

# ui_input "вопрос" [по умолчанию] -> ответ в REPLY
ui_input() {
    local q="$1" def="${2:-}"
    REPLY="$def"
    interactive || return 0
    if [ "$TUI" = 1 ]; then
        REPLY="$(whiptail --title AnkiVoice --ok-button OK --cancel-button "$(t 'Назад' 'Back')" \
                 --inputbox "$q" 0 70 "$def" 3>&1 1>/dev/tty 2>&3 < /dev/tty)" || REPLY=""
        return 0
    fi
    printf '  %s%s%s%s: ' "$C_Y" "$q" "$C_0" "${def:+ [$def]}" > /dev/tty
    read -r REPLY < /dev/tty || REPLY=""
    REPLY="${REPLY:-$def}"
}

# ------------------------------------------------------------ дистрибутив
OS_ID=""; OS_LIKE=""; OS_NAME="Linux"
if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    OS_ID="${ID:-}"; OS_LIKE="${ID_LIKE:-}"; OS_NAME="${PRETTY_NAME:-${NAME:-Linux}}"
fi
FAMILY=unknown
for id in $OS_ID $OS_LIKE; do
    case "$id" in
        arch|manjaro|endeavouros|garuda|cachyos|artix) FAMILY=arch; break ;;
        debian|ubuntu|linuxmint|pop|elementary|zorin|kali|raspbian|neon) FAMILY=debian; break ;;
        fedora|rhel|centos|rocky|almalinux|nobara|ultramarine) FAMILY=fedora; break ;;
        opensuse*|suse|sles) FAMILY=suse; break ;;
        void) FAMILY=void; break ;;
        solus) FAMILY=solus; break ;;
        gentoo|funtoo) FAMILY=gentoo; break ;;
        nixos) FAMILY=nixos; break ;;
        alpine) FAMILY=alpine; break ;;
    esac
done
if [ "$FAMILY" = unknown ]; then
    for pm in pacman apt-get dnf zypper xbps-install eopkg emerge apk; do
        if command -v "$pm" >/dev/null 2>&1; then
            case "$pm" in pacman) FAMILY=arch;; apt-get) FAMILY=debian;; dnf) FAMILY=fedora;;
                zypper) FAMILY=suse;; xbps-install) FAMILY=void;; eopkg) FAMILY=solus;;
                emerge) FAMILY=gentoo;; apk) FAMILY=alpine;; esac
            break
        fi
    done
fi

# имя пакета для зависимости в этом семействе (пусто — менеджер пакетов не ставит)
pkgs_for() {
    case "$FAMILY:$1" in
        arch:git|debian:git|fedora:git|suse:git|void:git|solus:git|alpine:git) echo git ;;
        gentoo:git) echo dev-vcs/git ;;
        *:curl) [ "$FAMILY" = gentoo ] && echo net-misc/curl || echo curl ;;
        arch:ffmpeg|debian:ffmpeg|suse:ffmpeg|void:ffmpeg|solus:ffmpeg|alpine:ffmpeg) echo ffmpeg ;;
        fedora:ffmpeg) echo ffmpeg-free ;;
        gentoo:ffmpeg) echo media-video/ffmpeg ;;
        arch:build) echo base-devel cmake ;;
        debian:build) echo build-essential cmake ;;
        fedora:build|suse:build) echo gcc gcc-c++ make cmake ;;
        void:build) echo base-devel cmake ;;
        solus:build) echo -c system.devel cmake ;;
        gentoo:build) echo dev-build/cmake ;;
        alpine:build) echo build-base cmake ;;
        # anki есть в репозиториях Arch, Void и Ubuntu; в Debian 12 и Fedora
        # его нет — там Anki ставится из Flathub (проверено в контейнерах)
        arch:anki|void:anki) echo anki ;;
        debian:anki) case " $OS_ID $OS_LIKE " in *" ubuntu "*) echo anki ;; *) echo "" ;; esac ;;
        *) echo "" ;;
    esac
}
pm_cmd() {   # команда установки пакетов (без самих пакетов)
    case "$FAMILY" in
        arch)   echo "sudo pacman -S --needed --noconfirm" ;;
        debian) echo "sudo apt-get install -y" ;;
        fedora) echo "sudo dnf install -y" ;;
        suse)   echo "sudo zypper --non-interactive install" ;;
        void)   echo "sudo xbps-install -Sy" ;;
        solus)  echo "sudo eopkg install -y" ;;
        gentoo) echo "sudo emerge --noreplace" ;;
        alpine) echo "sudo apk add" ;;
        *)      echo "" ;;
    esac
}
pm_refresh() {
    case "$FAMILY" in
        debian) sudo apt-get update ;;
        arch)   sudo pacman -Sy --noconfirm ;;
        *) : ;;
    esac
}

# ------------------------------------------------------------ проверка
# Состояние зависимостей: STATE[x] = ok|missing|skip, WHERE[x] — где нашлось,
# ACTION[x] = pkg|download|path|skip (решение пользователя)
declare -A STATE WHERE ACTION USERDIR NAME_OF REQUIRED HINT
EXTRA_PATH=""          # папки с программами на других дисках -> PATH ankivoice
ANKI2_DIR=""           # папка данных Anki (Anki2), если не стандартная

NAME_OF[git]="git"; NAME_OF[curl]="curl"; NAME_OF[ffmpeg]="ffmpeg"
NAME_OF[build]="$(t 'компилятор C/C++, make, cmake' 'C/C++ compiler, make, cmake')"
NAME_OF[uv]="uv ($(t 'менеджер Python' 'Python manager'))"
NAME_OF[gpu]="$(t 'видеокарта NVIDIA (драйвер)' 'NVIDIA GPU (driver)')"
NAME_OF[anki]="Anki"
NAME_OF[connect]="AnkiConnect ($(t 'дополнение' 'add-on') $ANKICONNECT_CODE)"
NAME_OF[engine]="$(t 'движок GPT-SoVITS' 'GPT-SoVITS engine')"
HINT[ffmpeg]="$(t 'проверка звука и сжатие в .ogg' 'audio checks and .ogg compression')"
HINT[build]="$(t 'сборка pyopenjtalk (японское произношение)' 'builds pyopenjtalk (Japanese pronunciation)')"
HINT[gpu]="$(t 'без неё синтез на процессоре, в разы медленнее' 'without it synthesis runs on the CPU, many times slower')"
HINT[anki]="$(t 'AnkiVoice пишет звук в карточки Anki' 'AnkiVoice writes audio into Anki cards')"
HINT[connect]="$(t 'через него AnkiVoice говорит с Anki' 'AnkiVoice talks to Anki through it')"
HINT[engine]="$(t 'синтезирует голоса; ~6 ГБ с моделями' 'synthesizes the voices; ~6 GB with models')"

SELF_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
if [ -z "$APP_DIR" ]; then
    if [ -n "$SELF_DIR" ] && [ -f "$SELF_DIR/app/voice_pipeline.py" ]; then
        APP_DIR="$SELF_DIR"                 # запуск из скачанной папки
    else
        APP_DIR="$DATA/app"
    fi
fi
NEED_CLONE=0; [ -f "$APP_DIR/app/voice_pipeline.py" ] || NEED_CLONE=1

read_cfg() {   # значение ключа из config.json (без Python: простой разбор)
    [ -f "$CONF/config.json" ] || return 0
    sed -n "s/^[[:space:]]*\"$1\"[[:space:]]*:[[:space:]]*\"\\(.*\\)\"[[:space:]]*,\\{0,1\\}[[:space:]]*$/\\1/p" \
        "$CONF/config.json" | head -1 | sed 's/\\\\/\\/g; s/\\"/"/g'
}
is_engine() { [ -n "$1" ] && [ -f "$1/api_v2.py" ] && [ -d "$1/GPT_SoVITS" ]; }

anki2_candidates() {
    [ -n "$ANKI2_DIR" ] && echo "$ANKI2_DIR"
    local c; c="$(read_cfg anki2_dir)"; [ -n "$c" ] && echo "$c"
    echo "${XDG_DATA_HOME:-$HOME/.local/share}/Anki2"
    echo "$HOME/.var/app/net.ankiweb.Anki/data/Anki2"
    echo "$HOME/snap/anki-woodrow/common/Anki2"
    echo "$HOME/Anki2"
}

detect_tool() {   # detect_tool ключ команда...
    local key="$1"; shift
    local c
    for c in "$@"; do
        if command -v "$c" >/dev/null 2>&1; then STATE[$key]=ok; WHERE[$key]="$(command -v "$c")"; return; fi
    done
    STATE[$key]=missing; WHERE[$key]=""
}

detect_all() {
    REQUIRED[git]=$NEED_CLONE; REQUIRED[curl]=0; REQUIRED[ffmpeg]=1; REQUIRED[build]=1
    REQUIRED[uv]=1; REQUIRED[gpu]=0; REQUIRED[anki]=0; REQUIRED[connect]=0; REQUIRED[engine]=0
    detect_tool git git
    detect_tool curl curl
    detect_tool ffmpeg ffmpeg
    detect_tool uv uv
    command -v uv >/dev/null 2>&1 || REQUIRED[curl]=1        # uv ставится скриптом через curl
    local miss=()
    for c in cc c++ make cmake; do command -v "$c" >/dev/null 2>&1 || miss+=("$c"); done
    if [ ${#miss[@]} -eq 0 ]; then STATE[build]=ok; WHERE[build]="$(command -v cmake)"
    else STATE[build]=missing; WHERE[build]="$(t 'нет' 'missing'): ${miss[*]}"; fi
    if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
        STATE[gpu]=ok; WHERE[gpu]="$(nvidia-smi -L | head -1 | sed 's/ (UUID.*//')"
    else STATE[gpu]=missing; WHERE[gpu]=""; fi
    # Anki: программа или её данные
    STATE[anki]=missing; WHERE[anki]=""
    if command -v anki >/dev/null 2>&1; then STATE[anki]=ok; WHERE[anki]="$(command -v anki)"
    elif command -v flatpak >/dev/null 2>&1 && flatpak info net.ankiweb.Anki >/dev/null 2>&1; then
        STATE[anki]=ok; WHERE[anki]="flatpak net.ankiweb.Anki"
    fi
    STATE[connect]=missing; WHERE[connect]=""
    local d
    while IFS= read -r d; do
        [ -d "$d" ] || continue
        if [ "${STATE[anki]}" != ok ] && [ -f "$d/prefs21.db" ]; then
            STATE[anki]=ok; WHERE[anki]="$(t 'данные' 'data'): $d"
        fi
        if [ -f "$d/addons21/$ANKICONNECT_CODE/__init__.py" ]; then
            STATE[connect]=ok; WHERE[connect]="$d/addons21/$ANKICONNECT_CODE"; ANKI2_DIR="${ANKI2_DIR:-$d}"; break
        fi
    done < <(anki2_candidates)
    # движок: флаг, конфиг, автопоиск
    STATE[engine]=missing; WHERE[engine]=""
    if [ -n "$ENGINE" ]; then
        ENGINE="$(realpath -m "${ENGINE/#\~/$HOME}")"
        is_engine "$ENGINE" || die "$ENGINE: $(t 'нет api_v2.py и GPT_SoVITS/ — это не папка GPT-SoVITS' 'no api_v2.py and GPT_SoVITS/ — not a GPT-SoVITS folder')"
    elif [ "$DOWNLOAD_ENGINE" = 0 ]; then
        local cand; cand="$(read_cfg gptsovits_path)"
        if is_engine "$cand"; then ENGINE="$cand"
        else
            local api
            while IFS= read -r -d '' api; do
                d="$(dirname "$api")"
                if is_engine "$d"; then ENGINE="$d"; break; fi
            done < <(find "$HOME" "$DATA" "/run/media/$USER" /media /mnt /opt \
                        -maxdepth 4 -type f -name api_v2.py -path '*[Ss][Oo][Vv][Ii][Tt][Ss]*' \
                        -not -path '*/.cache/*' -not -path '*/Trash/*' -print0 2>/dev/null)
        fi
    fi
    if [ -n "$ENGINE" ] && is_engine "$ENGINE"; then STATE[engine]=ok; WHERE[engine]="$ENGINE"; fi
    [ "$DOWNLOAD_ENGINE" = 1 ] && { STATE[engine]=missing; ACTION[engine]=download; }
    [ "$NO_ENGINE" = 1 ] && [ "${STATE[engine]}" != ok ] && ACTION[engine]=skip
    return 0
}

free_gb() {   # свободно ГБ в папке (или в ближайшей существующей выше); без awk
    local d="$1" line
    while [ ! -d "$d" ] && [ "$d" != / ]; do d="$(dirname "$d")"; done
    line="$(df -Pk "$d" 2>/dev/null | tail -n 1)" || true
    set -- $line
    [ -n "${4:-}" ] && [ "$4" -eq "$4" ] 2>/dev/null && echo $(( $4 / 1048576 )) || echo 0
}
pad() {   # дополнить пробелами до N символов, а не байт: длину UTF-8 считаем
          # сами — в контейнерах и минимальных системах локали часто нет
    local s="$1" n="$2" cont len
    cont="$(LC_ALL=C; printf '%s' "${s//[!$'\x80'-$'\xbf']/}")"
    len=$(( $(LC_ALL=C; printf '%s' "$s" | wc -c) - $(printf '%s' "$cont" | LC_ALL=C wc -c) ))
    printf '%s%*s' "$s" $(( n > len ? n - len : 0 )) ""
}

DEPS=(git curl ffmpeg build uv gpu anki connect engine)
print_report() {
    step "$(t 'Проверка системы' 'System check') — $OS_NAME"
    [ "$FAMILY" = unknown ] && warn "$(t 'дистрибутив не распознан: системные пакеты придётся поставить вручную' 'unknown distribution: system packages must be installed by hand')"
    [ "$FAMILY" = alpine ] && warn "$(t 'Alpine (musl): PyTorch под musl не ставится — движок GPT-SoVITS здесь не заработает' 'Alpine (musl): PyTorch is not available for musl — the GPT-SoVITS engine will not run here')"
    [ "$FAMILY" = nixos ] && warn "$(t 'NixOS: системные пакеты ставь через configuration.nix или nix profile; uv-Python может потребовать nix-ld' 'NixOS: install system packages via configuration.nix or nix profile; uv-managed Python may need nix-ld')"
    local k mark note
    for k in "${DEPS[@]}"; do
        if [ "${STATE[$k]}" = ok ]; then mark="${C_G}✓${C_0}"; note="${WHERE[$k]}"
        elif [ "${REQUIRED[$k]}" = 1 ]; then mark="${C_R}✗${C_0}"; note="$(t 'не найдено — нужно' 'not found — required')${WHERE[$k]:+ (${WHERE[$k]})}"
        else mark="${C_Y}○${C_0}"; note="$(t 'не найдено' 'not found')${HINT[$k]:+ — ${HINT[$k]}}"; fi
        printf '  %s %s %s%s%s\n' "$mark" "$(pad "${NAME_OF[$k]}" 34)" "$C_D" "$note" "$C_0"
    done
    local fg; fg="$(free_gb "$(dirname "$DATA")")"
    printf '  %s %s %s%s %s%s\n' "$([ "${fg:-0}" -ge 10 ] && echo "${C_G}✓${C_0}" || echo "${C_Y}○${C_0}")" \
        "$(pad "$(t 'место на диске' 'disk space')" 34)" "$C_D" "${fg:-?} $(t 'ГБ свободно в' 'GB free in')" "$(dirname "$DATA")" "$C_0"
}

# ------------------------------------------------------------ вопросы
# путь, который указал пользователь, проверяем по смыслу зависимости
check_user_dir() {   # check_user_dir ключ папка -> 0 если годится
    local k="$1" d="$2"
    case "$k" in
        git|curl|ffmpeg|uv) [ -x "$d/$k" ] ;;
        build) [ -x "$d/cmake" ] || [ -x "$d/cc" ] ;;
        anki) [ -x "$d/anki" ] || [ -f "$d/prefs21.db" ] ;;
        connect) [ -f "$d/addons21/$ANKICONNECT_CODE/__init__.py" ] || [ -d "$d/addons21" ] || [ -f "$d/prefs21.db" ] ;;
        engine) is_engine "$d" ;;
        *) [ -d "$d" ] ;;
    esac
}
path_hint() {
    case "$1" in
        git|curl|ffmpeg|uv) t "папка, где лежит программа $1 (например /mnt/disk/tools/bin)" "folder that contains the $1 program (e.g. /mnt/disk/tools/bin)" ;;
        build) t "папка с cmake и компилятором" "folder with cmake and the compiler" ;;
        anki) t "папка программы Anki (с файлом anki) или папка данных Anki2" "the Anki program folder (with the anki file) or the Anki2 data folder" ;;
        connect) t "папка данных Anki (Anki2 — в ней addons21)" "Anki's data folder (Anki2 — contains addons21)" ;;
        engine) t "папка GPT-SoVITS (в ней api_v2.py)" "the GPT-SoVITS folder (contains api_v2.py)" ;;
    esac
}

ask_dep() {   # решение по одной недостающей зависимости
    local k="$1" opts=() pk
    pk="$(pkgs_for "$k")"
    case "$k" in
        uv) opts+=(download "$(t 'Скачать uv (astral.sh, в ~/.local/bin)' 'Download uv (astral.sh, into ~/.local/bin)')") ;;
        connect) opts+=(download "$(t 'Скачать с AnkiWeb и поставить в Anki' 'Download from AnkiWeb and add to Anki')") ;;
        engine) opts+=(download "$(t "Скачать GPT-SoVITS $GSV_REF (~6 ГБ) в" "Download GPT-SoVITS $GSV_REF (~6 GB) into") $DATA") ;;
        anki)
            [ -n "$pk" ] && opts+=(pkg "$(t 'Поставить пакетом:' 'Install the package:') $(pm_cmd) $pk")
            command -v flatpak >/dev/null 2>&1 && opts+=(flatpak "$(t 'Поставить из Flathub (flatpak net.ankiweb.Anki)' 'Install from Flathub (flatpak net.ankiweb.Anki)')") ;;
        gpu) ;;
        *) [ -n "$pk" ] && [ -n "$(pm_cmd)" ] && opts+=(pkg "$(t 'Поставить пакетом:' 'Install the package:') $(pm_cmd) $pk") ;;
    esac
    [ "$k" != gpu ] && opts+=(path "$(t 'Уже установлено — указать папку' 'Already installed — point to its folder')")
    if [ "${REQUIRED[$k]}" = 1 ]; then
        opts+=(abort "$(t 'Отменить установку' 'Cancel installation')")
    else
        opts+=(skip "$(t 'Пропустить (можно поставить позже)' 'Skip (can be installed later)')")
    fi
    if [ "$k" = gpu ]; then ACTION[gpu]=skip; FORCE_CPU=1; return; fi
    while :; do
        ui_menu "${NAME_OF[$k]}" "$(t 'Не найдено' 'Not found')${HINT[$k]:+ — ${HINT[$k]}}. $(t 'Что сделать?' 'What should we do?')" "${opts[@]}"
        case "$REPLY" in
            abort) die "$(t 'установка отменена' 'installation cancelled')" ;;
            path)
                ui_input "$(path_hint "$k")" ""
                local d="${REPLY/#\~/$HOME}"
                [ -z "$d" ] && continue
                d="$(realpath -m "$d")"
                if check_user_dir "$k" "$d"; then
                    ACTION[$k]=path; USERDIR[$k]="$d"; return
                fi
                warn "$d: $(t 'тут нет нужного' 'this is not it') ($(path_hint "$k"))"
                [ "$TUI" = 1 ] && interactive && whiptail --title AnkiVoice --msgbox "$d: $(t 'тут нет нужного' 'this is not it') — $(path_hint "$k")" 0 0 < /dev/tty > /dev/tty 2>&1
                interactive || die "$d: $(path_hint "$k")" ;;
            *) ACTION[$k]="$REPLY"; return ;;
        esac
    done
}

ask_data_dir() {
    local need=6; [ "${STATE[engine]}" != ok ] && [ "${ACTION[engine]:-}" = download ] && need=12
    local fg; fg="$(free_gb "$(dirname "$DATA")")"
    if [ "${fg:-0}" -lt "$need" ]; then
        warn "$(t "мало места: нужно ~$need ГБ, свободно ${fg:-?} ГБ в" "low disk space: ~$need GB needed, ${fg:-?} GB free in") $(dirname "$DATA")"
        if ui_yesno "$(t 'Положить окружения и движок на другой диск?' 'Put the environments and the engine on another drive?')" y; then
            ui_input "$(t 'Папка (например /mnt/data/AnkiVoice)' 'Folder (e.g. /mnt/data/AnkiVoice)')" ""
            [ -n "$REPLY" ] && DATA="$(realpath -m "${REPLY/#\~/$HOME}")"
        fi
    fi
}

plan_and_confirm() {
    PKGS=()
    local k lines=() pk
    for k in "${DEPS[@]}"; do
        [ "${STATE[$k]}" = ok ] && continue
        case "${ACTION[$k]:-}" in
            pkg) pk="$(pkgs_for "$k")"; PKGS+=($pk); lines+=("• ${NAME_OF[$k]}: $(t 'пакет' 'package') $pk") ;;
            flatpak) lines+=("• ${NAME_OF[$k]}: flatpak install flathub net.ankiweb.Anki") ;;
            download) lines+=("• ${NAME_OF[$k]}: $(t 'скачать' 'download')") ;;
            path) lines+=("• ${NAME_OF[$k]}: $(t 'использовать' 'use') ${USERDIR[$k]}") ;;
            skip) lines+=("• ${NAME_OF[$k]}: $(t 'пропустить' 'skip')") ;;
        esac
    done
    [ "$FORCE_CPU" = 1 ] && lines+=("• PyTorch: $(t 'версия для процессора (без CUDA)' 'CPU build (no CUDA)')")
    lines+=("• $(t 'Окружения Python и данные:' 'Python environments and data:') $DATA")
    [ "$NEED_CLONE" = 1 ] && lines+=("• AnkiVoice: git clone $REPO_URL → $APP_DIR")
    local text; text="$(printf '%s\n' "${lines[@]}")"
    [ ${#PKGS[@]} -gt 0 ] && text+=$'\n'"$(t 'Команда:' 'Command:') $(pm_cmd) ${PKGS[*]}"
    step "$(t 'План установки' 'Installation plan')"
    printf '%s\n' "$text" | sed 's/^/  /'
    [ "$MODE" = dry-run ] && { info "$(t '--dry-run: ничего не меняю' '--dry-run: nothing is changed')"; exit 0; }
    ui_yesno "$text"$'\n\n'"$(t 'Начать установку?' 'Start the installation?')" y || die "$(t 'установка отменена' 'installation cancelled')"
}

# ------------------------------------------------------------ удаление
if [ "$MODE" = uninstall ]; then
    step "$(t 'Удаление AnkiVoice' 'Uninstalling AnkiVoice')"
    rm -f "$BIN/ankivoice" "${XDG_DATA_HOME:-$HOME/.local/share}/applications/ankivoice.desktop"
    ok "$(t 'команда и ярлык удалены' 'command and menu entry removed')"
    if [ -d "$DATA" ] && ui_yesno "$(t "Удалить окружения, скачанный движок и программу в $DATA?" "Remove the environments, the downloaded engine and the program in $DATA?")" n; then
        rm -rf "$DATA"; ok "$DATA $(t 'удалено' 'removed')"
    fi
    if [ -d "$CONF" ] && ui_yesno "$(t "Удалить настройки и историю ($CONF)?" "Remove settings and history ($CONF)?")" n; then
        rm -rf "$CONF"; ok "$CONF $(t 'удалено' 'removed')"
    fi
    info "$(t 'Anki, AnkiConnect и озвученные карточки не тронуты.' 'Anki, AnkiConnect and voiced cards are untouched.')"
    exit 0
fi

# ------------------------------------------------- 1. проверка и вопросы
detect_all
print_report
[ "$MODE" = check ] && exit 0

if [ "$ASSUME_YES" = 1 ] || ! interactive; then
    # без вопросов: всё недостающее ставим тем, что умеем, необязательное — пропускаем
    for k in "${DEPS[@]}"; do
        [ "${STATE[$k]}" = ok ] && continue
        [ -n "${ACTION[$k]:-}" ] && continue
        case "$k" in
            uv|engine) ACTION[$k]=download ;;
            connect) ACTION[$k]=$([ "${STATE[anki]}" = ok ] && echo download || echo skip) ;;
            gpu) ACTION[$k]=skip; FORCE_CPU=1 ;;
            anki) ACTION[$k]=skip ;;
            *) if [ -n "$(pkgs_for "$k")" ] && [ -n "$(pm_cmd)" ]; then ACTION[$k]=pkg
               elif [ "${REQUIRED[$k]}" = 1 ]; then die "$(t 'поставь вручную:' 'install by hand:') ${NAME_OF[$k]}"
               else ACTION[$k]=skip; fi ;;
        esac
    done
else
    step "$(t 'Чего не хватает — выбери, что сделать' 'What is missing — choose what to do')"
    for k in "${DEPS[@]}"; do
        [ "${STATE[$k]}" = ok ] && continue
        [ -n "${ACTION[$k]:-}" ] && continue
        if [ "$k" = connect ] && [ "${STATE[anki]}" != ok ] && [ "${ACTION[anki]:-}" = skip ]; then
            ACTION[connect]=skip; continue
        fi
        ask_dep "$k"
    done
fi
ask_data_dir
plan_and_confirm

# ------------------------------------------------- 2. выполняем план
mkdir -p "$DATA" "$CONF" "$BIN"
GSV_VENV="$DATA/gsv-venv"          # для своей папки движка (может быть на NTFS)
for k in "${DEPS[@]}"; do
    if [ "${ACTION[$k]:-}" = path ]; then
        case "$k" in
            git|curl|ffmpeg|uv|build) EXTRA_PATH="${EXTRA_PATH:+$EXTRA_PATH:}${USERDIR[$k]}" ;;
            anki) [ -f "${USERDIR[$k]}/prefs21.db" ] && ANKI2_DIR="${USERDIR[$k]}" ;;
            connect) ANKI2_DIR="${USERDIR[$k]}" ;;
            engine) ENGINE="${USERDIR[$k]}" ;;
        esac
    fi
done
[ -n "$EXTRA_PATH" ] && export PATH="$EXTRA_PATH:$PATH"

if [ ${#PKGS[@]} -gt 0 ]; then
    step "$(t 'Системные пакеты' 'System packages')"
    pm_refresh || warn "$(t 'не удалось обновить список пакетов' 'could not refresh package lists')"
    # shellcheck disable=SC2046
    $(pm_cmd) "${PKGS[@]}" || die "$(t 'не удалось поставить системные пакеты' 'could not install system packages')"
    ok "${PKGS[*]}"
fi
if [ "${ACTION[anki]:-}" = flatpak ]; then
    flatpak install -y --user flathub net.ankiweb.Anki || warn "$(t 'Anki из Flathub не поставился — поставь позже' 'Anki from Flathub failed — install it later')"
    ANKI2_DIR="${ANKI2_DIR:-$HOME/.var/app/net.ankiweb.Anki/data/Anki2}"
fi
for c in ffmpeg cc c++ make cmake; do
    command -v "$c" >/dev/null 2>&1 || die "$(t "всё ещё нет $c — поставь его и запусти установщик снова" "$c is still missing — install it and run the installer again")"
done

# ---------------------------------------------------------------- uv
step "$(t 'uv (менеджер Python)' 'uv (Python manager)')"
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null \
        || die "$(t 'не удалось поставить uv' 'could not install uv')"
fi
UV="$(command -v uv)"
ok "uv: $("$UV" --version)"
export UV_HTTP_TIMEOUT="${UV_HTTP_TIMEOUT:-300}"

# ------------------------------------------------------ сама программа
step "AnkiVoice"
if [ "$NEED_CLONE" = 1 ]; then
    git clone --depth 1 --branch "$REPO_BRANCH" "$REPO_URL" "$APP_DIR" \
        || die "$(t 'не удалось скачать' 'could not download') $REPO_URL"
elif [ -d "$APP_DIR/.git" ] && [ "$APP_DIR" = "$DATA/app" ]; then
    # --autostash: свои голоса в app/voices.json не мешают обновлению
    git -C "$APP_DIR" pull --rebase --autostash -q || warn "$(t 'git pull не удался — работаю с тем, что есть' 'git pull failed — using what is there')"
fi
chmod +x "$APP_DIR/install.sh" "$APP_DIR/pipeline.sh" "$APP_DIR/run.sh" 2>/dev/null || true
ok "$(t 'папка программы' 'program folder'): $APP_DIR"

step "$(t 'Python для чтения японского (pyruntime)' 'Python for Japanese text (pyruntime)')"
PYRT="$APP_DIR/pyruntime"
if [ ! -x "$PYRT/bin/python" ]; then
    "$UV" venv -q --python 3.12 "$PYRT" || die "$(t 'не удалось создать' 'could not create') $PYRT"
fi
"$UV" pip install -q --python "$PYRT/bin/python" -r "$APP_DIR/requirements.txt" \
    || die "$(t 'не удалось поставить зависимости pyruntime' 'could not install pyruntime dependencies')"
"$PYRT/bin/python" -c "import haqumei, sudachipy, sudachidict_core, e2k" \
    || die "$(t 'pyruntime собран не полностью' 'pyruntime is incomplete')"
ok "Haqumei, SudachiPy"

# ---------------------------------------------------------- AnkiConnect
if [ "${ACTION[connect]:-}" = download ]; then
    step "AnkiConnect"
    A2=""
    while IFS= read -r d; do [ -d "$d" ] && { A2="$d"; break; }; done < <(anki2_candidates)
    A2="${A2:-${XDG_DATA_HOME:-$HOME/.local/share}/Anki2}"
    TMPZ="$(mktemp --suffix=.zip)"
    if curl -fsSL -o "$TMPZ" "$ANKICONNECT_URL" && [ -s "$TMPZ" ]; then
        mkdir -p "$A2/addons21/$ANKICONNECT_CODE"
        "$PYRT/bin/python" -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
            "$TMPZ" "$A2/addons21/$ANKICONNECT_CODE" \
            && ok "$(t 'поставлено в' 'installed into') $A2/addons21/$ANKICONNECT_CODE — $(t 'перезапусти Anki' 'restart Anki')" \
            || warn "$(t 'не распаковалось — поставь в Anki: Инструменты → Дополнения → Получить → ' 'could not unpack — in Anki: Tools → Add-ons → Get Add-ons → ')$ANKICONNECT_CODE"
        ANKI2_DIR="${ANKI2_DIR:-$A2}"
    else
        warn "$(t 'AnkiWeb не ответил — поставь в Anki: Инструменты → Дополнения → Получить → ' 'AnkiWeb did not answer — in Anki: Tools → Add-ons → Get Add-ons → ')$ANKICONNECT_CODE"
    fi
    rm -f "$TMPZ"
fi

# -------------------------------------------- движок GPT-SoVITS
GSV_DOWNLOADED=0
if [ "${ACTION[engine]:-}" = download ]; then
    step "$(t 'Скачиваю GPT-SoVITS' 'Downloading GPT-SoVITS') $GSV_REF"
    ENGINE="$DATA/GPT-SoVITS"
    if [ -d "$ENGINE/.git" ]; then ok "$(t 'исходники уже скачаны' 'sources already downloaded'): $ENGINE"
    else git clone --depth 1 --branch "$GSV_REF" "$GSV_REPO" "$ENGINE" || die "$(t 'не удалось скачать GPT-SoVITS' 'could not download GPT-SoVITS')"; fi
    GSV_DOWNLOADED=1
fi
case "$ENGINE" in
    "$DATA"/*)
        # движок, скачанный нами, — со своим окружением рядом: требования у
        # версий движка разные, общий gsv-venv сломал бы уже настроенную папку
        GSV_VENV="$ENGINE/.venv"
        [ -d "$ENGINE/.git" ] && GSV_DOWNLOADED=1 ;;
esac

if [ -n "$ENGINE" ] && is_engine "$ENGINE"; then
    ok "$(t 'движок' 'engine'): $ENGINE"
    step "$(t 'Python-окружение движка (первый раз — 5–15 минут)' 'Engine Python environment (first time: 5–15 minutes)')"
    if [ "$FORCE_CPU" = 0 ] && command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
        TORCH_INDEX="$TORCH_CUDA_INDEX"; DEVICE="cuda"
        ok "NVIDIA: $(nvidia-smi -L | head -1 | sed 's/ (UUID.*//')"
    else
        TORCH_INDEX="$TORCH_CPU_INDEX"; DEVICE="cpu"
        warn "$(t 'torch для процессора (синтез будет медленнее)' 'CPU torch (synthesis will be slower)')"
    fi
    if [ ! -x "$GSV_VENV/bin/python" ]; then
        "$UV" venv -q --python 3.10 "$GSV_VENV" || die "$(t 'не удалось создать' 'could not create') $GSV_VENV"
    fi
    GPY="$GSV_VENV/bin/python"
    if ! "$GPY" -c "import torch, sys; sys.exit(0 if torch.__version__.startswith('$TORCH_VER') else 1)" 2>/dev/null; then
        "$UV" pip install --python "$GPY" "torch==$TORCH_VER" "torchaudio==$TORCH_VER" \
            --index-url "$TORCH_INDEX" || die "$(t 'не удалось поставить torch' 'could not install torch')"
    fi
    TMPC="$(mktemp)"
    trap 'rm -f "$TMPC"' EXIT
    "$PYRT/bin/python" "$APP_DIR/linux/engine_constraints.py" "$ENGINE" > "$TMPC"
    printf 'torch==%s\ntorchaudio==%s\n' "$TORCH_VER" "$TORCH_VER" >> "$TMPC"
    # pyopenjtalk собирается из исходников; его CMakeLists старше 3.5 —
    # без этой переменной CMake 4 отказывается его конфигурировать.
    # Ставим его отдельным шагом: uv собирает в закешированной папке
    # исходников, и если там осталась неудачная сборка (config.h без
    # HAVE_FCNTL_H — «O_RDONLY was not declared»), она повторяется вечно.
    # Тогда чистим кеш пакета и собираем заново.
    export CMAKE_POLICY_VERSION_MINIMUM=3.5
    if ! "$GPY" -c "import pyopenjtalk" 2>/dev/null; then
        if ! "$UV" pip install -q --python "$GPY" "pyopenjtalk>=0.4.1" "numpy<2"; then
            warn "$(t 'pyopenjtalk не собрался — чищу кеш и пробую ещё раз' 'pyopenjtalk failed to build — clearing its cache and retrying')"
            "$UV" cache clean pyopenjtalk >/dev/null 2>&1 || true
            "$UV" pip install --python "$GPY" "pyopenjtalk>=0.4.1" "numpy<2" \
                || die "$(t 'pyopenjtalk не собирается (нужны gcc, g++, cmake)' 'pyopenjtalk does not build (gcc, g++, cmake are needed)')"
        fi
    fi
    "$UV" pip install --python "$GPY" \
        -r "$ENGINE/requirements.txt" -c "$TMPC" \
        --index-strategy unsafe-best-match --extra-index-url "$TORCH_INDEX" \
        || die "$(t 'не удалось поставить зависимости GPT-SoVITS (см. вывод выше)' 'could not install GPT-SoVITS dependencies (see above)')"
    if [ -f "$ENGINE/extra-req.txt" ]; then
        CMAKE_POLICY_VERSION_MINIMUM=3.5 "$UV" pip install --python "$GPY" \
            -r "$ENGINE/extra-req.txt" -c "$TMPC" --no-deps || true
    fi
    "$GPY" -c "import torch, pyopenjtalk, fastapi, transformers" \
        || die "$(t 'окружение движка собрано не полностью' 'the engine environment is incomplete')"
    ok "torch $("$GPY" -c 'import torch;print(torch.__version__)'), $DEVICE"

    if [ "$GSV_DOWNLOADED" = 1 ]; then
        step "$(t 'Предобученные модели GPT-SoVITS (HuggingFace lj1995/GPT-SoVITS)' 'GPT-SoVITS pretrained models (HuggingFace lj1995/GPT-SoVITS)')"
        "$GPY" - "$ENGINE/GPT_SoVITS/pretrained_models" <<'PY' || die "models"
import fnmatch, os, sys
from huggingface_hub import HfApi, hf_hub_download
# качаем только недостающее: общие модели можно заранее скопировать из
# другой папки движка (snapshot_download перекачал бы их целиком)
dest, repo = sys.argv[1], "lj1995/GPT-SoVITS"
want = ["chinese-hubert-base/*", "chinese-roberta-wwm-ext-large/*",
        "gsv-v2final-pretrained/*", "s1v3.ckpt",
        "v2Pro/s2Gv2Pro.pth", "v2Pro/s2Gv2ProPlus.pth", "sv/*"]
files = [f for f in HfApi().list_repo_files(repo)
         if any(fnmatch.fnmatch(f, w) for w in want)]
for f in files:
    if os.path.isfile(os.path.join(dest, f)):
        continue
    print("  ->", f, flush=True)
    hf_hub_download(repo, f, local_dir=dest)
PY
        for d in GPT_weights_v2Pro GPT_weights_v2ProPlus SoVITS_weights_v2Pro SoVITS_weights_v2ProPlus; do
            mkdir -p "$ENGINE/$d"
        done
        # v2Pro/v2ProPlus в половинной точности (fp16) на CUDA дают NaN, и
        # вокодер отдаёт сплошную тишину (проверено на RTX 3060) — считаем в fp32
        CFGY="$ENGINE/GPT_SoVITS/configs/tts_infer.yaml"
        if [ -f "$CFGY" ] && sed -n '/^custom:/,/^[^ ]/p' "$CFGY" | grep -q '^  is_half: true'; then
            sed -i '/^custom:/,/^[^ ]/ s/^  is_half: true/  is_half: false/' "$CFGY"
            ok "fp32 ($(t 'в fp16 голоса v2Pro выходят тишиной' 'v2Pro voices are silent in fp16'))"
        fi
    fi

    # прогрев: словарь Open JTalk и данные NLTK качаются один раз
    ( cd "$ENGINE" && "$GPY" - <<'PY' ) || warn "$(t 'прогрев не удался — данные скачаются при первом синтезе' 'warm-up failed — data will download on first synthesis')"
import pyopenjtalk
pyopenjtalk.g2p("試験")
try:
    import nltk
    for pkg in ("averaged_perceptron_tagger", "averaged_perceptron_tagger_eng", "cmudict"):
        nltk.download(pkg, quiet=True)
except Exception:
    pass
PY
    if [ "$DEVICE" = cpu ] && [ -f "$ENGINE/GPT_SoVITS/configs/tts_infer.yaml" ]; then
        warn "$(t 'на CPU выстави в GPT_SoVITS/configs/tts_infer.yaml: device: cpu, is_half: false' 'on CPU set in GPT_SoVITS/configs/tts_infer.yaml: device: cpu, is_half: false')"
    fi
    printf '%s\n' "$ENGINE" > "$APP_DIR/app/gptsovits_path.txt"
else
    GPY=""
    warn "$(t 'движок не настроен: позже — ./install.sh --engine ПАПКА или --download-engine' 'engine not set up: later run ./install.sh --engine FOLDER or --download-engine')"
fi

# --- конфиг приложения: движок, его Python, нестандартные папки
"$PYRT/bin/python" - "$CONF/config.json" "${ENGINE:-}" "${GPY:-}" "${ANKI2_DIR:-}" "$EXTRA_PATH" "$UI_LANG" <<'PY'
import json, os, sys
p, eng, py, anki2, extra, lang = sys.argv[1:7]
try:
    cfg = json.load(open(p, encoding="utf-8"))
except Exception:
    cfg = {}
if eng and py:
    cfg["gptsovits_path"] = eng
    cfg["gptsovits_python"] = py
if anki2:
    cfg["anki2_dir"] = anki2
if extra:
    cfg["extra_path"] = extra
cfg.setdefault("lang", "ru" if lang == "ru" else cfg.get("lang") or "")
if not cfg["lang"]:
    del cfg["lang"]                     # язык выберет сама программа (по системе)
os.makedirs(os.path.dirname(p), exist_ok=True)
tmp = p + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
os.replace(tmp, p)
PY
ok "$(t 'настройки:' 'settings:') $CONF/config.json"

# ------------------------------------------------ команда и ярлык
step "$(t 'Команда ankivoice и ярлык' 'The ankivoice command and menu entry')"
cat > "$BIN/ankivoice" <<EOF
#!/usr/bin/env bash
# AnkiVoice — запуск (создан install.sh)
APP="$APP_DIR"
${EXTRA_PATH:+export PATH="$EXTRA_PATH:\$PATH"   # программы на других дисках (выбрано в установщике)}
case "\${1:-}" in
    pipeline|cli) shift; exec "\$APP/pipeline.sh" "\$@" ;;
    doctor)       shift; exec "\$APP/pyruntime/bin/python" "\$APP/app/anki_gui.py" doctor "\$@" ;;
    classic)      shift; exec "\$APP/pyruntime/bin/python" "\$APP/app/anki_gui.py" --classic "\$@" ;;
    update)       shift
                  if [ -d "\$APP/.git" ]; then git -C "\$APP" pull --rebase --autostash || exit 1; fi
                  exec "\$APP/install.sh" --update "\$@" ;;
    uninstall)    shift; exec "\$APP/install.sh" --uninstall "\$@" ;;
    -h|--help)    echo "ankivoice [--no-open] [--port N]  — web UI"
                  echo "ankivoice pipeline <command>      — console (list, voice, test, selftest, ...)"
                  echo "ankivoice doctor                  — diagnostics"
                  echo "ankivoice update                  — update the program and environments"
                  echo "ankivoice uninstall               — remove AnkiVoice"
                  exit 0 ;;
    *)            exec "\$APP/pyruntime/bin/python" "\$APP/app/anki_gui.py" "\$@" ;;
esac
EOF
chmod +x "$BIN/ankivoice"
ok "$BIN/ankivoice"
case ":$ORIG_PATH:" in
    *":$BIN:"*) ;;
    *)
        # папки команды нет в PATH: без этого `ankivoice` в терминале не найдётся
        case "$(basename "${SHELL:-bash}")" in
            zsh)  RC="$HOME/.zshrc"; LINE="export PATH=\"$BIN:\$PATH\"" ;;
            fish) RC="$HOME/.config/fish/config.fish"; LINE="fish_add_path \"$BIN\"" ;;
            *)    RC="$HOME/.bashrc"; LINE="export PATH=\"$BIN:\$PATH\"" ;;
        esac
        if grep -qsF "$LINE" "$RC"; then
            ok "PATH: $RC"
        elif ui_yesno "$(t "Добавить $BIN в PATH (строка в $RC)?" "Add $BIN to PATH (a line in $RC)?")" y; then
            mkdir -p "$(dirname "$RC")"
            printf '\n# AnkiVoice: ankivoice command\n%s\n' "$LINE" >> "$RC"
            ok "PATH → $RC ($(t 'открой новый терминал' 'open a new terminal'))"
        else
            warn "$(t 'добавь в' 'add to') $RC: $LINE"
        fi
        ;;
esac

if [ "$DESKTOP" = 1 ]; then
    APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
    mkdir -p "$APPS"
    cat > "$APPS/ankivoice.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=AnkiVoice
Comment=Voice Anki cards with GPT-SoVITS voices
Comment[ru]=Озвучка карточек Anki голосами GPT-SoVITS
Exec=$BIN/ankivoice
Icon=$APP_DIR/doc/logo.svg
Terminal=false
Categories=Education;Audio;
EOF
    ok "$(t 'ярлык в меню приложений' 'menu entry'): AnkiVoice"
fi

# ------------------------------------------------------- проверка
step "$(t 'Самопроверка' 'Self-check')"
"$BIN/ankivoice" doctor || warn "$(t 'есть замечания (см. выше) — Anki с AnkiConnect должен быть запущен' 'there are remarks (see above) — Anki with AnkiConnect must be running')"

printf '\n%s%s%s %s %sankivoice%s\n' "$C_G" "$(t 'Готово.' 'Done.')" "$C_0" "$(t 'Запуск:' 'Run:')" "$C_B" "$C_0"
for k in "${DEPS[@]}"; do
    [ "${ACTION[$k]:-}" = skip ] && [ "$k" != gpu ] && \
        info "$(t 'пропущено' 'skipped'): ${NAME_OF[$k]} — ${HINT[$k]:-}"
done
exit 0
