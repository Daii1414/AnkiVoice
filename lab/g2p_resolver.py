# -*- coding: utf-8 -*-
"""
Резолвер чтений: выбирает лучшее чтение для слова из кандидатов,
учитывая контекст предложения, доменный словарь и фуригану.

Логика приоритета (от высокого к низкому):
  1. FURIGANA_VERIFIED — фуригана из ExpressionFurigana, прошла валидацию
  2. DOMAIN_DICT       — запись из доменного словаря колод
  3. HAQUEMEI_PRON     — контекстная произносительная форма Haqumei (с сандхи)
  4. HAQUEMEI_READ     — словарная форма Haqumei
  5. SUDACHI           — резерв
  6. PYOPENJTALK       — резерв для чисел / неизвестных слов
  7. UNKNOWN           — чтение не найдено

При неоднозначности (несколько кандидатов с близкой уверенностью)
резолвер может запросить контекстное разрешение или упаковать слово
как «требует проверки».
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from domain_dict import DomainDictionary
from g2p_candidates import CandidateGenerator
from g2p_provenance import (
    ReadingCandidate,
    ReadingSource,
    best_candidate,
    is_high_confidence,
)


@dataclass
class ResolvedReading:
    """Итоговое разрешенное чтение для одного слова в предложении."""
    surface: str
    reading: str
    source: ReadingSource
    confidence: float
    is_verified: bool
    candidates: list[ReadingCandidate] = field(default_factory=list)
    needs_review: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "surface": self.surface,
            "reading": self.reading,
            "source": self.source.value,
            "confidence": self.confidence,
            "is_verified": self.is_verified,
            "needs_review": self.needs_review,
            "reason": self.reason,
            "candidates": [c.to_dict() for c in self.candidates],
        }


class ReadingResolver:
    """
    Разрешает чтение слова из набора кандидатов.

    Параметры:
      * domain_dict — доменный словарь (высший приоритет после фуриганы)
      * generator   — генератор кандидатов (Haqumei/Sudachi/pyopenjtalk)
      * ambiguity_threshold — разница в уверенности ниже которой
        слово считается неоднозначным и помечается needs_review
    """

    def __init__(
        self,
        domain_dict: Optional[DomainDictionary] = None,
        generator: Optional[CandidateGenerator] = None,
        ambiguity_threshold: float = 0.05,
    ):
        self.domain_dict = domain_dict or DomainDictionary()
        self.generator = generator or CandidateGenerator(
            domain_dict=self.domain_dict
        )
        self.ambiguity_threshold = ambiguity_threshold

    # ------------------------------------------------------------------ main entry
    def resolve(
        self,
        surface: str,
        furigana: Optional[str] = None,
        furigana_verified: bool = False,
        context: Optional[str] = None,
    ) -> ResolvedReading:
        """
        Вернуть итоговое чтение для surface.

        furigana — чтение из ExpressionFurigana (опционально).
        furigana_verified — прошла ли фуригана валидацию
          (соответствует написанию слова, не мусор).
        context — окружение предложения (для будущей модели неоднозначности).
        """
        # 0. Фуригана — источник истины, но только если валидна
        if furigana and furigana_verified:
            return ResolvedReading(
                surface=surface,
                reading=self._normalize_furigana(furigana),
                source=ReadingSource.FURIGANA_VERIFIED,
                confidence=1.0,
                is_verified=True,
                candidates=[ReadingCandidate(
                    surface=surface,
                    reading=self._normalize_furigana(furigana),
                    source=ReadingSource.FURIGANA_VERIFIED,
                    confidence=1.0,
                    is_verified=True,
                )],
                reason="furigana_verified",
            )

        # 1. Кандидаты из генератора (доменный словарь + Haqumei + резервы)
        candidates = self.generator.candidates_for(surface)
        if not candidates:
            return ResolvedReading(
                surface=surface,
                reading="",
                source=ReadingSource.UNKNOWN,
                confidence=0.0,
                is_verified=False,
                needs_review=True,
                reason="no_candidates",
            )

        best = best_candidate(candidates)

        # 2. Проверка неоднозначности: несколько кандидатов с близкой уверенностью
        if len(candidates) > 1:
            gap = candidates[0].confidence - candidates[1].confidence
            if gap < self.ambiguity_threshold:
                # Неоднозначно — помечаем на ревью, но берем лучшего
                return ResolvedReading(
                    surface=surface,
                    reading=best.reading,
                    source=best.source,
                    confidence=best.confidence,
                    is_verified=best.is_verified,
                    candidates=candidates,
                    needs_review=True,
                    reason=f"ambiguous_gap={gap:.3f}",
                )

        # 3. Низкая уверенность — тоже на ревью
        if not is_high_confidence(best, threshold=0.8):
            return ResolvedReading(
                surface=surface,
                reading=best.reading,
                source=best.source,
                confidence=best.confidence,
                is_verified=best.is_verified,
                candidates=candidates,
                needs_review=True,
                reason=f"low_confidence={best.confidence:.2f}",
            )

        return ResolvedReading(
            surface=surface,
            reading=best.reading,
            source=best.source,
            confidence=best.confidence,
            is_verified=best.is_verified,
            candidates=candidates,
            needs_review=False,
            reason="resolved",
        )

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _normalize_furigana(furigana: str) -> str:
        """Привести фуригану к катане для сравнения с чтениями движков."""
        # Фуригана обычно приходит в хирагене; конвертируем в катану
        out = []
        for c in furigana:
            o = ord(c)
            if 0x3041 <= o <= 0x3096:  # хирагана -> катакана (+0x60)
                out.append(chr(o + 0x60))
            else:
                out.append(c)
        return "".join(out)

    # ------------------------------------------------------------------ batch
    def resolve_batch(
        self,
        items: list[dict],
    ) -> list[ResolvedReading]:
        """
        items: список словарей с ключами:
          surface, furigana (opt), furigana_verified (opt), context (opt)
        """
        results = []
        for item in items:
            results.append(self.resolve(
                surface=item["surface"],
                furigana=item.get("furigana"),
                furigana_verified=item.get("furigana_verified", False),
                context=item.get("context"),
            ))
        return results
