# -*- coding: utf-8 -*-
"""
Тест всей инфраструктуры чтения:
- Система уверенности / provenance (g2p_provenance)
- Доменный словарь с train/holdout (domain_dict)
- Генератор кандидатов (g2p_candidates)
- Резолвер неоднозначностей (g2p_resolver)
- Сравнение Опция 1 (ExpressionFurigana) vs Опция 2 (автомат)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "pylibs"))

from domain_dict import DomainDictionary, ReadingSource
from g2p_provenance import ReadingCandidate, best_candidate, is_high_confidence, confidence_from_delta
from g2p_candidates import CandidateGenerator
from g2p_resolver import ReadingResolver, ResolvedReading

# Подключаем Haqumei для тестов
try:
    from haqumei import Haqumei
    H = Haqumei(revert_long_vowels=True, revert_yotsugana=True)
    H_OK = True
except Exception as e:
    print(f"Haqumei недоступен: {e}")
    H = None
    H_OK = False


def test_provenance():
    print("=" * 60)
    print("ТЕСТ 1: Система уверенности (provenance)")
    print("=" * 60)
    c1 = ReadingCandidate("六百", "ロッピャク", ReadingSource.HAQUEMEI_PRON, 0.92, delta=0)
    c2 = ReadingCandidate("六百", "ロクヒャク", ReadingSource.HAQUEMEI_READ, 0.70, delta=500)
    c3 = ReadingCandidate("生花", "セイカ", ReadingSource.DOMAIN_DICT, 0.97, is_verified=True)
    print(f"  c1: {c1.reading} conf={c1.confidence} source={c1.source.value}")
    print(f"  c2: {c2.reading} conf={c2.confidence} source={c2.source.value}")
    print(f"  c3: {c3.reading} conf={c3.confidence} verified={c3.is_verified}")
    best = best_candidate([c1, c2, c3])
    print(f"  BEST: {best.reading} ({best.source.value}) conf={best.confidence}")
    print(f"  high_conf c1: {is_high_confidence(c1)}")
    print(f"  high_conf c2: {is_high_confidence(c2)}")
    print(f"  confidence_from_delta(0): {confidence_from_delta(0):.3f}")
    print(f"  confidence_from_delta(500): {confidence_from_delta(500):.3f}")
    print(f"  confidence_from_delta(2000): {confidence_from_delta(2000):.3f}")
    assert best.reading == "セイカ", f"Expected セイカ, got {best.reading}"
    print("  ✅ ПРОЙДЕН")


def test_domain_dict():
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Доменный словарь с train/holdout")
    print("=" * 60)
    dd = DomainDictionary()
    dd.add("合印", "アイジルシ", ReadingSource.DOMAIN_DICT, verified=True, example="合印を押す")
    dd.add("仕口", "しくち", ReadingSource.DOMAIN_DICT, verified=False)
    dd.add("六百", "ロッピャク", ReadingSource.DOMAIN_DICT, verified=False)
    print(f" .entries: {len(dd.entries)}")
    print(f"  lookup 合印: {dd.lookup('合印').reading}")
    print(f"  candidate: {dd.candidate('合印')}")

    # train/holdout split
    dd.train_holdout_split(holdout_fraction=0.3, seed=42)
    stats = dd.stats()
    print(f"  stats: {stats}")
    assert stats["split_done"] == True
    assert stats["train"] + stats["holdout"] == stats["total"]
    print(f" 合印 in_train: {dd.in_train('合印')}, in_holdout: {dd.in_holdout('合印')}")

    # Save/load
    dd.save("E:/TTS-проект/lab/test_domain_dict.json")
    dd2 = DomainDictionary().load("E:/TTS-проект/lab/test_domain_dict.json")
    print(f"  loaded entries: {len(dd2.entries)}, 合印={dd2.lookup('合印').reading}")
    assert dd2.lookup("合印").reading == "アイジルシ"
    assert dd2.stats()["split_done"] == True
    print("  ✅ ПРОЙДЕН")


def test_candidates():
    print("\n" + "=" * 60)
    print("ТЕСТ 3: Генератор кандидатов (Haqumei)")
    print("=" * 60)
    if not H_OK:
        print("  ⏭ Пропущен (Haqumei недоступен)")
        return
    dd = DomainDictionary()
    gen = CandidateGenerator(domain_dict=dd, haqumei=H)

    for surface in ["六百", "生花", "合印", "殿"]:
        cands = gen.candidates_for(surface)
        print(f"  {surface}:")
        for c in cands:
            print(f"    - {c.reading} conf={c.confidence:.3f} source={c.source.value} delta={c.delta}")
        best = gen.best(surface)
        print(f"    BEST: {best.reading} ({best.source.value}) conf={best.confidence:.3f}")
    print("  ✅ ПРОЙДЕН")


def test_resolver():
    print("\n" + "=" * 60)
    print("ТЕСТ 4: Резолвер неоднозначностей")
    print("=" * 60)
    if not H_OK:
        print("  ⏭ Пропущен (Haqumei недоступен)")
        return
    dd = DomainDictionary()
    dd.add("合印", "アイジルシ", ReadingSource.DOMAIN_DICT, verified=True)
    gen = CandidateGenerator(domain_dict=dd, haqumei=H)
    resolver = ReadingResolver(domain_dict=dd, generator=gen, ambiguity_threshold=0.05)

    # Case 1: Фуригана валидна (Опция 1)
    r1 = resolver.resolve("合印", furigana="あいじるし", furigana_verified=True)
    print(f"  Case 1 (furigana verified): {r1.reading} source={r1.source.value} conf={r1.confidence} verified={r1.is_verified}")
    assert r1.source == ReadingSource.FURIGANA_VERIFIED
    assert r1.is_verified == True
    assert r1.reading == "アイジルシ"

    # Case 2: Автомат без фуриганы (Опция 2)
    r2 = resolver.resolve("合印", furigana=None, furigana_verified=False)
    print(f"  Case 2 (auto): {r2.reading} source={r2.source.value} conf={r2.confidence:.3f} review={r2.needs_review}")
    # Доменный словарь должен перебить автомат
    assert r2.source == ReadingSource.DOMAIN_DICT

    # Case 3: Неоднозначность (generate candidates с близкой уверенностью)
    #合印 в domain_dict уже есть, так что берем слово без записи
    r3 = resolver.resolve("今日", furigana=None, furigana_verified=False)
    print(f"  Case 3 (今日 auto): {r3.reading} source={r3.source.value} conf={r3.confidence:.3f} review={r3.needs_review}")
    print(f"    candidates: {[(c.reading, round(c.confidence,3)) for c in r3.candidates]}")

    # Case 4: Неизвестное слово
    r4 = resolver.resolve("🌀", furigana=None, furigana_verified=False)
    print(f"  Case 4 (unknown): {r4.reading} source={r4.source.value} review={r4.needs_review}")
    assert r4.source == ReadingSource.UNKNOWN

    print("  ✅ ПРОЙДЕН")


def test_option1_vs_option2():
    print("\n" + "=" * 60)
    print("ТЕСТ 5: Сравнение Опция 1 (ExpressionFurigana) vs Опция 2 (автомат)")
    print("=" * 60)
    if not H_OK:
        print("  ⏭ Пропущен (Haqumei недоступен)")
        return
    dd = DomainDictionary()
    gen = CandidateGenerator(domain_dict=dd, haqumei=H)
    resolver = ReadingResolver(domain_dict=dd, generator=gen)

    # Тестовые случаи: (текст, фуригана, фуригана_верифицирована)
    cases = [
        ("合印", "あいじるし", True),   # Опция 1 должна выиграть
        ("合印", "あいいん", True),     # Опция 1 (другое чтение)
        ("六百", None, False),           # Только опция 2
        ("生花", "いけばな", True),     # Опция 1 (domain override)
        ("今日", None, False),           # Только опция 2
        ("殿", None, False),             # Только опция 2
    ]

    results = []
    for text, furi, verified in cases:
        # Опция 1: с фуриганой
        r_opt1 = resolver.resolve(text, furigana=furi, furigana_verified=verified)
        # Опция 2: только автомат
        r_opt2 = resolver.resolve(text, furigana=None, furigana_verified=False)
        results.append((text, r_opt1, r_opt2))
        match = "✅" if r_opt1.reading == r_opt2.reading else "⚠"
        print(f"  {text:6s} | Opt1(furi={furi}): {r_opt1.reading:10s} ({r_opt1.source.value:20s}) | Opt2(auto): {r_opt2.reading:10s} ({r_opt2.source.value:20s}) | {match}")

    # Подсчет статистики
    opt1_verified = sum(1 for _, r1, _ in results if r1.is_verified)
    opt2_verified = sum(1 for _, _, r2 in results if r2.is_verified)
    print(f"\n  Opt1 verified: {opt1_verified}/{len(results)}")
    print(f"  Opt2 verified: {opt2_verified}/{len(results)}")
    print("  ✅ ПРОЙДЕН")


def main():
    test_provenance()
    test_domain_dict()
    test_candidates()
    test_resolver()
    test_option1_vs_option2()
    print("\n" + "=" * 60)
    print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    print("=" * 60)


if __name__ == "__main__":
    main()


