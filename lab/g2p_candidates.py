# -*- coding: utf-8 -*-
"""
Генератор кандидатов чтения для слова.

Источники candidates (по убыванию приоритета):
  1. Domain dictionary (если есть запись для этой поверхности)
  2. Haqumei g2p_candidates_detailed (все варианты чтения с delta)
  3. Sudachi (резерв)
  4. pyopenjtalk (резерв для чисел и неизвестных слов)

Возвращает отсортированный по уверенности список ReadingCandidate.
"""

from __future__ import annotations

import re
import sys
from typing import Optional

sys.path.insert(0, r"E:\TTS-проект\lab\pylibs")

from domain_dict import DomainDictionary, ReadingSource
from g2p_provenance import (
    ReadingCandidate,
    best_candidate,
    confidence_from_delta,
    is_high_confidence,
)

try:
    from haqumei import Haqumei
except Exception:
    Haqumei = None  # type: ignore


_KANJI_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\U00020000-\U0002FA1f]")


class CandidateGenerator:
    """Генерирует все возможные чтения для слова с иероглифами."""

    def __init__(
        self,
        domain_dict: Optional[DomainDictionary] = None,
        haqumei: Optional[object] = None,
        sudachi_client=None,
        pyopenjtalk_g2p=None,
    ):
        self.domain_dict = domain_dict or DomainDictionary()
        self.h = haqumei
        self.sudachi_client = sudachi_client
        self.pyopenjtalk_g2p = pyopenjtalk_g2p

    # ------------------------------------------------------------------ main entry
    def candidates_for(self, surface: str) -> list[ReadingCandidate]:
        """Все кандидаты чтения для одной поверхности слова."""
        cands: list[ReadingCandidate] = []

        # 1. Доменный словарь (высший приоритет после фуриганы)
        entry = self.domain_dict.lookup(surface)
        if entry:
            cands.append(
                ReadingCandidate(
                    surface=surface,
                    reading=entry.reading,
                    source=entry.source,
                    confidence=0.97,
                    is_verified=entry.verified,
                    context_notes="domain_dict",
                )
            )
            return cands  # словарь перебивает автомат

        # 2. Иероглифы — Haqumei candidates
        if _KANJI_RE.search(surface) and self.h is not None:
            cands.extend(self._haqumei_candidates(surface))
        elif _KANJI_RE.search(surface):
            # Haqumei недоступен — пробуем Sudachi / pyopenjtalk
            pass

        # 3. Резерв: Sudachi
        if not cands and self.sudachi_client is not None:
            try:
                toks = self.sudachi_client.tokenize(surface)
                if toks:
                    for s, nf, r in toks:
                        if r and r != "?":
                            cands.append(
                                ReadingCandidate(
                                    surface=s,
                                    reading=r,
                                    source=ReadingSource.SUDACHI,
                                    confidence=0.60,
                                    context_notes="sudachi_fallback",
                                )
                            )
            except Exception:
                pass

        # 4. Резерв: pyopenjtalk
        if not cands and self.pyopenjtalk_g2p is not None:
            try:
                r = self.pyopenjtalk_g2p(surface)
                if r:
                    cands.append(
                        ReadingCandidate(
                            surface=surface,
                            reading=r,
                            source=ReadingSource.PYOPENJTALK,
                            confidence=0.55,
                            context_notes="pyopenjtalk_fallback",
                        )
                    )
            except Exception:
                pass

        # 5. Если ничего не нашлось — помечаем неизвестным
        if not cands:
            cands.append(
                ReadingCandidate(
                    surface=surface,
                    reading="",
                    source=ReadingSource.UNKNOWN,
                    confidence=0.0,
                    context_notes="no_reading_found",
                )
            )

        # Сортируем по уверенности (убывание)
        cands.sort(key=lambda c: c.confidence, reverse=True)
        return cands

    # ------------------------------------------------------------------ Haqumei candidates
    def _haqumei_candidates(self, surface: str) -> list[ReadingCandidate]:
        """Все варианты чтения из Haqumei g2p_candidates_detailed."""
        out: list[ReadingCandidate] = []
        try:
            c = self.h.g2p_candidates_detailed(surface)
            for cd in c.candidates:
                # Собираем чтение из всех слов кандидата
                reads = []
                prons = []
                for w in cd.words:
                    reads.append(w.read or "")
                    prons.append(w.pron or "")
                reading_katakana = "".join(reads)
                pron_katakana = "".join(prons)

                # Предпочитаем pron (произносительную форму) если она валидная
                final_reading = pron_katakana if pron_katakana else reading_katakana

                conf = confidence_from_delta(cd.delta, base=0.85)
                out.append(
                    ReadingCandidate(
                        surface=surface,
                        reading=final_reading,
                        source=ReadingSource.HAQUEMEI_PRON,
                        confidence=conf,
                        delta=cd.delta,
                        context_notes=f"haqumei_cand_delta={cd.delta}",
                    )
                )
        except Exception:
            pass
        return out

    # ------------------------------------------------------------------ best choice
    def best(self, surface: str) -> Optional[ReadingCandidate]:
        """Лучший кандидат для поверхности."""
        cands = self.candidates_for(surface)
        return best_candidate(cands)
