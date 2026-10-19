# -*- coding: utf-8 -*-
"""
Система уверенности и происхождения (provenance) для каждого чтения.

Каждый кандидат на чтение слова получает:
  * чтение ( kana )
  * источник (provenance): откуда взялось чтение
  * уверенность (0..1): насколько мы уверены, что это правильное чтение
  * флаг верификации: было ли чтение подтверждено фуриганой из ExpressionFurigana

Источники по убыванию приоритета:
  FURIGANA_VERIFIED — фуригана из ExpressionFurigana, прошла валидацию (источник истины)
  DOMAIN_DICT       — доменный словарь из колод (пользовательский, проверенный)
  HAQUEMEI_PRON     — произносительная форма Haqumei (контекстная, с сандхи)
  HAQUEMEI_READ     — словарная форма Haqumei
  SUDACHI           — резервная цепочка Sudachi
  PYOPENJTALK       — резерв pyopenjtalk (числа, неизвестные слова)
  UNKNOWN           — чтения нет, слово помечено как неизвестное
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ReadingSource(Enum):
    FURIGANA_VERIFIED = "furigana_verified"
    DOMAIN_DICT = "domain_dict"
    HAQUEMEI_PRON = "haqumei_pron"
    HAQUEMEI_READ = "haqumei_read"
    SUDACHI = "sudachi"
    PYOPENJTALK = "pyopenjtalk"
    UNKNOWN = "unknown"


# Базовые веса уверенности по источнику (до контекстной коррекции)
SOURCE_BASE_CONFIDENCE = {
    ReadingSource.FURIGANA_VERIFIED: 1.0,
    ReadingSource.DOMAIN_DICT: 0.97,
    ReadingSource.HAQUEMEI_PRON: 0.85,
    ReadingSource.HAQUEMEI_READ: 0.70,
    ReadingSource.SUDACHI: 0.60,
    ReadingSource.PYOPENJTALK: 0.55,
    ReadingSource.UNKNOWN: 0.0,
}


@dataclass
class ReadingCandidate:
    """Один вариант чтения слова с метриками уверенности."""
    surface: str          # как слово escritas в исходном тексте
    reading: str          # чтение в катане
    source: ReadingSource
    confidence: float     # 0.0 .. 1.0
    delta: Optional[float] = None   # delta из Haqumei candidates (чем меньше — тем лучше)
    is_verified: bool = False       # подтверждено фуриганой
    context_notes: str = ""         # почему выбрано/отклонено

    def to_dict(self) -> dict:
        return {
            "surface": self.surface,
            "reading": self.reading,
            "source": self.source.value,
            "confidence": self.confidence,
            "delta": self.delta,
            "is_verified": self.is_verified,
            "context_notes": self.context_notes,
        }


def confidence_from_delta(delta: Optional[float], base: float = 0.85) -> float:
    """
    Преобразует delta Haqumei в уверенность 0..1.

    delta=0 — лучший вариант, confidence = base.
    Чем больше delta — тем ниже уверенность (экспоненциальное затухание).
    """
    if delta is None:
        return base
    import math
    # Каждые +500 delta уменьшают уверенность примерно в 2 раза
    return max(0.0, min(1.0, base * math.exp(-delta / 500.0)))


def best_candidate(candidates: list[ReadingCandidate]) -> Optional[ReadingCandidate]:
    """Вернуть кандидата с наивысшей уверенностью."""
    if not candidates:
        return None
    return max(candidates, key=lambda c: c.confidence)


def is_high_confidence(c: ReadingCandidate, threshold: float = 0.8) -> bool:
    """Чтение можно считать достоверным без дополнительной проверки."""
    return c.confidence >= threshold and c.source != ReadingSource.UNKNOWN
