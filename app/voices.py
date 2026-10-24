# -*- coding: utf-8 -*-
"""Реестр голосов (voices.json) и их файлы.

load/save/get_voice, пути весов и референсов (относительные считаются
от папки движка), сканирование весов внутри движка.
"""
import json
import os
import re

import av_state
from engines import (DEFAULT_START_CONFIG, ENGINE_INDEX, _norm,
                     _read_app_config, engine_kind, indextts_dir,
                     require_engine)
from paths import CODE

VOICES_FILE = os.path.join(CODE, "voices.json")
ENGINE_LOCAL_FILE = os.path.join(CODE, "gptsovits_path.txt")

# ----------------------------------------------------------- работа с голосами
def load_voices():
    if not os.path.exists(VOICES_FILE):
        return {"start_config": DEFAULT_START_CONFIG, "default_voice": None, "voices": {}}
    try:
        with open(VOICES_FILE, encoding="utf-8") as f:
            cfg = json.load(f)
    except ValueError as e:
        raise SystemExit(
            "voices.json повреждён (сломан JSON): %s\n"
            "Файл: %s\nПочини его или удали — голоса добавятся заново "
            "(pipeline.bat scan --apply)." % (e, VOICES_FILE))
    cfg.setdefault("voices", {})
    cfg.setdefault("start_config", DEFAULT_START_CONFIG)
    return cfg


def save_voices(cfg):
    # запись во временный файл + атомарная замена: обрыв/вылет не портит voices.json
    tmp = VOICES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, VOICES_FILE)


def get_voice(name=None):
    if engine_kind() != ENGINE_INDEX:
        require_engine()          # для IndexTTS движок GPT-SoVITS не нужен
    cfg = load_voices()
    name = name or cfg.get("default_voice")
    if not name:
        raise SystemExit("Голос не задан. Сделай: voice_pipeline.py list")
    if name not in cfg["voices"]:
        raise SystemExit("Голос '%s' не найден. Доступны: %s"
                         % (name, ", ".join(sorted(cfg["voices"])) or "—"))
    v = dict(cfg["voices"][name])
    v["name"] = name
    base = av_state.ENGINE if engine_kind() != ENGINE_INDEX else (indextts_dir() or CODE)
    for key in ("gpt", "sovits", "ref"):
        if v.get(key):
            v[key] = _voice_file(v[key], base)
    v["aux"] = [_voice_file(a, base) for a in v.get("aux") or []]
    return v


def _voice_file(p, base):
    """Путь к файлу голоса: относительный ищем в папке движка, а если там
    нет — в папке другого движка.

    Так сделано, потому что у IndexTTS голос — это референс, а референсы
    часто лежат в папке GPT-SoVITS (там их и нашли при сканировании).
    Раньше IndexTTS искал референс только у себя и голос «Мадара» не работал.
    """
    if not p:
        return p
    p = os.path.expanduser(p)
    if os.path.isabs(p):
        return p
    first = os.path.normpath(os.path.join(base, p))
    if os.path.exists(first):
        return first
    other = _other_engine_dir(base)
    if other:
        alt = os.path.normpath(os.path.join(other, p))
        if os.path.exists(alt):
            return alt
    return first


def _other_engine_dir(base):
    """Папка другого движка (IndexTTS ↔ GPT-SoVITS)."""
    cfg = _read_app_config() or {}
    if base == indextts_dir(cfg):
        return str(cfg.get("gptsovits_path") or "").strip()
    return str(cfg.get("indextts_path") or "").strip()


def ref_duration(path):
    try:
        import soundfile as sf
        info = sf.info(path)
        return info.duration
    except Exception:
        return None

# ------------------------------------------------------ поиск голосов в движке
def _epoch_of(name):
    m = re.search(r"[-_]e(\d+)", name)
    return int(m.group(1)) if m else -1


