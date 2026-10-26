# -*- coding: utf-8 -*-
"""Модуль транслитерации английских слов и аббревиатур в японскую катакану (e2k).

Интегрирует легкую нейросеть e2k (Patchethium/e2k: RNN на базе Wiktionary и JMdict)
с гибридной обработкой аббревиатур, цифр и IT-терминов.

Логика обработки текста с латиницей:
  1. Нормализация дефисных терминов (Wi-Fi -> ワイファイ).
  2. Смешанные токены (цифры + буквы, например: 3D -> スリーディー, 2D -> ツーディー, 4K -> フォーケー).
  3. Словарь общеупотребительных IT/бизнес-аббревиатур и терминов (IT, AI, USB, CPU, GPU, HTML, etc.).
  4. Проверка через e2k.NGram / эвристики:
     - Аббревиатуры (все заглавные <= 4 букв или не являющиеся английскими словами)
       раскрываются побуквенно по алфавиту (IEC -> アイイーシー, USB -> ユーエスビー).
     - Полноценные английские слова транслитерируются фонетически через e2k.C2K
       (bus -> バス, community -> コミュニティー, coffee -> コーヒー, online -> オンライン).
  5. Грациозный fallback на базовую таблицу LATIN, если e2k недоступен.
"""
import re

# Алфавитное побуквенное чтение латиницы (для аббревиатур)
LATIN = {
    "A": "エー", "B": "ビー", "C": "シー", "D": "ディー", "E": "イー",
    "F": "エフ", "G": "ジー", "H": "エイチ", "I": "アイ", "J": "ジェー",
    "K": "ケー", "L": "エル", "M": "エム", "N": "エヌ", "O": "オー",
    "P": "ピー", "Q": "キュー", "R": "アール", "S": "エス", "T": "ティー",
    "U": "ユー", "V": "ブイ", "W": "ダブリュー", "X": "エックス",
    "Y": "ワイ", "Z": "ゼット",
}

# Специальные аббревиатуры, смешанные токены (цифра+буква) и устоявшиеся чтения
ACRONYMS = {
    # Числовые аббревиатуры и форматы
    "3D": "スリーディー",
    "2D": "ツーディー",
    "4K": "フォーケー",
    "8K": "エイトケー",
    "1ST": "ファースト",
    "2ND": "セカンド",
    "3RD": "サード",
    "4WD": "ヨンダブリューディー",
    "2WD": "ツーダブリューディー",
    "2WAY": "ツーウェイ",
    "3WAY": "スリーウェイ",

    # IT / Технологии
    "IT": "アイティー",
    "AI": "エーアイ",
    "UI": "ユーアイ",
    "UX": "ユーエックス",
    "VR": "ブイアール",
    "AR": "エーアール",
    "MR": "エムアール",
    "PC": "ピーシー",
    "OS": "オーエス",
    "ID": "アイディー",
    "IP": "アイピー",
    "CPU": "シーピーユー",
    "GPU": "ジーピーユー",
    "RAM": "ラム",
    "ROM": "ロム",
    "SSD": "エスエスディー",
    "HDD": "エイチディーディー",
    "USB": "ユーエスビー",
    "HTML": "エイチティーエムエル",
    "CSS": "シーエスエス",
    "JS": "ジェイエス",
    "URL": "ユーアールエル",
    "URI": "ユーアールアイ",
    "API": "エーピーアイ",
    "SDK": "エスディーケー",
    "PDF": "ピーディーエフ",
    "CSV": "シーエスブイ",
    "JSON": "ジェイソン",
    "SQL": "エスキューエル",
    "IOT": "アイオーティー",
    "ICT": "アイシーティー",
    "SNS": "エスエヌエス",
    "PR": "ピーアール",
    "CD": "シーディー",
    "DVD": "ディーブイディー",
    "TV": "テレビ",
    "CEO": "シーイーオー",
    "CTO": "シーティーオー",
    "COO": "シーオーオー",
    "CFO": "シーエフオー",
    "FAQ": "エフエーキュー",
    "B2B": "ビートゥービー",
    "B2C": "ビートゥーシー",
    "EC": "イーシー",
    "DX": "ディーエックス",

    # Сети / Стандарты
    "WIFI": "ワイファイ",
    "WI-FI": "ワイファイ",
    "BLUETOOTH": "ブルートゥース",
    "LAN": "ラン",
    "WAN": "ワン",
    "VPN": "ブイピーエヌ",
    "SSL": "エスエスエル",
    "TLS": "ティーエルエス",
    "HTTP": "エイチティーティーピー",
    "HTTPS": "エイチティーティーピーエス",
    "FTP": "エフティーピー",
    "DNS": "ディーエヌエス",
    "IPX": "アイピーエックス",
    "IEC": "アイイーシー",
    "ISO": "アイエスオー",
    "JIS": "ジス",
    "MACOS": "マックオーエス",

    # Архитектура / ГИС / 3D
    "BIM": "ビム",
    "CIM": "シム",
    "CAD": "キャド",
    "CAM": "キャム",
    "GIS": "ジーアイエス",
    "PLATEAU": "プラトー",
}

