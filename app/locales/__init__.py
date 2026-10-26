# -*- coding: utf-8 -*-
"""Языки интерфейса AnkiVoice.

Ключи словарей — русский текст разметки (так устроен переводчик страницы:
он ищет точный текст узла). Английский живёт в i18n_en.py, остальные — в
модулях этой папки (СГЕНЕРИРОВАНЫ lab/build_locales.py из переводов, руками
не правятся). Чего нет в словаре языка, показывается по-английски.

Модули импортируются в table() явными строками: так PyInstaller видит их и
вшивает в exe, а грузятся они только при выборе языка.
"""

# (код, самоназвание, по-английски, язык студии обучения GPT-SoVITS)
LANGS = (
    ("ru", "Русский", "Russian", "ru_RU"),
    ("en", "English", "English", "en_US"),
    ("zh-CN", "简体中文（中国大陆）", "Chinese (Simplified, China)", "zh_CN"),
    ("zh-SG", "简体中文（新加坡）", "Chinese (Simplified, Singapore)", "zh_SG"),
    ("zh-TW", "繁體中文（台灣）", "Chinese (Traditional, Taiwan)", "zh_TW"),
    ("zh-HK", "繁體中文（香港）", "Chinese (Traditional, Hong Kong)", "zh_HK"),
    ("yue", "粵語（廣東話）", "Cantonese", "zh_HK"),
    ("ja", "日本語", "Japanese", "ja_JP"),
    ("ko", "한국어", "Korean", "ko_KR"),
    ("es", "Español", "Spanish", "es_ES"),
    ("pt-BR", "Português (Brasil)", "Portuguese (Brazil)", "pt_BR"),
    ("fr", "Français", "French", "fr_FR"),
    ("de", "Deutsch", "German", "en_US"),
    ("it", "Italiano", "Italian", "it_IT"),
    ("nl", "Nederlands", "Dutch", "en_US"),
    ("pl", "Polski", "Polish", "en_US"),
    ("cs", "Čeština", "Czech", "en_US"),
    ("uk", "Українська", "Ukrainian", "ru_RU"),
    ("tr", "Türkçe", "Turkish", "tr_TR"),
    ("sv", "Svenska", "Swedish", "en_US"),
    ("id", "Bahasa Indonesia", "Indonesian", "en_US"),
    ("vi", "Tiếng Việt", "Vietnamese", "en_US"),
    ("th", "ไทย", "Thai", "en_US"),
    ("hi", "हिन्दी", "Hindi", "en_US"),
)
CODES = tuple(c for c, *_ in LANGS)


def studio_lang(code):
    """Язык интерфейса студии GPT-SoVITS (у неё свой, меньший набор)."""
    for c, _n, _e, s in LANGS:
        if c == code:
            return s
    return "en_US"


def normalize(code):
    """«zh_TW.UTF-8», «pt», «zh-Hant» -> поддерживаемый код или ''."""
    if not code:
        return ""
    c = str(code).split(".")[0].split("@")[0].replace("_", "-").strip()
    low = c.lower()
    for k in CODES:
        if k.lower() == low:
            return k
    if low.startswith("zh"):
        if low.endswith(("-hk", "-mo")):
            return "zh-HK"
        if "hant" in low or low.endswith("-tw"):
            return "zh-TW"
        if low.endswith("-sg"):
            return "zh-SG"
        return "zh-CN"
    if low.startswith("yue"):
        return "yue"
    if low.startswith("pt"):
        return "pt-BR"
    base = low.split("-")[0]
    for k in CODES:
        if k.lower() == base:
            return k
    return ""


def table(code):
    """Словарь языка {русский текст: перевод}; для ru — пустой."""
    from i18n_en import I18N_EN
    if code == "en":
        return dict(I18N_EN)
    if code not in CODES or code == "ru":
        return {}
    if code in ("zh-CN", "zh-SG"):
        from locales import zh_cn as mod
    elif code == "zh-TW":
        from locales import zh_tw as mod
    elif code == "zh-HK":
        from locales import zh_hk as mod
    elif code == "yue":
        from locales import yue as mod
    elif code == "ja":
        from locales import ja as mod
    elif code == "ko":
        from locales import ko as mod
    elif code == "es":
        from locales import es as mod
    elif code == "pt-BR":
        from locales import pt_br as mod
    elif code == "fr":
        from locales import fr as mod
    elif code == "de":
        from locales import de as mod
    elif code == "it":
        from locales import it as mod
    elif code == "nl":
        from locales import nl as mod
    elif code == "pl":
        from locales import pl as mod
    elif code == "cs":
        from locales import cs as mod
    elif code == "uk":
        from locales import uk as mod
    elif code == "tr":
        from locales import tr as mod
    elif code == "sv":
        from locales import sv as mod
    elif code == "id":
        from locales import id as mod
    elif code == "vi":
        from locales import vi as mod
    elif code == "th":
        from locales import th as mod
    else:
        from locales import hi as mod
    # недостающее — по-английски, а не по-русски
    out = dict(I18N_EN)
    out.update(mod.T)
    if code == "zh-SG":
        out.update(getattr(mod, "SG", {}))
    return out
