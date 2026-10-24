# -*- coding: utf-8 -*-
"""Общее изменяемое состояние движка - единственное место, где оно живёт.

ENGINE/PYTHON и компания заполняются resolve_engine() (app/engines.py) и
читаются всеми модулями через av_state.X - так у модулей нет циклов
импорта, а у состояния нет дублирующихся копий.
"""

ENGINE = None             # папка установленного движка или None
PYTHON = None             # ENGINE/runtime/python.exe
ACTIVE_VOICE_FILE = None  # ENGINE/logs/active_voice.txt
SERVER_LOG = None         # ENGINE/logs/api_v2_pipeline.log