# Регулярки
_RE_HYPHEN_WIFI = re.compile(r"(?<![A-Za-z0-9])wi-?fi(?![A-Za-z0-9])", re.IGNORECASE)
_RE_ALPHANUM = re.compile(
    r"(?<![A-Za-z0-9])([0-9]+[A-Za-z]+|[A-Za-z]+[0-9]+)(?![A-Za-z0-9])"
)
_RE_WORDS = re.compile(r"[A-Za-z]+")

# Lazy-loading модели e2k
_c2k_model = None
_ngram_model = None
_e2k_checked = False


def has_e2k():
    """Доступна ли нейросеть e2k в текущем интерпретаторе Python."""
    c2k, _ = _init_e2k()
    return c2k is not None


def _init_e2k():
    """Ленивая инициализация e2k (C2K и NGram)."""
    global _c2k_model, _ngram_model, _e2k_checked
    if _e2k_checked:
        return _c2k_model, _ngram_model
    _e2k_checked = True
    try:
        from e2k import C2K, NGram
        _c2k_model = C2K()
        _ngram_model = NGram()
    except Exception:
        _c2k_model = None
        _ngram_model = None
    return _c2k_model, _ngram_model


def transliterate_en(text):
    """Транслитерировать английский текст в японскую катакану.

    Примеры:
      'community bus' -> 'コミュニティー バス'
      '3Dモデル'      -> 'スリーディーモデル'
      'USBメモリ'     -> 'ユーエスビーメモリ'
      'IT企業'        -> 'アイティー企業'
      'coffee break'  -> 'コーヒー ブレーク'
    """
    if not text or not re.search(r"[A-Za-z0-9]", text):
        return text

    c2k, ngram = _init_e2k()

    # 1. Специфические составные шаблоны с дефисом (Wi-Fi)
    text = _RE_HYPHEN_WIFI.sub("ワイファイ", text)

    # 2. Смешанные буквенно-цифровые токены (3D, 2D, 4K, 1st и т.д.)
    def _repl_alphanum(m):
        raw = m.group(0)
        u = raw.upper()
        if u in ACRONYMS:
            return ACRONYMS[u]
        # Отдельные случаи: <число>D, <число>K, <число>st/nd/rd/th
        m_d = re.match(r"^(\d+)([A-Za-z]+)$", raw)
        if m_d:
            num, sfx = m_d.group(1), m_d.group(2).upper()
            digit_names = {"1": "ワン", "2": "ツー", "3": "スリー", "4": "フォー",
                           "5": "ファイブ", "6": "シックス", "7": "セブン",
                           "8": "エイト", "9": "ナイン"}
            if num in digit_names and sfx in ("D", "K", "G"):
                return digit_names[num] + LATIN.get(sfx, sfx)
        return raw

    text = _RE_ALPHANUM.sub(_repl_alphanum, text)

    # 3. Чистые английские слова и аббревиатуры
    def _repl_word(m):
        return _word(m.group(0))

    def _word(raw):
        u = raw.upper()

        # Словарная аббревиатура/термин
        if u in ACRONYMS:
            return ACRONYMS[u]

        # Строчная буква-приставка перед Словом: iPhone, iPad, iOS, eBay.
        # Целиком e2k читал их как одно слово («iphone» -> イフォン); буква
        # произносится по алфавиту, остальное — как обычное слово.
        m_pre = re.match(r"^([a-z])([A-Z][A-Za-z]*)$", raw)
        if m_pre:
            return LATIN[m_pre.group(1).upper()] + _word(m_pre.group(2))

        # Одиночные буквы (например 'I形' -> 'アイ形')
        if len(raw) == 1:
            return LATIN.get(u, raw)

        # Короткие заглавные аббревиатуры (<= 4 символов, например CPU, USB, IEC)
        # Если NGram говорит, что это не английское произносимое слово
        is_acronym = raw.isupper() and len(raw) <= 4
        if ngram is not None:
            if not ngram(raw.lower()):
                is_acronym = True

        if is_acronym:
            return "".join(LATIN.get(c, c) for c in u)

        # Полноценное английское слово: транслитерируем через C2K
        if c2k is not None:
            try:
                res = c2k(raw.lower())
                if res:
                    return res
            except Exception:
                pass

        # Fallback на побуквенное чтение
        return "".join(LATIN.get(c, c) for c in u)

    text = _RE_WORDS.sub(_repl_word, text)
    return text
