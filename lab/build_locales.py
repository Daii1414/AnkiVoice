# -*- coding: utf-8 -*-
"""Переводы интерфейса AnkiVoice: выгрузка строк и сборка модулей языков.

    python lab/build_locales.py extract OUT.json    # строки для переводчика
    python lab/build_locales.py build DIR           # DIR/<код>.json -> модули
    python lab/build_locales.py check               # полнота и подстановки

Источник строк — словарь английского интерфейса (ключ — русский текст
разметки), описания встроенных тем и тексты установщика Windows. Переводчик
получает [{id, ru, en}] и возвращает {id: перевод}; по id перевод ложится на
русский ключ, так что длинные ключи никто не переписывает руками.

Сборка пишет app/locales/<модуль>.py (T = {русский: перевод}) и
installer/messages.iss ([CustomMessages] всех языков установщика).
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "app"), os.path.join(ROOT, "installer")]

import fragile_assets  # noqa: E402
import strings as installer_strings  # noqa: E402
from i18n_en import I18N_EN  # noqa: E402
from locales import CODES  # noqa: E402

# код языка -> модуль app/locales (zh-SG берёт zh_cn + поправки SG)
MODULES = {c: c.lower().replace("-", "_") for c in CODES if c not in ("ru", "en", "zh-SG")}

# код языка -> язык установщика Inno Setup (файл .isl)
INNO = {
    "ru": ("russian", "compiler:Languages\\Russian.isl"),
    "en": ("english", "compiler:Default.isl"),
    "zh-CN": ("chinesesimp", "compiler:Languages\\ChineseSimplified.isl"),
    "zh-TW": ("chinesetrad", "compiler:Languages\\ChineseTraditional.isl"),
    "ja": ("japanese", "compiler:Languages\\Japanese.isl"),
    "ko": ("korean", "compiler:Languages\\Korean.isl"),
    "es": ("spanish", "compiler:Languages\\Spanish.isl"),
    "pt-BR": ("brazilianportuguese", "compiler:Languages\\BrazilianPortuguese.isl"),
    "fr": ("french", "compiler:Languages\\French.isl"),
    "de": ("german", "compiler:Languages\\German.isl"),
    "it": ("italian", "compiler:Languages\\Italian.isl"),
    "nl": ("dutch", "compiler:Languages\\Dutch.isl"),
    "pl": ("polish", "compiler:Languages\\Polish.isl"),
    "cs": ("czech", "compiler:Languages\\Czech.isl"),
    "uk": ("ukrainian", "compiler:Languages\\Ukrainian.isl"),
    "tr": ("turkish", "compiler:Languages\\Turkish.isl"),
    "sv": ("swedish", "compiler:Languages\\Swedish.isl"),
    "th": ("thai", "compiler:Languages\\Thai.isl"),
    "id": ("indonesian", "installer\\languages\\Indonesian.isl"),
    "vi": ("vietnamese", "installer\\languages\\Vietnamese.isl"),
    "hi": ("hindi", "installer\\languages\\Hindi.islu"),
}


def source_items():
    """[{id, ru, en}] — всё, что переводится."""
    items = []
    for i, (ru, en) in enumerate(I18N_EN.items()):
        items.append({"id": "u%d" % i, "ru": ru, "en": en})
    for t in fragile_assets.THEMES:
        d = t.get("desc") or {}
        if d.get("ru"):
            items.append({"id": "t:" + t["id"], "ru": d["ru"], "en": d.get("en", "")})
    for k, ru in installer_strings.RU.items():
        items.append({"id": "i:" + k, "ru": ru, "en": installer_strings.EN[k]})
    return items


def _tail(s):
    """Хвост ключа, который должен сохраниться: пробел или двоеточие —
    так переводчик страницы узнаёт «начало фразы, дальше данные»."""
    m = re.search(r"[\s:]+$", s)
    return m.group(0) if m else ""


def problems(item, text):
    """Почему перевод не годится (пусто — годится)."""
    out = []
    if not isinstance(text, str) or not text.strip():
        return ["пусто"]
    for ph in ("%1", "%2"):
        if (ph in item["en"]) != (ph in text):
            out.append("подстановка " + ph)
    if _tail(item["ru"]).endswith(" ") and not text.endswith((" ", "　")) \
            and not re.search(r"[　-鿿가-힯฀-๿]$", text):
        # префиксный ключ («Голосов: N») — пробел перед данными нужен
        # (в CJK и тайском пробел не пишут — там допустимо без него)
        if item["en"].endswith(" "):
            out.append("потерян пробел в конце")
    if item["ru"].strip().endswith(":") and item["en"].strip().endswith(":") \
            and not text.strip().endswith((":", "：")):
        out.append("потеряно двоеточие")
    return out


def extract(path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(source_items(), f, ensure_ascii=False, indent=0)
    print("%s: %d строк" % (path, len(source_items())))


def _py_dict(name, d):
    lines = ["%s = {" % name]
    for k, v in d.items():
        lines.append("    %s: %s," % (json.dumps(k, ensure_ascii=False),
                                       json.dumps(v, ensure_ascii=False)))
    lines.append("}")
    return "\n".join(lines) + "\n"


def build(src_dir):
    # id -> строка берём из той выгрузки, что видели переводчики: словарь
    # мог пополниться позже, и номера u<N> сдвинулись бы
    snap = os.path.join(src_dir, "source.json")
    if os.path.isfile(snap):
        with open(snap, encoding="utf-8") as f:
            items = json.load(f)
    else:
        items = source_items()
    by_id = {it["id"]: it for it in items}
    inst = {}                                  # код -> {ключ установщика: текст}
    bad = 0
    for code, mod in MODULES.items():
        p = os.path.join(src_dir, code + ".json")
        if not os.path.isfile(p):
            print("нет перевода:", code)
            continue
        with open(p, encoding="utf-8") as f:
            tr = json.load(f)
        ui, inst[code] = {}, {}
        for iid, text in tr.items():
            it = by_id.get(iid)
            if not it:
                continue
            why = problems(it, text)
            if why:
                bad += 1
                print("  %s %s: %s — %r" % (code, iid, ", ".join(why), text[:60]))
                continue
            if iid.startswith("i:"):
                inst[code][iid[2:]] = text
            else:
                ui[it["ru"]] = text
        # строки, добавленные после выгрузки: {русский: {код: перевод}}
        late = os.path.join(src_dir, "late.json")
        if os.path.isfile(late):
            with open(late, encoding="utf-8") as f:
                for ru, per in json.load(f).items():
                    if per.get(code):
                        ui[ru] = per[code]
        missing = [i for i in by_id if i not in tr]
        extra = ""
        if code == "zh-CN":
            sg = os.path.join(src_dir, "zh-SG.json")
            if os.path.isfile(sg):
                with open(sg, encoding="utf-8") as f:
                    sgd = {by_id[i]["ru"]: t for i, t in json.load(f).items()
                           if i in by_id and not i.startswith("i:")
                           and ui.get(by_id[i]["ru"]) != t}      # только отличия
                extra = "\n# сингапурские отличия от материкового\n" + _py_dict("SG", sgd)
        out = os.path.join(ROOT, "app", "locales", mod + ".py")
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write("# -*- coding: utf-8 -*-\n")
            f.write('"""Перевод интерфейса: %s. СГЕНЕРИРОВАНО lab/build_locales.py."""\n\n' % code)
            f.write(_py_dict("T", ui))
            f.write(extra)
        print("%-6s %4d строк, нет: %d -> %s" % (code, len(ui), len(missing),
                                                 os.path.relpath(out, ROOT)))
    write_inno(inst)
    if bad:
        print("отброшено переводов с ошибками: %d" % bad)


def write_inno(inst):
    """installer/messages.iss: [Languages] + [CustomMessages] всех языков."""
    lines = ["; СГЕНЕРИРОВАНО lab/build_locales.py — не править руками.", "",
             "[Languages]"]
    for code, (name, isl) in INNO.items():
        lines.append('Name: "%s"; MessagesFile: "%s"' % (name, isl))
    lines += ["", "[CustomMessages]"]
    for code, (name, _isl) in INNO.items():
        msgs = dict(installer_strings.EN)
        if code == "ru":
            msgs = dict(installer_strings.RU)
        else:
            msgs.update(inst.get(code, {}))
        msgs["AppLang"] = code              # язык интерфейса по умолчанию
        for k, v in msgs.items():
            # в .iss перевод строки запрещён, а %n — это перевод строки Inno
            lines.append("%s.%s=%s" % (name, k, v.replace("\n", " ")))
    path = os.path.join(ROOT, "installer", "messages.iss")
    with open(path, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write("\n".join(lines) + "\n")
    print("установщик: %s (%d языков)" % (os.path.relpath(path, ROOT), len(INNO)))


def check():
    """Полнота модулей языков относительно английского словаря."""
    from locales import table
    fails = 0
    for code in CODES:
        if code in ("ru", "en"):
            continue
        try:
            t = table(code)
        except Exception as e:
            print("FAIL %s: модуль не грузится (%s)" % (code, e))
            fails += 1
            continue
        own = sum(1 for k, v in t.items() if I18N_EN.get(k) != v)
        share = own / float(len(I18N_EN) or 1)
        flag = "OK  " if share > 0.97 else "FAIL"
        if share <= 0.97:
            fails += 1
        print("%s %-6s переведено %d из %d (%.0f%%)" % (flag, code, own, len(I18N_EN), share * 100))
    return fails


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "extract":
        extract(sys.argv[2])
    elif cmd == "build":
        build(sys.argv[2])
    else:
        sys.exit(1 if check() else 0)