def _pretty_name(base):
    """MISHIMA_V2 -> Mishima V2"""
    parts = [p for p in re.split(r"[_\-\s]+", base) if p]
    return " ".join(p if p.isdigit() else p[:1].upper() + p[1:].lower()
                    for p in parts)


def _find_ref_for(engine, base):
    """Референсный файл голоса: ищем в корне движка аудио с именем голоса."""
    token = re.sub(r"[_\-\s]+", "", base).lower()
    if not token:
        return ""
    try:
        names = sorted(os.listdir(engine))
    except OSError:
        return ""
    best = None
    for name in names:
        p = os.path.join(engine, name)
        if not os.path.isfile(p):
            continue
        low = name.lower()
        if os.path.splitext(low)[1] not in (".wav", ".mp3", ".flac"):
            continue
        hay = re.sub(r"[_\-\s]+", "", os.path.splitext(low)[0])
        if token not in hay:
            continue
        score = (2 if low.startswith("ref_main") else
                 1 if low.startswith("ref") else 0)
        if best is None or score > best[0]:
            best = (score, name)
    return best[1] if best else ""


def scan_engine_voices(engine):
    """Обходит папки весов движка и собирает пары GPT(.ckpt) + SoVITS(.pth).

    Папки вида GPT_weights* / SoVITS_weights*; имена файлов: Base-eNN.ckpt и
    Base_eN_sM.pth, base у пары совпадает без учёта регистра. Версии
    (v2Pro / v2ProPlus) между собой НЕ смешиваются. Из эпох берётся самая
    свежая. Возвращает словари с путями относительно engine.
    """
    gpts, sovits = {}, {}
    for sub in sorted(os.listdir(engine)):
        low = sub.lower()
        if not os.path.isdir(os.path.join(engine, sub)):
            continue
        if low.startswith("gpt_weights"):
            bucket, ext = gpts, ".ckpt"
        elif low.startswith("sovits_weights"):
            bucket, ext = sovits, ".pth"
        else:
            continue
        fam = re.sub(r"^(gpt|sovits)_weights", "", low).strip("_") or "default"
        d = os.path.join(engine, sub)
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for fn in names:
            if not fn.lower().endswith(ext):
                continue
            stem = os.path.splitext(fn)[0]
            base = re.sub(r"[-_]e\d+(_s\d+)?$", "", stem).strip()
            if not base:
                continue
            bucket.setdefault((fam, base.lower()), []).append(
                (_epoch_of(fn), os.path.join(sub, fn).replace("\\", "/"), base))

    out, seen = [], set()
    for key in sorted(gpts):
        fam, base_key = key
        if key not in sovits:
            continue                      # нет парного SoVITS — пропускаем
        _, gpt_rel, base = max(gpts[key], key=lambda t: t[0])
        _, sovits_rel, _ = max(sovits[key], key=lambda t: t[0])
        ver = ("v2Pro+" if "plus" in fam else
               "v2Pro" if fam == "v2pro" else
               "" if fam == "default" else fam)
        name = re.sub(r"[^a-z0-9_]+", "_", base_key).strip("_")
        if name in seen:
            name = name + "_" + re.sub(r"[^a-z0-9]+", "", fam)
        seen.add(name)
        out.append({
            "name": name,
            "display": _pretty_name(base) + (" · " + ver if ver else ""),
            "gpt": gpt_rel,
            "sovits": sovits_rel,
            "ref": _find_ref_for(engine, base),
        })
    return out


def _gpt_identity(path):
    """Путь к весам без номера эпохи — для узнавания уже известного голоса.

    'GPT_weights_v2ProPlus/Narator-e45.ckpt' и '.../Narator-e50.ckpt' —
    это один и тот же голос (просто разные эпохи), а не два разных.
    Сравнение по точному пути давало дубли с пустым референсом.
    """
    p = str(path or "").lower().replace("\\", "/")
    return re.sub(r"[-_]e\d+(_s\d+)?\.(ckpt|pth)$", r".\2", p)
