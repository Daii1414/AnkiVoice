# -*- coding: utf-8 -*-
"""
Доменный словарь чтений Japanese (kanji -> kana).

Словарь заполняется из полей Anki (Expression + ExpressionFurigana).
Поддерживает:
  * сохранение/загрузку в JSON
  * train/holdout-сплит (чтобы не тестировать на тех же словах, из которых built словарь)
  * поиск чтения по поверхности слова
  * добавление записей с меткой источника (furigana_verified / domain_mined)
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from typing import Optional

from g2p_provenance import ReadingCandidate, ReadingSource


@dataclass
class DictionaryEntry:
    surface: str          # как написано (например, 合印)
    reading: str          # чтение в катане (например, アイジルシ)
    source: ReadingSource = ReadingSource.DOMAIN_DICT
    verified: bool = False   # подтверждено фуриганой
    count: int = 1          # сколько раз встречено в колодах
    examples: list[str] = field(default_factory=list)  # примеры предложений


class DomainDictionary:
    """Доменный словарь с поддержкой train/holdout-разделения."""

    def __init__(self, path: Optional[str] = None):
        self.path = path
        self.entries: dict[str, DictionaryEntry] = {}  # surface -> entry
        self.train_ids: set[str] = set()
        self.holdout_ids: set[str] = set()
        self._split_done = False

    # ------------------------------------------------------------------ load/save
    def load(self, path: Optional[str] = None) -> "DomainDictionary":
        path = path or self.path
        if not path or not os.path.exists(path):
            return self
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.entries = {}
        for item in data.get("entries", []):
            src = ReadingSource(item.get("source", "domain_dict"))
            entry = DictionaryEntry(
                surface=item["surface"],
                reading=item["reading"],
                source=src,
                verified=item.get("verified", False),
                count=item.get("count", 1),
                examples=item.get("examples", []),
            )
            self.entries[entry.surface] = entry
        self.train_ids = set(data.get("train_ids", []))
        self.holdout_ids = set(data.get("holdout_ids", []))
        self._split_done = bool(self.train_ids or self.holdout_ids)
        return self

    def save(self, path: Optional[str] = None) -> None:
        path = path or self.path
        if not path:
            raise ValueError("path не задан")
        data = {
            "entries": [
                {
                    "surface": e.surface,
                    "reading": e.reading,
                    "source": e.source.value,
                    "verified": e.verified,
                    "count": e.count,
                    "examples": e.examples,
                }
                for e in self.entries.values()
            ],
            "train_ids": sorted(self.train_ids),
            "holdout_ids": sorted(self.holdout_ids),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------ lookup / add
    def lookup(self, surface: str) -> Optional[DictionaryEntry]:
        return self.entries.get(surface)

    def candidate(self, surface: str) -> Optional[ReadingCandidate]:
        e = self.lookup(surface)
        if not e:
            return None
        return ReadingCandidate(
            surface=e.surface,
            reading=e.reading,
            source=e.source,
            confidence=SOURCE_CONFIDENCE[e.source],
            is_verified=e.verified,
            context_notes="domain_dict",
        )

    def add(
        self,
        surface: str,
        reading: str,
        source: ReadingSource = ReadingSource.DOMAIN_DICT,
        verified: bool = False,
        example: Optional[str] = None,
    ) -> None:
        if surface in self.entries:
            e = self.entries[surface]
            e.reading = reading
            e.source = source
            e.verified = e.verified or verified
            e.count += 1
            if example and example not in e.examples:
                e.examples.append(example)
        else:
            self.entries[surface] = DictionaryEntry(
                surface=surface,
                reading=reading,
                source=source,
                verified=verified,
                count=1,
                examples=[example] if example else [],
            )

    # ------------------------------------------------------------------ train / holdout split
    def train_holdout_split(self, holdout_fraction: float = 0.2, seed: int = 42) -> None:
        """
        Разбивает записи на train и holdout.
        holdout — независимая выборка для проверки точности (не попадает в словарь).
        """
        rng = random.Random(seed)
        surfaces = list(self.entries.keys())
        rng.shuffle(surfaces)
        n_holdout = max(1, int(len(surfaces) * holdout_fraction))
        self.holdout_ids = set(surfaces[:n_holdout])
        self.train_ids = set(surfaces[n_holdout:])
        self._split_done = True

    def in_holdout(self, surface: str) -> bool:
        return surface in self.holdout_ids

    def in_train(self, surface: str) -> bool:
        return surface in self.train_ids

    def stats(self) -> dict:
        return {
            "total": len(self.entries),
            "train": len(self.train_ids),
            "holdout": len(self.holdout_ids),
            "verified": sum(1 for e in self.entries.values() if e.verified),
            "split_done": self._split_done,
        }


# Базовые веса уверенности (импорт отсюда, чтобы не было циклической зависимости)
SOURCE_CONFIDENCE = {
    ReadingSource.FURIGANA_VERIFIED: 1.0,
    ReadingSource.DOMAIN_DICT: 0.97,
    ReadingSource.HAQUEMEI_PRON: 0.85,
    ReadingSource.HAQUEMEI_READ: 0.70,
    ReadingSource.SUDACHI: 0.60,
    ReadingSource.PYOPENJTALK: 0.55,
    ReadingSource.UNKNOWN: 0.0,
}

