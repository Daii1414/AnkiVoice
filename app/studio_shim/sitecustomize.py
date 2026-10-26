# -*- coding: utf-8 -*-
"""Подкладывается студии обучения GPT-SoVITS через PYTHONPATH (см. studio.py).

webui.py движка запускает Gradio с server_name="0.0.0.0" — интерфейс с
доступом к файлам и обучению становится виден всей локальной сети. Как
только процесс импортирует gradio, подменяем Blocks.launch: слушать только
127.0.0.1. Действует и на дочерние вкладки студии (они наследуют PYTHONPATH).
"""
import importlib.util
import sys


class _GradioLocalOnly:
    def find_spec(self, name, path=None, target=None):
        if name != "gradio":
            return None
        sys.meta_path.remove(self)
        spec = importlib.util.find_spec(name)
        if spec is None or spec.loader is None:
            return spec
        exec_module = spec.loader.exec_module

        def patched(module):
            exec_module(module)
            launch = module.Blocks.launch

            def local_launch(self, *args, **kwargs):
                kwargs["server_name"] = "127.0.0.1"
                return launch(self, *args, **kwargs)

            module.Blocks.launch = local_launch

        spec.loader.exec_module = patched
        return spec


sys.meta_path.insert(0, _GradioLocalOnly())
