# -*- coding: utf-8 -*-
"""Пути приложения: где код, где корень, где lab/ и bundled/.

CODE — папка этого кода (app/ в установленном приложении), ROOT — на
уровень выше (там lab/ и bundled/). В репозитории и в установленном виде
раскладка одинаковая — поэтому пути считаются от самого файла.
"""
import os

CODE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CODE)
VOICES_FILE = os.path.join(CODE, "voices.json")
ENGINE_LOCAL_FILE = os.path.join(CODE, "gptsovits_path.txt")


def lab_dir():
    """Папка модулей lab/ — рядом с кодом или на уровень выше (в репозитории)."""
    for p in (os.path.join(CODE, "lab"), os.path.join(ROOT, "lab")):
        if os.path.isdir(p):
            return p
    return os.path.join(CODE, "lab")


def bundled(name):
    """Файл из bundled/ (встроенный Python, словарь Sudachi).

    В репозитории они лежат в bundled/, в установленном приложении — рядом
    с кодом. Ищем в обоих местах.
    """
    for p in (os.path.join(CODE, name), os.path.join(ROOT, "bundled", name)):
        if os.path.isfile(p):
            return p
    return os.path.join(CODE, name)


ENGINE = None             # заполняется resolve_engine() ниже
PYTHON = None             # ENGINE\runtime\python.exe
ACTIVE_VOICE_FILE = None  # ENGINE\logs\active_voice.txt
SERVER_LOG = None         # ENGINE\logs\api_v2_pipeline.log

TTS_HOST, TTS_PORT = "127.0.0.1", 9880
TTS_URL = "http://%s:%d" % (TTS_HOST, TTS_PORT)
DEFAULT_START_CONFIG = os.path.join("GPT_SoVITS", "configs", "tts_infer.yaml")
