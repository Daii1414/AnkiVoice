# -*- coding: utf-8 -*-
"""Сервис IndexTTS: нормализовать пик, чтобы QC не считал звук обрезанным.

IndexTTS 2.5 выдаёт горячий сигнал (пик около 0.999), и наш QC честно
помечает «обрезка». Нормализуем пик до 0.98 — громкость почти та же, но
верх сигнала не срезан.
"""

NORMALIZE_PEAK = 0.98


def normalize_peak(path, target=NORMALIZE_PEAK):
    """Смягчает пик файла. Возвращает (было, стало) или None."""
    try:
        import numpy as np
        import soundfile as sf
    except Exception:
        return None
    try:
        data, sr = sf.read(path, dtype="float32")
    except Exception:
        return None
    if data.size == 0:
        return None
    peak = float(np.abs(data).max())
    if peak <= target or peak <= 0:
        return (peak, peak)
    data = data * (target / peak)
    try:
        sf.write(path, data, sr)
    except Exception:
        return None
    return (peak, float(np.abs(data).max()))
