"""Tkinter GUI for starting and inspecting local llama.cpp servers.

Run ``python llama_cpp_gui.py --help`` to see GUI startup options.
"""

from __future__ import annotations

import argparse
import logging
import queue
import shlex
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from config import (
    APP_DIR,
    PROFILE_ORDER,
    RUNTIME_KEYS,
    detect_runtime_paths,
    get_profile,
    load_config,
    profile_display_name,
    runtime_value_is_usable,
    save_config,
)
from llama_cpp_release import BACKEND_CHOICES, read_manifest
from llama_server_manager import LlamaServerManager, format_uptime, tail_file

logger = logging.getLogger("llama_cpp_gui")


TOOLTIPS: dict[str, str] = {
    "Python": "Готовый Python из venv. Обычно менять не нужно.",
    "llama-server": "Бинарник llama.cpp server, который запускает модели.",
    "Working dir": "Рабочая папка запуска. Для вашей сборки это папка build-cuda/bin.",
    "LD library path": "Папка с библиотеками llama.cpp. Без нее llama-server не найдет .so файлы.",
    "llama.cpp backend": "Какой prebuilt release скачать: cpu самый совместимый, vulkan/rocm/openvino/sycl требуют соответствующие драйверы.",
    "Beginner setup": "Создать локальное .venv, установить Python-зависимости и выбрать этот Python для прокси.",
    "Auto-detect runtime": "Найти Python, llama-server, рабочую папку и LD_LIBRARY_PATH автоматически.",
    "Check server version": "Запустить llama-server --version для текущего бинарника.",
    "Check updates": "Проверить последний release llama.cpp на GitHub и сравнить с managed install.",
    "Download llama-server": "Скачать выбранный prebuilt llama-server release и прописать его в Runtime.",
    "Install Python libs": "Установить Python-пакеты из requirements.txt в выбранный Python.",
    "Install system libs": "Открыть терминал и установить системные пакеты, включая Tkinter.",
    "Active profile": "Шаблон настроек для одиночного запуска или нового instance.",
    "Model .gguf": "Файл модели. Для чата выбирайте LLM, для embeddings выбирайте bge/nomic/gte.",
    "MMProj": "Файл проектора для vision/multimodal моделей. Для обычного чата не нужен.",
    "Models dir": "Папка с моделями для router-режима.",
    "Models preset": "INI-файл пресетов router-режима. Можно оставить пустым.",
    "Host": "127.0.0.1 только для этой машины. 0.0.0.0 открывает доступ в локальной сети.",
    "Port": "Номер входа сервера. У разных instances порты должны быть разными.",
    "Model alias": "Имя модели, которое увидит клиент. Например local-llama.",
    "Alias": "Имя модели, которое увидит клиент. Например local-embeddings.",
    "API key": "Пароль для OpenAI-compatible API. Если пусто, ключ не требуется.",
    "Context": "Сколько токенов модель держит в памяти. Больше контекст - больше расход VRAM/RAM.",
    "Threads": "CPU-потоки для генерации. Обычно 4-8 достаточно.",
    "Batch threads": "CPU-потоки для обработки больших пачек. Пусто = как Threads.",
    "GPU layers": "Сколько слоев отправить на GPU. all или -1 = максимум на видеокарту.",
    "Main GPU": "Номер видеокарты: 0 = RTX A4000, 1 = RTX 3050.",
    "Split mode": "Как использовать GPU: none = одна GPU, layer = делить слои между GPU.",
    "Tensor split": "Ручное распределение по GPU, например 3,1. Если не знаете - оставьте пустым.",
    "Batch": "Логический размер пачки. Для bge рекомендуем 8192.",
    "Micro-batch": "Физический размер пачки. Для bge рекомендуем 8192, если хватает памяти.",
    "Flash attention": "Ускорение внимания. auto обычно самый спокойный вариант.",
    "Router max models": "Сколько моделей router может держать загруженными одновременно.",
    "Extra args": "Дополнительные параметры llama-server. Для bge: --pooling cls.",
    "Enabled": "Если включено, instance стартует кнопкой Start enabled.",
    "ID": "Внутреннее имя instance. Лучше латиницей без пробелов.",
    "Name": "Человеческое название строки в таблице.",
    "Profile": "Тип сервера: chat, embeddings, rerank, multimodal или router.",
    "Proxy host": "Адрес, на котором слушает Ollama-compatible proxy.",
    "Proxy port": "Порт proxy. 11435 выбран, чтобы не мешать настоящему Ollama на 11434.",
    "Target OpenAI URL": "Куда proxy пересылает запросы. Пусто = активный llama-server.",
    "Target API key": "Ключ целевого llama-server, если вы включили API key.",
    "Model name": "Имя модели, которое proxy показывает Ollama-клиентам.",
    "mmap": "Быстрая загрузка модели через memory map. Обычно включено.",
    "mlock": "Просить ОС не выгружать модель из памяти. Включайте только если понимаете последствия.",
    "web UI": "Встроенная web-страница llama-server. Для API можно выключить.",
    "continuous batching": "Улучшает параллельную обработку нескольких запросов.",
    "metrics": "Включает endpoint метрик Prometheus.",
    "slots": "Показывает служебную информацию о слотах сервера.",
    "router autoload": "Router сам загружает выбранную модель при запросе.",
    "Start proxy together with server": "Запускать Ollama-compatible proxy вместе с одиночным сервером.",
    "Add": "Добавить новый instance из текущего шаблона.",
    "Duplicate": "Скопировать выбранный instance на новый порт.",
    "Remove": "Удалить выбранный instance и остановить его процесс.",
    "Start selected": "Запустить только выбранную строку.",
    "Stop selected": "Остановить только выбранную строку.",
    "Restart selected": "Перезапустить выбранную строку после изменения настроек.",
    "Start enabled": "Запустить все строки, где Enabled включен.",
    "Stop all": "Остановить все instance-процессы из списка.",
    "Copy URL": "Скопировать OpenAI URL выбранного instance.",
    "Use for proxy": "Назначить выбранный instance целью Ollama-compatible proxy.",
    "Apply to selected": "Сохранить поля редактора в выбранный instance.",
    "Reload selected": "Отменить несохраненные правки и перечитать выбранный instance.",
    "Start": "Запустить одиночный сервер с вкладки Server.",
    "Restart": "Перезапустить одиночный сервер.",
    "Stop": "Остановить одиночный сервер, proxy и все instances.",
    "Open": "Открыть web UI одиночного сервера в браузере.",
    "Save": "Сохранить настройки в config.json.",
    "Copy OpenAI URL": "Скопировать адрес вида http://host:port/v1.",
    "Copy Ollama URL": "Скопировать адрес proxy для Ollama-compatible клиентов.",
    "Quit": "Закрыть управляющее окно. Запущенные процессы лучше остановить заранее.",
    "Refresh devices": "Обновить список видеокарт, которые видит llama.cpp.",
    "Refresh logs": "Перечитать последние строки логов.",
    "Open logs folder": "Открыть папку logs.",
    "Start proxy": "Запустить только Ollama-compatible proxy.",
    "Stop proxy": "Остановить только Ollama-compatible proxy.",
}


HOUSEHOLD_HELP_TEXT = """КАК ПОЛЬЗОВАТЬСЯ ПРОГРАММОЙ БЕЗ ТЕХНИЧЕСКОЙ МАГИИ

1. Что делает программа

Эта программа включает и выключает локальные нейросети llama.cpp.
Модель - это файл .gguf. Сервер - это процесс, который дает другим программам доступ к модели.

2. Самый простой запуск

- Откройте вкладку Instances.
- Выберите строку Chat 8081.
- Проверьте поле Model .gguf.
- Нажмите Apply to selected.
- Нажмите Start selected.
- Когда в таблице появится running, нажмите Copy URL.
- Вставьте этот адрес в Open WebUI как OpenAI-compatible URL.

3. Если нужна модель для поиска по документам

- Выберите строку Embeddings 8082.
- Убедитесь, что Model .gguf указывает на bge-m3-Q8_0.gguf.
- Для BGE уже выставлены рекомендуемые настройки:
  Profile = embeddings
  Context = 8192
  Batch = 8192
  Micro-batch = 8192
  Extra args = --pooling cls
- Нажмите Apply to selected.
- Нажмите Start selected.

4. Как выбрать видеокарту

- Main GPU = 0: NVIDIA RTX A4000.
- Main GPU = 1: NVIDIA GeForce RTX 3050.
- Для одной видеокарты поставьте Split mode = none.
- Если хотите делить модель между видеокартами, поставьте Split mode = layer.

5. Если запускаете несколько моделей

У каждой строки должен быть свой Port:
- Chat: 8081
- Embeddings: 8082
- Rerank: 8083

Не ставьте одинаковый порт двум строкам. Это как пытаться посадить двух людей на один стул.

6. Что нажимать

- Add: добавить новую строку.
- Duplicate: скопировать выбранную строку.
- Apply to selected: сохранить изменения в выбранной строке.
- Start selected: включить выбранную строку.
- Stop selected: выключить выбранную строку.
- Start enabled: включить все строки с галочкой Enabled.
- Stop all: выключить все строки.
- Use for proxy: сделать выбранную строку целью для Ollama-compatible proxy.

7. Если что-то не работает

- Откройте вкладку Logs.
- Нажмите Refresh logs.
- Посмотрите последние строки.

Частые причины:
- выбран не тот .gguf файл;
- не хватает видеопамяти;
- порт уже занят;
- для большой модели слишком большой Context;
- забыли нажать Apply to selected перед Start selected.

8. Главное правило

Для нескольких моделей работайте во вкладке Instances.
Вкладка Server нужна только для одиночного запуска и шаблонов.
"""


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str, delay_ms: int = 450):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id: str | None = None
        self._tip_window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self) -> None:
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self) -> None:
        if self._tip_window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 18
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        except Exception:
            return
        self._tip_window = tk.Toplevel(self.widget)
        self._tip_window.wm_overrideredirect(True)
        self._tip_window.wm_geometry(f"+{x}+{y}")
        label = ttk.Label(
            self._tip_window,
            text=self.text,
            justify=tk.LEFT,
            wraplength=420,
            padding=(8, 5),
            relief=tk.SOLID,
            borderwidth=1,
            background="#fff8dc",
        )
        label.pack()

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._tip_window:
            try:
                self._tip_window.destroy()
            except Exception:
                pass
            self._tip_window = None


class LlamaCppGUI:
    def __init__(self, root: tk.Tk, geometry: str = "1180x820", refresh_devices_on_start: bool = True):
        self.root = root
        self.root.title("llama.cpp Control Deck")
        self.root.geometry(geometry)
        self.config = load_config()
        self.manager = LlamaServerManager(self.config)
        self.current_profile = str(self.config.get("active_profile") or "chat")
        self.profile_names = PROFILE_ORDER[:]

        self.runtime_vars: dict[str, tk.Variable] = {}
        self.profile_vars: dict[str, tk.Variable] = {}
        self.proxy_vars: dict[str, tk.Variable] = {}
        self.instance_vars: dict[str, tk.Variable] = {}
        self.status_vars: dict[str, tk.StringVar] = {}
        self.selected_instance_id: str | None = None
        self._refresh_job: str | None = None
        self._refreshing_instances_table = False
        self._active_scroll_canvas: tk.Canvas | None = None
        self._mousewheel_bound = False

        self._build_ui()
        self._load_runtime_vars()
        self._load_profile_vars(self.current_profile)
        self._load_proxy_vars()
        self._setup_close_handler()
        self.refresh_instances_table(select_first=True)
        if refresh_devices_on_start:
            self.refresh_devices()
        else:
            self.devices_text.insert("1.0", "Device refresh skipped. Use Refresh devices when needed.")
        self.refresh_status()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(self.root)
        notebook.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        server_tab = self._create_scrollable_tab(notebook, "Server")
        instances_tab = self._create_scrollable_tab(notebook, "Instances")
        proxy_tab = self._create_scrollable_tab(notebook, "Ollama proxy")
        devices_tab = ttk.Frame(notebook, padding=10)
        logs_tab = ttk.Frame(notebook, padding=10)
        help_tab = ttk.Frame(notebook, padding=10)
        notebook.add(devices_tab, text="GPU / devices")
        notebook.add(logs_tab, text="Logs")
        notebook.add(help_tab, text="Help")

        self._build_server_tab(server_tab)
        self._build_instances_tab(instances_tab)
        self._build_proxy_tab(proxy_tab)
        self._build_devices_tab(devices_tab)
        self._build_logs_tab(logs_tab)
        self._build_help_tab(help_tab)
        self._build_bottom_bar()

    def _tooltip_text(self, label: str) -> str:
        return TOOLTIPS.get(label, "")

    def _attach_tooltip(self, widget: tk.Widget, label: str, text: str | None = None) -> None:
        tip = text if text is not None else self._tooltip_text(label)
        if tip:
            ToolTip(widget, tip)

    def _button(self, parent, text: str, command=None, **kwargs) -> ttk.Button:
        button = ttk.Button(parent, text=text, command=command, **kwargs)
        self._attach_tooltip(button, text)
        return button

    def _checkbutton(self, parent, text: str, variable: tk.Variable, **kwargs) -> ttk.Checkbutton:
        checkbutton = ttk.Checkbutton(parent, text=text, variable=variable, **kwargs)
        self._attach_tooltip(checkbutton, text)
        return checkbutton

    def _ensure_mousewheel_bindings(self) -> None:
        if self._mousewheel_bound:
            return
        self.root.bind_all("<MouseWheel>", self._handle_global_mousewheel)
        self.root.bind_all("<Button-4>", self._handle_global_mousewheel)
        self.root.bind_all("<Button-5>", self._handle_global_mousewheel)
        self._mousewheel_bound = True

    def _handle_global_mousewheel(self, event) -> None:
        canvas = self._active_scroll_canvas
        if canvas is None:
            return
        if getattr(event, "num", None) == 4:
            canvas.yview_scroll(-3, "units")
        elif getattr(event, "num", None) == 5:
            canvas.yview_scroll(3, "units")
        else:
            delta = int(-1 * (event.delta / 120))
            if delta:
                canvas.yview_scroll(delta * 3, "units")

    def _create_scrollable_tab(self, notebook: ttk.Notebook, text: str) -> ttk.Frame:
        outer = ttk.Frame(notebook)
        notebook.add(outer, text=text)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        inner = ttk.Frame(canvas, padding=10)
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def configure_scrollregion(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def configure_width(event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        def bind_wheel(_event=None) -> None:
            self._active_scroll_canvas = canvas

        def unbind_wheel(_event=None) -> None:
            if self._active_scroll_canvas is canvas:
                self._active_scroll_canvas = None

        self._ensure_mousewheel_bindings()
        inner.bind("<Configure>", configure_scrollregion)
        canvas.bind("<Configure>", configure_width)
        canvas.bind("<Enter>", bind_wheel)
        canvas.bind("<Leave>", unbind_wheel)
        inner.bind("<Enter>", bind_wheel)
        inner.bind("<Leave>", unbind_wheel)
        return inner

    def _build_server_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(2, weight=1)

        runtime = ttk.LabelFrame(parent, text="Runtime", padding=10)
        runtime.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        runtime.columnconfigure(1, weight=1)
        self.runtime_vars["python_path"] = tk.StringVar()
        self.runtime_vars["llama_server_binary"] = tk.StringVar()
        self.runtime_vars["llama_server_cwd"] = tk.StringVar()
        self.runtime_vars["llama_server_library_path"] = tk.StringVar()
        self.runtime_vars["llama_cpp_release_backend"] = tk.StringVar(value="auto")
        self._path_row(runtime, 0, "Python", self.runtime_vars["python_path"], self.browse_python)
        self._path_row(runtime, 1, "llama-server", self.runtime_vars["llama_server_binary"], self.browse_binary)
        self._path_row(runtime, 2, "Working dir", self.runtime_vars["llama_server_cwd"], self.browse_cwd, directory=True)
        self._path_row(runtime, 3, "LD library path", self.runtime_vars["llama_server_library_path"], self.browse_lib_dir, directory=True)
        self._combo_row(runtime, 4, "llama.cpp backend", self.runtime_vars["llama_cpp_release_backend"], list(BACKEND_CHOICES))

        setup_buttons = ttk.Frame(runtime)
        setup_buttons.grid(row=5, column=1, columnspan=2, sticky="w", pady=(8, 0))
        self._button(setup_buttons, text="Beginner setup", command=self.beginner_setup).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        self._button(setup_buttons, text="Install Python libs", command=self.install_python_libraries).pack(
            side=tk.LEFT, padx=6
        )
        self._button(setup_buttons, text="Install system libs", command=self.install_system_libraries).pack(
            side=tk.LEFT, padx=6
        )

        llama_buttons = ttk.Frame(runtime)
        llama_buttons.grid(row=6, column=1, columnspan=2, sticky="w", pady=(6, 0))
        self._button(llama_buttons, text="Auto-detect runtime", command=self.auto_detect_runtime).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        self._button(llama_buttons, text="Check server version", command=self.check_llama_server_version).pack(
            side=tk.LEFT, padx=6
        )
        self._button(llama_buttons, text="Check updates", command=self.check_llama_cpp_updates).pack(
            side=tk.LEFT, padx=6
        )
        self._button(llama_buttons, text="Download llama-server", command=self.download_llama_server).pack(
            side=tk.LEFT, padx=6
        )

        selector = ttk.LabelFrame(parent, text="Profile", padding=10)
        selector.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        selector.columnconfigure(1, weight=1)
        self.active_profile_var = tk.StringVar(value=self.current_profile)
        ttk.Label(selector, text="Active profile").grid(row=0, column=0, sticky="w", padx=(0, 8))
        combo = ttk.Combobox(
            selector,
            textvariable=self.active_profile_var,
            values=self.profile_names,
            state="readonly",
            width=24,
        )
        combo.grid(row=0, column=1, sticky="w")
        combo.bind("<<ComboboxSelected>>", self.on_profile_changed)
        self.profile_hint_var = tk.StringVar()
        ttk.Label(selector, textvariable=self.profile_hint_var, foreground="#555").grid(
            row=0, column=2, sticky="w", padx=16
        )

        left = ttk.LabelFrame(parent, text="Model and endpoint", padding=10)
        left.grid(row=2, column=0, sticky="nsew", padx=(0, 4))
        left.columnconfigure(1, weight=1)

        right = ttk.LabelFrame(parent, text="Runtime parameters", padding=10)
        right.grid(row=2, column=1, sticky="nsew", padx=(4, 0))
        right.columnconfigure(1, weight=1)

        for key in [
            "model_path",
            "mmproj_path",
            "models_dir",
            "models_preset",
            "host",
            "port",
            "alias",
            "api_key",
            "n_ctx",
            "n_threads",
            "n_threads_batch",
            "n_gpu_layers",
            "main_gpu",
            "split_mode",
            "tensor_split",
            "n_batch",
            "n_ubatch",
            "flash_attn",
            "extra_args",
            "models_max",
        ]:
            self.profile_vars[key] = tk.StringVar()
        for key in ["use_mmap", "use_mlock", "webui", "cont_batching", "metrics", "slots", "models_autoload"]:
            self.profile_vars[key] = tk.BooleanVar()

        self._path_row(left, 0, "Model .gguf", self.profile_vars["model_path"], self.browse_model)
        self._path_row(left, 1, "MMProj", self.profile_vars["mmproj_path"], self.browse_mmproj)
        self._path_row(left, 2, "Models dir", self.profile_vars["models_dir"], self.browse_models_dir, directory=True)
        self._path_row(left, 3, "Models preset", self.profile_vars["models_preset"], self.browse_models_preset)
        self._entry_row(left, 4, "Host", self.profile_vars["host"])
        self._entry_row(left, 5, "Port", self.profile_vars["port"])
        self._entry_row(left, 6, "Model alias", self.profile_vars["alias"])
        self._entry_row(left, 7, "API key", self.profile_vars["api_key"], show="*")

        self._entry_row(right, 0, "Context", self.profile_vars["n_ctx"])
        self._entry_row(right, 1, "Threads", self.profile_vars["n_threads"])
        self._entry_row(right, 2, "Batch threads", self.profile_vars["n_threads_batch"])
        self._entry_row(right, 3, "GPU layers", self.profile_vars["n_gpu_layers"])
        self._entry_row(right, 4, "Main GPU", self.profile_vars["main_gpu"])
        self._combo_row(right, 5, "Split mode", self.profile_vars["split_mode"], ["none", "layer", "row", "tensor"])
        self._entry_row(right, 6, "Tensor split", self.profile_vars["tensor_split"])
        self._entry_row(right, 7, "Batch", self.profile_vars["n_batch"])
        self._entry_row(right, 8, "Micro-batch", self.profile_vars["n_ubatch"])
        self._combo_row(right, 9, "Flash attention", self.profile_vars["flash_attn"], ["auto", "on", "off"])
        self._entry_row(right, 10, "Router max models", self.profile_vars["models_max"])
        self._entry_row(right, 11, "Extra args", self.profile_vars["extra_args"])

        flags = ttk.Frame(right)
        flags.grid(row=12, column=0, columnspan=3, sticky="w", pady=(10, 0))
        for idx, (key, label) in enumerate(
            [
                ("use_mmap", "mmap"),
                ("use_mlock", "mlock"),
                ("webui", "web UI"),
                ("cont_batching", "continuous batching"),
                ("metrics", "metrics"),
                ("slots", "slots"),
                ("models_autoload", "router autoload"),
            ]
        ):
            self._checkbutton(flags, text=label, variable=self.profile_vars[key]).grid(
                row=idx // 3, column=idx % 3, sticky="w", padx=(0, 14), pady=2
            )

    def _build_instances_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        top = ttk.LabelFrame(parent, text="Running instances", padding=10)
        top.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        top.columnconfigure(0, weight=1)

        columns = (
            "enabled",
            "name",
            "profile",
            "host",
            "port",
            "gpu",
            "ctx",
            "alias",
            "status",
            "pid",
            "healthy",
            "url",
        )
        self.instances_tree = ttk.Treeview(top, columns=columns, show="headings", height=9)
        headings = {
            "enabled": "Enabled",
            "name": "Name",
            "profile": "Profile",
            "host": "Host",
            "port": "Port",
            "gpu": "GPU",
            "ctx": "Ctx",
            "alias": "Alias",
            "status": "Status",
            "pid": "PID",
            "healthy": "Healthy",
            "url": "OpenAI URL",
        }
        widths = {
            "enabled": 70,
            "name": 140,
            "profile": 100,
            "host": 100,
            "port": 70,
            "gpu": 60,
            "ctx": 70,
            "alias": 150,
            "status": 90,
            "pid": 80,
            "healthy": 80,
            "url": 260,
        }
        for column in columns:
            self.instances_tree.heading(column, text=headings[column])
            self.instances_tree.column(column, width=widths[column], stretch=column in {"name", "alias", "url"})
        self.instances_tree.grid(row=0, column=0, sticky="ew")
        self.instances_tree.bind("<<TreeviewSelect>>", self.on_instance_selected)

        y_scroll = ttk.Scrollbar(top, orient="vertical", command=self.instances_tree.yview)
        x_scroll = ttk.Scrollbar(top, orient="horizontal", command=self.instances_tree.xview)
        self.instances_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        buttons = ttk.Frame(top)
        buttons.grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self._button(buttons, text="Add", command=self.add_instance).pack(side=tk.LEFT, padx=(0, 6))
        self._button(buttons, text="Duplicate", command=self.duplicate_instance).pack(side=tk.LEFT, padx=6)
        self._button(buttons, text="Remove", command=self.remove_instance).pack(side=tk.LEFT, padx=6)
        self._button(buttons, text="Start selected", command=self.start_selected_instance).pack(side=tk.LEFT, padx=6)
        self._button(buttons, text="Stop selected", command=self.stop_selected_instance).pack(side=tk.LEFT, padx=6)
        self._button(buttons, text="Restart selected", command=self.restart_selected_instance).pack(side=tk.LEFT, padx=6)
        self._button(buttons, text="Start enabled", command=self.start_enabled_instances).pack(side=tk.LEFT, padx=6)
        self._button(buttons, text="Stop all", command=self.stop_all_instances).pack(side=tk.LEFT, padx=6)
        self._button(buttons, text="Copy URL", command=self.copy_selected_instance_url).pack(side=tk.LEFT, padx=6)
        self._button(buttons, text="Use for proxy", command=self.use_selected_instance_for_proxy).pack(side=tk.LEFT, padx=6)

        editor = ttk.LabelFrame(parent, text="Selected instance", padding=10)
        editor.grid(row=1, column=0, sticky="ew")
        editor.columnconfigure(0, weight=1)
        editor.columnconfigure(1, weight=1)

        string_keys = [
            "id",
            "name",
            "profile",
            "model_path",
            "mmproj_path",
            "models_dir",
            "models_preset",
            "host",
            "port",
            "alias",
            "api_key",
            "n_ctx",
            "n_threads",
            "n_threads_batch",
            "n_gpu_layers",
            "main_gpu",
            "split_mode",
            "tensor_split",
            "n_batch",
            "n_ubatch",
            "flash_attn",
            "models_max",
            "extra_args",
        ]
        for key in string_keys:
            self.instance_vars[key] = tk.StringVar()
        for key in ["enabled", "use_mmap", "use_mlock", "webui", "cont_batching", "metrics", "slots", "models_autoload"]:
            self.instance_vars[key] = tk.BooleanVar()

        basic = ttk.LabelFrame(editor, text="Basic", padding=8)
        basic.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=(0, 8))
        basic.columnconfigure(1, weight=1)

        paths = ttk.LabelFrame(editor, text="Models and router", padding=8)
        paths.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=(0, 8))
        paths.columnconfigure(1, weight=1)

        runtime = ttk.LabelFrame(editor, text="GPU and runtime", padding=8)
        runtime.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        runtime.columnconfigure(1, weight=1)
        runtime.columnconfigure(4, weight=1)

        flags = ttk.LabelFrame(editor, text="Flags", padding=8)
        flags.grid(row=2, column=0, columnspan=2, sticky="ew")

        self._checkbutton(basic, text="Enabled", variable=self.instance_vars["enabled"]).grid(
            row=0, column=0, sticky="w", pady=4
        )
        self._entry_row(basic, 1, "ID", self.instance_vars["id"])
        self._entry_row(basic, 2, "Name", self.instance_vars["name"])
        instance_profile_combo = self._combo_row(basic, 3, "Profile", self.instance_vars["profile"], self.profile_names)
        instance_profile_combo.bind("<<ComboboxSelected>>", self.on_instance_profile_changed)
        self._entry_row(basic, 4, "Host", self.instance_vars["host"])
        self._entry_row(basic, 5, "Port", self.instance_vars["port"])
        self._entry_row(basic, 6, "Alias", self.instance_vars["alias"])
        self._entry_row(basic, 7, "API key", self.instance_vars["api_key"], show="*")

        self._path_row(paths, 0, "Model .gguf", self.instance_vars["model_path"], self.browse_instance_model)
        self._path_row(paths, 1, "MMProj", self.instance_vars["mmproj_path"], self.browse_instance_mmproj)
        self._path_row(paths, 2, "Models dir", self.instance_vars["models_dir"], self.browse_instance_models_dir, directory=True)
        self._path_row(paths, 3, "Models preset", self.instance_vars["models_preset"], self.browse_instance_models_preset)
        self._entry_row(paths, 4, "Router max models", self.instance_vars["models_max"])

        self._entry_row(runtime, 0, "Context", self.instance_vars["n_ctx"])
        self._entry_row(runtime, 1, "Threads", self.instance_vars["n_threads"])
        self._entry_row(runtime, 2, "Batch threads", self.instance_vars["n_threads_batch"])
        self._entry_row(runtime, 3, "GPU layers", self.instance_vars["n_gpu_layers"])
        self._entry_row(runtime, 4, "Main GPU", self.instance_vars["main_gpu"])
        self._combo_row(runtime, 5, "Split mode", self.instance_vars["split_mode"], ["none", "layer", "row", "tensor"])
        self._entry_row(runtime, 6, "Tensor split", self.instance_vars["tensor_split"])
        self._entry_row(runtime, 7, "Batch", self.instance_vars["n_batch"])
        self._entry_row(runtime, 8, "Micro-batch", self.instance_vars["n_ubatch"])
        self._combo_row(runtime, 9, "Flash attention", self.instance_vars["flash_attn"], ["auto", "on", "off"])
        self._entry_row(runtime, 10, "Extra args", self.instance_vars["extra_args"])

        for idx, (key, label) in enumerate(
            [
                ("use_mmap", "mmap"),
                ("use_mlock", "mlock"),
                ("webui", "web UI"),
                ("cont_batching", "continuous batching"),
                ("metrics", "metrics"),
                ("slots", "slots"),
                ("models_autoload", "router autoload"),
            ]
        ):
            self._checkbutton(flags, text=label, variable=self.instance_vars[key]).grid(
                row=idx // 3, column=idx % 3, sticky="w", padx=(0, 14), pady=2
            )

        ttk.Label(
            editor,
            text="Каждый instance хранит свои настройки. Вкладка Server для multi-instance не нужна.",
            foreground="#555",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        editor_buttons = ttk.Frame(editor)
        editor_buttons.grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self._button(editor_buttons, text="Apply to selected", command=self.apply_instance_editor).pack(side=tk.LEFT)
        self._button(editor_buttons, text="Reload selected", command=self.reload_selected_instance).pack(side=tk.LEFT, padx=8)

    def _build_proxy_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        self.proxy_vars["enabled"] = tk.BooleanVar()
        self.proxy_vars["host"] = tk.StringVar()
        self.proxy_vars["port"] = tk.StringVar()
        self.proxy_vars["target_base_url"] = tk.StringVar()
        self.proxy_vars["target_api_key"] = tk.StringVar()
        self.proxy_vars["model"] = tk.StringVar()

        self._checkbutton(parent, text="Start proxy together with server", variable=self.proxy_vars["enabled"]).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10)
        )
        self._entry_row(parent, 1, "Proxy host", self.proxy_vars["host"])
        self._entry_row(parent, 2, "Proxy port", self.proxy_vars["port"])
        self._entry_row(parent, 3, "Target OpenAI URL", self.proxy_vars["target_base_url"])
        self._entry_row(parent, 4, "Target API key", self.proxy_vars["target_api_key"], show="*")
        self._entry_row(parent, 5, "Model name", self.proxy_vars["model"])

        ttk.Label(
            parent,
            text="Leave Target OpenAI URL empty to use the active llama-server profile.",
            foreground="#555",
        ).grid(row=6, column=1, sticky="w", pady=(0, 10))

        buttons = ttk.Frame(parent)
        buttons.grid(row=7, column=0, columnspan=3, sticky="w", pady=8)
        self._button(buttons, text="Start proxy", command=self.start_proxy).pack(side=tk.LEFT, padx=(0, 6))
        self._button(buttons, text="Stop proxy", command=self.stop_proxy).pack(side=tk.LEFT, padx=6)
        self._button(buttons, text="Copy Ollama URL", command=self.copy_ollama_url).pack(side=tk.LEFT, padx=6)

    def _build_devices_tab(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)
        self._button(parent, text="Refresh devices", command=self.refresh_devices).grid(row=0, column=0, sticky="w")
        self.devices_text = tk.Text(parent, height=20, wrap="word")
        self.devices_text.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

    def _build_logs_tab(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(2, weight=1)
        parent.columnconfigure(0, weight=1)
        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, sticky="ew")
        self._button(toolbar, text="Refresh logs", command=self.refresh_logs).pack(side=tk.LEFT, padx=(0, 6))
        self._button(toolbar, text="Open logs folder", command=self.open_logs_folder).pack(side=tk.LEFT, padx=6)
        self.log_path_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.log_path_var, foreground="#555").grid(row=1, column=0, sticky="w", pady=6)
        self.logs_text = tk.Text(parent, height=28, wrap="none")
        self.logs_text.grid(row=2, column=0, sticky="nsew")
        scroll_y = ttk.Scrollbar(parent, command=self.logs_text.yview)
        scroll_y.grid(row=2, column=1, sticky="ns")
        self.logs_text.configure(yscrollcommand=scroll_y.set)

    def _build_help_tab(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        text = tk.Text(parent, wrap="word", height=28)
        text.grid(row=0, column=0, sticky="nsew")
        scroll_y = ttk.Scrollbar(parent, command=text.yview)
        scroll_y.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=scroll_y.set)
        text.insert("1.0", HOUSEHOLD_HELP_TEXT)
        text.configure(state="disabled")

    def _build_bottom_bar(self) -> None:
        bottom = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        bottom.grid(row=1, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        status = ttk.LabelFrame(bottom, text="Status", padding=8)
        status.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        status.columnconfigure(1, weight=1)
        for row, key in enumerate(["server", "proxy", "urls"]):
            self.status_vars[key] = tk.StringVar()
            ttk.Label(status, text=key.capitalize()).grid(row=row, column=0, sticky="w", padx=(0, 10))
            ttk.Label(status, textvariable=self.status_vars[key]).grid(row=row, column=1, sticky="w")

        buttons = ttk.Frame(bottom)
        buttons.grid(row=0, column=1, sticky="e")
        self._button(buttons, text="Save", command=self.save_all).grid(row=0, column=0, padx=3)
        self._button(buttons, text="Start", command=self.start_all).grid(row=0, column=1, padx=3)
        self._button(buttons, text="Restart", command=self.restart_all).grid(row=0, column=2, padx=3)
        self._button(buttons, text="Stop", command=self.stop_all).grid(row=0, column=3, padx=3)
        self._button(buttons, text="Open", command=self.open_server).grid(row=0, column=4, padx=3)
        self._button(buttons, text="Copy OpenAI URL", command=self.copy_openai_url).grid(row=1, column=1, padx=3, pady=(6, 0))
        self._button(buttons, text="Copy Ollama URL", command=self.copy_ollama_url).grid(row=1, column=2, padx=3, pady=(6, 0))
        self._button(buttons, text="Quit", command=self.root.destroy).grid(row=1, column=4, padx=3, pady=(6, 0))

    def _entry_row(self, parent: ttk.Frame, row: int, label: str, var: tk.Variable, show: str | None = None) -> ttk.Entry:
        label_widget = ttk.Label(parent, text=label)
        label_widget.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        self._attach_tooltip(label_widget, label)
        entry = ttk.Entry(parent, textvariable=var, show=show)
        entry.grid(row=row, column=1, sticky="ew", pady=4)
        self._attach_tooltip(entry, label)
        return entry

    def _combo_row(self, parent: ttk.Frame, row: int, label: str, var: tk.Variable, values: list[str]) -> ttk.Combobox:
        label_widget = ttk.Label(parent, text=label)
        label_widget.grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
        self._attach_tooltip(label_widget, label)
        combo = ttk.Combobox(parent, textvariable=var, values=values, state="readonly")
        combo.grid(row=row, column=1, sticky="ew", pady=4)
        self._attach_tooltip(combo, label)
        return combo

    def _path_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        var: tk.Variable,
        command,
        directory: bool = False,
    ) -> None:
        self._entry_row(parent, row, label, var)
        browse = self._button(parent, text="Browse", command=command, width=10)
        self._attach_tooltip(browse, label, f"Выбрать значение для поля {label}.")
        browse.grid(row=row, column=2, sticky="e", padx=(6, 0))

    def browse_python(self) -> None:
        self._browse_file(self.runtime_vars["python_path"], "Select Python runtime")

    def browse_binary(self) -> None:
        self._browse_file(self.runtime_vars["llama_server_binary"], "Select llama-server")

    def browse_cwd(self) -> None:
        self._browse_dir(self.runtime_vars["llama_server_cwd"])

    def browse_lib_dir(self) -> None:
        self._browse_dir(self.runtime_vars["llama_server_library_path"])

    def beginner_setup(self) -> None:
        base_python = shutil.which("python3") or sys.executable
        if not base_python or not Path(base_python).exists():
            messagebox.showerror("Beginner setup", "python3 not found. Install python3 first.")
            return
        requirements = APP_DIR / "requirements.txt"
        if not requirements.exists():
            messagebox.showerror("Beginner setup", f"requirements.txt not found:\n{requirements}")
            return

        venv_dir = APP_DIR / ".venv"
        venv_python = venv_dir / "bin" / "python"
        script = " && ".join(
            [
                f"{shlex.quote(base_python)} -m venv {shlex.quote(str(venv_dir))}",
                f"{shlex.quote(str(venv_python))} -m pip install -r {shlex.quote(str(requirements))}",
            ]
        )
        if not messagebox.askyesno(
            "Beginner setup",
            "Create/update local .venv and install Python dependencies?\n\n"
            f"Python will be set to:\n{venv_python}",
        ):
            return

        def on_success() -> None:
            self.runtime_vars["python_path"].set(str(venv_python))
            self._save_runtime_vars()
            save_config(self.config)
            self.manager.update_config(self.config)
            messagebox.showinfo(
                "Beginner setup",
                "Local .venv is ready. Python runtime was updated.\n\n"
                "Next: click Auto-detect runtime, choose a .gguf model, then Start.",
            )

        self._run_command_window("Beginner setup", ["bash", "-lc", script], cwd=APP_DIR, on_success=on_success)

    def _runtime_config_from_vars(self) -> dict[str, Any]:
        config = dict(self.config)
        for key, var in self.runtime_vars.items():
            config[key] = str(var.get() or "").strip()
        return config

    def auto_detect_runtime(self) -> None:
        detected = detect_runtime_paths(self._runtime_config_from_vars(), prefer_existing=False, deep_search=True)
        labels = {
            "python_path": "Python",
            "llama_server_binary": "llama-server",
            "llama_server_cwd": "Working dir",
            "llama_server_library_path": "LD library path",
        }
        applied: list[str] = []
        warnings: list[str] = []
        for key in RUNTIME_KEYS:
            value = str(detected.get(key) or "").strip()
            if value and runtime_value_is_usable(key, value):
                self.runtime_vars[key].set(value)
                applied.append(f"{labels[key]}: {value}")
            else:
                warnings.append(f"{labels[key]}: not found")

        self._save_runtime_vars()
        save_config(self.config)
        self.manager.update_config(self.config)
        self.refresh_status()

        unusable = [
            labels[key]
            for key in RUNTIME_KEYS
            if not runtime_value_is_usable(key, self.runtime_vars[key].get())
        ]
        message = "\n".join(applied + warnings)
        if unusable:
            message += "\n\nNeed manual check: " + ", ".join(unusable)
            messagebox.showwarning("Auto-detect runtime", message)
        else:
            messagebox.showinfo("Auto-detect runtime", message)

    def _selected_release_backend(self) -> str:
        backend = str(self.runtime_vars["llama_cpp_release_backend"].get() or "auto").strip().lower()
        return backend if backend in BACKEND_CHOICES else "auto"

    def _release_tool_command(self, command: str, *args: str) -> list[str]:
        python_path = self._selected_python_path()
        return [
            python_path,
            str(APP_DIR / "llama_cpp_release.py"),
            "--backend",
            self._selected_release_backend(),
            command,
            *args,
        ]

    def check_llama_server_version(self) -> None:
        binary = str(self.runtime_vars["llama_server_binary"].get() or "").strip()
        if not binary:
            messagebox.showwarning("Check server version", "llama-server path is empty.")
            return
        command = self._release_tool_command("version", "--binary", binary)
        library = str(self.runtime_vars["llama_server_library_path"].get() or "").strip()
        if library:
            command.extend(["--library", library])
        self._run_command_window("Check server version", command, cwd=APP_DIR)

    def check_llama_cpp_updates(self) -> None:
        binary = str(self.runtime_vars["llama_server_binary"].get() or "").strip()
        command = self._release_tool_command("check")
        if binary:
            command.extend(["--binary", binary])
        library = str(self.runtime_vars["llama_server_library_path"].get() or "").strip()
        if library:
            command.extend(["--library", library])
        self._run_command_window("Check llama.cpp updates", command, cwd=APP_DIR)

    def download_llama_server(self) -> None:
        backend = self._selected_release_backend()
        if not messagebox.askyesno(
            "Download llama-server",
            "Download the latest prebuilt llama.cpp release from GitHub?\n\n"
            f"Backend: {backend}\n\n"
            "The downloaded server will be saved under runtime/llama.cpp and selected in Runtime.",
        ):
            return

        def on_success() -> None:
            manifest = read_manifest()
            binary = str(manifest.get("binary_path") or "")
            library = str(manifest.get("library_path") or "")
            if binary:
                self.runtime_vars["llama_server_binary"].set(binary)
                self.runtime_vars["llama_server_cwd"].set(str(Path(binary).parent))
            if library:
                self.runtime_vars["llama_server_library_path"].set(library)
            self._save_runtime_vars()
            save_config(self.config)
            self.manager.update_config(self.config)
            self.refresh_status()
            messagebox.showinfo(
                "Download llama-server",
                "llama-server was downloaded and selected.\n\n"
                f"Release: {manifest.get('tag_name') or 'unknown'}\n"
                f"Binary: {binary or 'not found'}\n\n"
                "Restart any running server to use the new binary.",
            )

        self._run_command_window(
            "Download llama-server",
            self._release_tool_command("install"),
            cwd=APP_DIR,
            on_success=on_success,
        )

    def _selected_python_path(self) -> str:
        python_path = str(self.runtime_vars["python_path"].get() or "").strip()
        if python_path and Path(python_path).exists():
            return python_path
        detected = detect_runtime_paths(self._runtime_config_from_vars(), prefer_existing=True, deep_search=False)
        return detected.get("python_path") or sys.executable

    def install_python_libraries(self) -> None:
        python_path = self._selected_python_path()
        if not Path(python_path).exists():
            messagebox.showerror("Install Python libs", f"Python runtime not found:\n{python_path}")
            return
        requirements = APP_DIR / "requirements.txt"
        if not requirements.exists():
            messagebox.showerror("Install Python libs", f"requirements.txt not found:\n{requirements}")
            return
        command = [python_path, "-m", "pip", "install", "-r", str(requirements)]
        if not messagebox.askyesno(
            "Install Python libs",
            "Run this command?\n\n" + shlex.join(command),
        ):
            return
        self._run_command_window("Install Python libs", command, cwd=APP_DIR)

    def _system_dependency_command(self) -> str:
        if shutil.which("apt-get"):
            return "sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip python3-tk"
        if shutil.which("dnf"):
            return "sudo dnf install -y python3 python3-pip python3-tkinter"
        if shutil.which("pacman"):
            return "sudo pacman -S --needed python python-pip tk"
        if shutil.which("zypper"):
            return "sudo zypper install -y python3 python3-pip python3-tk"
        return ""

    def install_system_libraries(self) -> None:
        command = self._system_dependency_command()
        if not command:
            messagebox.showwarning(
                "Install system libs",
                "Could not detect apt, dnf, pacman, or zypper. Install Python, pip, venv, and Tkinter manually.",
            )
            return
        if not messagebox.askyesno(
            "Install system libs",
            "A terminal will open for sudo/system package installation:\n\n" + command,
        ):
            return
        self._launch_terminal_command(command)

    def _run_command_window(
        self,
        title: str,
        command: list[str],
        cwd: Path | None = None,
        on_success: Callable[[], None] | None = None,
    ) -> None:
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("900x520")
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)

        text = tk.Text(window, wrap="word")
        text.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        scroll_y = ttk.Scrollbar(window, command=text.yview)
        scroll_y.grid(row=0, column=1, sticky="ns", pady=8)
        text.configure(yscrollcommand=scroll_y.set)

        close_button = ttk.Button(window, text="Close", command=window.destroy, state=tk.DISABLED)
        close_button.grid(row=1, column=0, sticky="e", padx=8, pady=(0, 8))

        output_queue: queue.Queue[tuple[str, str | int]] = queue.Queue()

        def append(value: str) -> None:
            text.insert(tk.END, value)
            text.see(tk.END)

        def worker() -> None:
            try:
                with subprocess.Popen(
                    command,
                    cwd=str(cwd or APP_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                ) as process:
                    if process.stdout is not None:
                        for line in process.stdout:
                            output_queue.put(("line", line))
                    output_queue.put(("done", process.wait()))
            except Exception as exc:
                output_queue.put(("error", str(exc)))

        def poll() -> None:
            done = False
            try:
                while True:
                    kind, value = output_queue.get_nowait()
                    if kind == "line":
                        append(str(value))
                    elif kind == "error":
                        append(f"\nERROR: {value}\n")
                        done = True
                    elif kind == "done":
                        code = int(value)
                        append(f"\nExit code: {code}\n")
                        if code == 0 and on_success is not None:
                            on_success()
                        done = True
                    output_queue.task_done()
            except queue.Empty:
                pass
            if done:
                close_button.configure(state=tk.NORMAL)
            else:
                window.after(100, poll)

        append("$ " + shlex.join(command) + "\n\n")
        threading.Thread(target=worker, daemon=True).start()
        poll()

    def _launch_terminal_command(self, command: str) -> None:
        script = (
            command
            + "\nstatus=$?\necho\necho Exit code: $status\n"
            + "read -r -p 'Press Enter to close...' _\nexit $status"
        )
        candidates = []
        if shutil.which("x-terminal-emulator"):
            candidates.append(["x-terminal-emulator", "-e", "bash", "-lc", script])
        if shutil.which("gnome-terminal"):
            candidates.append(["gnome-terminal", "--", "bash", "-lc", script])
        if shutil.which("konsole"):
            candidates.append(["konsole", "-e", "bash", "-lc", script])
        if shutil.which("xfce4-terminal"):
            candidates.append(["xfce4-terminal", "--command", "bash -lc " + shlex.quote(script)])
        if shutil.which("xterm"):
            candidates.append(["xterm", "-e", "bash", "-lc", script])

        for candidate in candidates:
            try:
                subprocess.Popen(candidate, cwd=str(APP_DIR))
                return
            except Exception:
                continue
        messagebox.showwarning(
            "Install system libs",
            "Could not open a terminal. Run this command manually:\n\n" + command,
        )

    def browse_model(self) -> None:
        self._browse_file(self.profile_vars["model_path"], "Select GGUF model", [("GGUF", "*.gguf"), ("All", "*.*")])

    def browse_mmproj(self) -> None:
        self._browse_file(self.profile_vars["mmproj_path"], "Select MMProj", [("GGUF", "*.gguf"), ("All", "*.*")])

    def browse_models_dir(self) -> None:
        self._browse_dir(self.profile_vars["models_dir"])

    def browse_models_preset(self) -> None:
        self._browse_file(self.profile_vars["models_preset"], "Select router preset")

    def browse_instance_model(self) -> None:
        self._browse_file(self.instance_vars["model_path"], "Select GGUF model", [("GGUF", "*.gguf"), ("All", "*.*")])

    def browse_instance_mmproj(self) -> None:
        self._browse_file(self.instance_vars["mmproj_path"], "Select MMProj", [("GGUF", "*.gguf"), ("All", "*.*")])

    def browse_instance_models_dir(self) -> None:
        self._browse_dir(self.instance_vars["models_dir"])

    def browse_instance_models_preset(self) -> None:
        self._browse_file(self.instance_vars["models_preset"], "Select router preset")

    def _browse_file(self, var: tk.Variable, title: str, filetypes: list[tuple[str, str]] | None = None) -> None:
        initial = str(var.get() or "")
        initialdir = str(Path(initial).parent) if initial else str(Path.home())
        filename = filedialog.askopenfilename(title=title, initialdir=initialdir, filetypes=filetypes or [("All", "*.*")])
        if filename:
            var.set(filename)

    def _browse_dir(self, var: tk.Variable) -> None:
        initial = str(var.get() or "") or str(Path.home())
        dirname = filedialog.askdirectory(initialdir=initial if Path(initial).exists() else str(Path.home()))
        if dirname:
            var.set(dirname)

    def _load_runtime_vars(self) -> None:
        for key, var in self.runtime_vars.items():
            var.set(str(self.config.get(key) or ""))

    def _load_profile_vars(self, name: str) -> None:
        profile = get_profile(self.config, name)
        self.profile_hint_var.set(profile_display_name(name))
        for key, var in self.profile_vars.items():
            value = profile.get(key, "")
            if isinstance(var, tk.BooleanVar):
                var.set(bool(value))
            else:
                var.set("" if value is None else str(value))

    def _load_proxy_vars(self) -> None:
        proxy = self.config.get("ollama_proxy") or {}
        for key, var in self.proxy_vars.items():
            value = proxy.get(key, "")
            if isinstance(var, tk.BooleanVar):
                var.set(bool(value))
            else:
                var.set("" if value is None else str(value))

    def _instances(self) -> list[dict[str, Any]]:
        instances = self.config.setdefault("instances", [])
        if not isinstance(instances, list):
            self.config["instances"] = []
        return self.config["instances"]

    def _find_instance(self, instance_id: str | None) -> dict[str, Any] | None:
        if not instance_id:
            return None
        for instance in self._instances():
            if str(instance.get("id") or "") == instance_id:
                return instance
        return None

    def _load_instance_vars(self, instance: dict[str, Any] | None) -> None:
        if instance is None:
            for var in self.instance_vars.values():
                if isinstance(var, tk.BooleanVar):
                    var.set(False)
                else:
                    var.set("")
            return
        effective = self.manager._instance_effective_profile(instance)
        for key, var in self.instance_vars.items():
            if key == "enabled":
                value = instance.get(key, True)
            elif key in {"id", "name", "profile"}:
                value = instance.get(key, "")
            else:
                value = instance.get(key, effective.get(key, ""))
            if isinstance(var, tk.BooleanVar):
                var.set(bool(value))
            else:
                var.set("" if value is None else str(value))

    def _instance_from_vars(self) -> dict[str, Any]:
        numeric_keys = {
            "port",
            "n_ctx",
            "n_threads",
            "n_threads_batch",
            "main_gpu",
            "n_batch",
            "n_ubatch",
            "models_max",
        }
        instance: dict[str, Any] = {
            "id": str(self.instance_vars["id"].get()).strip(),
            "name": str(self.instance_vars["name"].get()).strip(),
            "enabled": bool(self.instance_vars["enabled"].get()),
            "profile": str(self.instance_vars["profile"].get()).strip() or "chat",
        }
        for key, var in self.instance_vars.items():
            if key in {"id", "name", "enabled", "profile"}:
                continue
            if isinstance(var, tk.BooleanVar):
                instance[key] = bool(var.get())
            elif key in numeric_keys:
                instance[key] = self._int_or_string(str(var.get()))
            else:
                instance[key] = str(var.get()).strip()
        if not instance.get("host"):
            instance["host"] = "127.0.0.1"
        return instance

    def _save_selected_instance_vars(self) -> None:
        if not self.selected_instance_id:
            return
        existing = self._find_instance(self.selected_instance_id)
        if existing is None:
            return
        updated = self._instance_from_vars()
        if not updated["id"]:
            updated["id"] = self.selected_instance_id
        other_ids = {
            str(instance.get("id") or "")
            for instance in self._instances()
            if instance is not existing
        }
        if updated["id"] in other_ids:
            base = updated["id"]
            idx = 2
            while f"{base}-{idx}" in other_ids:
                idx += 1
            updated["id"] = f"{base}-{idx}"
        existing.clear()
        existing.update(updated)
        self.selected_instance_id = str(updated["id"])

    def _int_or_string(self, value: str) -> Any:
        text = str(value).strip()
        if text == "":
            return ""
        try:
            return int(text)
        except ValueError:
            return text

    def _save_profile_vars(self, name: str) -> None:
        profile = get_profile(self.config, name)
        for key, var in self.profile_vars.items():
            if isinstance(var, tk.BooleanVar):
                profile[key] = bool(var.get())
            elif key in {"port", "n_ctx", "n_threads", "n_threads_batch", "main_gpu", "n_batch", "n_ubatch", "models_max"}:
                profile[key] = self._int_or_string(str(var.get()))
            else:
                profile[key] = str(var.get()).strip()

    def _save_runtime_vars(self) -> None:
        for key, var in self.runtime_vars.items():
            self.config[key] = str(var.get()).strip()

    def _save_proxy_vars(self) -> None:
        proxy = self.config.setdefault("ollama_proxy", {})
        for key, var in self.proxy_vars.items():
            if isinstance(var, tk.BooleanVar):
                proxy[key] = bool(var.get())
            elif key == "port":
                proxy[key] = self._int_or_string(str(var.get()))
            else:
                proxy[key] = str(var.get()).strip()

    def save_all(self, silent: bool = False) -> None:
        self._save_runtime_vars()
        self._save_profile_vars(self.current_profile)
        self._save_proxy_vars()
        self._save_selected_instance_vars()
        self.config["active_profile"] = self.active_profile_var.get()
        save_config(self.config)
        self.manager.update_config(self.config)
        self.current_profile = self.active_profile_var.get()
        self.refresh_instances_table()
        if not silent:
            messagebox.showinfo("Saved", "Configuration saved.")

    def on_profile_changed(self, _event=None) -> None:
        old = self.current_profile
        new = self.active_profile_var.get()
        if old:
            self._save_profile_vars(old)
        self.current_profile = new
        self.config["active_profile"] = new
        self._load_profile_vars(new)
        self.refresh_status()

    def refresh_instances_table(self, select_first: bool = False) -> None:
        if not hasattr(self, "instances_tree"):
            return
        selected = self.selected_instance_id
        self._refreshing_instances_table = True
        try:
            self.instances_tree.delete(*self.instances_tree.get_children())
            for instance in self._instances():
                status = self.manager.instance_status(instance)
                owner = status.get("port_owner")
                state = "running" if status["running"] else "stopped"
                if owner and not status["running"]:
                    state = "port busy"
                values = (
                "yes" if status["enabled"] else "no",
                status["name"],
                status["profile"],
                status["host"],
                status["port"],
                status.get("main_gpu", ""),
                status.get("n_ctx", ""),
                status["alias"],
                state,
                status.get("pid") or "",
                "yes" if status["healthy"] else "no",
                status["openai_url"],
                )
                self.instances_tree.insert("", tk.END, iid=status["id"], values=values)

            ids = list(self.instances_tree.get_children())
            if selected and selected in ids:
                self.instances_tree.selection_set(selected)
                self.instances_tree.focus(selected)
            elif select_first and ids:
                self.instances_tree.selection_set(ids[0])
                self.instances_tree.focus(ids[0])
                self.selected_instance_id = ids[0]
                self._load_instance_vars(self._find_instance(ids[0]))
        finally:
            self._refreshing_instances_table = False

    def on_instance_selected(self, _event=None) -> None:
        if self._refreshing_instances_table:
            return
        if self.selected_instance_id:
            self._save_selected_instance_vars()
        selection = self.instances_tree.selection()
        self.selected_instance_id = selection[0] if selection else None
        self._load_instance_vars(self._find_instance(self.selected_instance_id))

    def on_instance_profile_changed(self, _event=None) -> None:
        profile_name = str(self.instance_vars["profile"].get() or "chat")
        profile = get_profile(self.config, profile_name)
        preserve = {
            "id": self.instance_vars["id"].get(),
            "name": self.instance_vars["name"].get(),
            "enabled": self.instance_vars["enabled"].get(),
            "host": self.instance_vars["host"].get() or profile.get("host", "127.0.0.1"),
            "port": self.instance_vars["port"].get() or profile.get("port", ""),
        }
        temp = dict(profile)
        temp.update(
            {
                "id": preserve["id"],
                "name": preserve["name"],
                "enabled": preserve["enabled"],
                "profile": profile_name,
                "host": preserve["host"],
                "port": preserve["port"],
            }
        )
        self._load_instance_vars(temp)

    def _next_instance_id(self, base: str) -> str:
        existing = {str(instance.get("id") or "") for instance in self._instances()}
        candidate = base
        idx = 2
        while candidate in existing:
            candidate = f"{base}-{idx}"
            idx += 1
        return candidate

    def add_instance(self) -> None:
        self._save_selected_instance_vars()
        profile_name = self.active_profile_var.get() or "chat"
        profile = get_profile(self.config, profile_name)
        base_port = int(profile.get("port") or 8081)
        used_ports = {
            int(instance.get("port"))
            for instance in self._instances()
            if str(instance.get("port") or "").isdigit()
        }
        port = base_port
        while port in used_ports:
            port += 1
        instance_id = self._next_instance_id(f"{profile_name}-{port}")
        instance = {
            "id": instance_id,
            "name": f"{profile_display_name(profile_name)} {port}",
            "enabled": True,
            "profile": profile_name,
            "host": str(profile.get("host") or "127.0.0.1"),
            "port": port,
        }
        for key in [
            "model_path",
            "mmproj_path",
            "models_dir",
            "models_preset",
            "alias",
            "api_key",
            "n_ctx",
            "n_threads",
            "n_threads_batch",
            "n_gpu_layers",
            "main_gpu",
            "split_mode",
            "tensor_split",
            "n_batch",
            "n_ubatch",
            "flash_attn",
            "models_max",
            "extra_args",
            "use_mmap",
            "use_mlock",
            "webui",
            "cont_batching",
            "metrics",
            "slots",
            "models_autoload",
        ]:
            instance[key] = profile.get(key, "")
        if not instance.get("alias"):
            instance["alias"] = instance_id
        self._instances().append(instance)
        self.selected_instance_id = instance_id
        self.refresh_instances_table()
        self.instances_tree.selection_set(instance_id)
        self._load_instance_vars(instance)

    def duplicate_instance(self) -> None:
        self._save_selected_instance_vars()
        source = self._find_instance(self.selected_instance_id)
        if source is None:
            self.add_instance()
            return
        copy = dict(source)
        port = int(copy.get("port") or 8081)
        used_ports = {
            int(instance.get("port"))
            for instance in self._instances()
            if str(instance.get("port") or "").isdigit()
        }
        while port in used_ports:
            port += 1
        copy["port"] = port
        copy["id"] = self._next_instance_id(f"{copy.get('profile', 'chat')}-{port}")
        copy["name"] = f"{copy.get('name') or 'Instance'} copy"
        copy["alias"] = f"{copy.get('alias') or copy['id']}-{port}"
        self._instances().append(copy)
        self.selected_instance_id = copy["id"]
        self.refresh_instances_table()
        self.instances_tree.selection_set(copy["id"])
        self._load_instance_vars(copy)

    def remove_instance(self) -> None:
        instance_id = self.selected_instance_id
        if not instance_id:
            return
        if not messagebox.askyesno("Remove instance", f"Remove instance {instance_id}?"):
            return
        self.manager.stop_instance(instance_id)
        self.config["instances"] = [
            instance for instance in self._instances() if str(instance.get("id") or "") != instance_id
        ]
        self.selected_instance_id = None
        self._load_instance_vars(None)
        self.refresh_instances_table(select_first=True)

    def apply_instance_editor(self) -> None:
        self._save_selected_instance_vars()
        save_config(self.config)
        self.manager.update_config(self.config)
        self.refresh_instances_table()
        messagebox.showinfo("Saved", "Instance saved.")

    def reload_selected_instance(self) -> None:
        self._load_instance_vars(self._find_instance(self.selected_instance_id))

    def _selected_instance_or_warn(self) -> dict[str, Any] | None:
        self._save_selected_instance_vars()
        instance = self._find_instance(self.selected_instance_id)
        if instance is None:
            messagebox.showwarning("No instance", "Select an instance first.")
            return None
        return instance

    def start_selected_instance(self) -> None:
        self.save_all(silent=True)
        instance = self._selected_instance_or_warn()
        if instance is None:
            return
        result = self.manager.start_instance(instance)
        self.refresh_status()
        if not result.ok:
            messagebox.showerror("Start failed", result.message)

    def stop_selected_instance(self) -> None:
        instance_id = self.selected_instance_id
        if not instance_id:
            messagebox.showwarning("No instance", "Select an instance first.")
            return
        result = self.manager.stop_instance(instance_id)
        self.refresh_status()
        if not result.ok:
            messagebox.showwarning("Stop failed", result.message)

    def restart_selected_instance(self) -> None:
        self.save_all(silent=True)
        instance = self._selected_instance_or_warn()
        if instance is None:
            return
        result = self.manager.restart_instance(instance)
        self.refresh_status()
        if not result.ok:
            messagebox.showerror("Restart failed", result.message)

    def start_enabled_instances(self) -> None:
        self.save_all(silent=True)
        results = []
        for instance in self._instances():
            if bool(instance.get("enabled", True)):
                results.append(self.manager.start_instance(instance))
        self.refresh_status()
        failed = [result.message for result in results if not result.ok]
        if failed:
            messagebox.showwarning("Some instances failed", "\n\n".join(failed))
        else:
            messagebox.showinfo("Started", f"Started {len(results)} enabled instance(s).")

    def stop_all_instances(self) -> None:
        results = self.manager.stop_all_instances()
        self.refresh_status()
        failed = [result.message for result in results if not result.ok]
        if failed:
            messagebox.showwarning("Some instances failed", "\n\n".join(failed))

    def copy_selected_instance_url(self) -> None:
        instance = self._find_instance(self.selected_instance_id)
        if instance is None:
            messagebox.showwarning("No instance", "Select an instance first.")
            return
        status = self.manager.instance_status(instance)
        self.copy_to_clipboard(status["openai_url"])

    def use_selected_instance_for_proxy(self) -> None:
        instance = self._find_instance(self.selected_instance_id)
        if instance is None:
            messagebox.showwarning("No instance", "Select an instance first.")
            return
        status = self.manager.instance_status(instance)
        self.proxy_vars["target_base_url"].set(status["openai_url"])
        self.proxy_vars["model"].set(status["alias"])
        self._save_proxy_vars()
        save_config(self.config)
        self.manager.update_config(self.config)
        messagebox.showinfo(
            "Proxy target updated",
            f"Ollama proxy now points to:\n{status['openai_url']}\n\nModel: {status['alias']}",
        )

    def start_all(self) -> None:
        self.save_all(silent=True)
        result = self.manager.start_server()
        if not result.ok:
            messagebox.showerror("Start failed", result.message)
            self.refresh_status()
            return
        proxy_result = None
        if bool(self.proxy_vars["enabled"].get()):
            proxy_result = self.manager.start_proxy()
        self.refresh_status()
        if proxy_result and not proxy_result.ok:
            messagebox.showwarning("Proxy failed", f"Server started, but proxy failed:\n{proxy_result.message}")
        else:
            messagebox.showinfo("Started", "llama-server started.")

    def stop_all(self) -> None:
        proxy = self.manager.stop_proxy()
        server = self.manager.stop_server()
        instance_results = self.manager.stop_all_instances()
        self.refresh_status()
        failed = [result.message for result in [proxy, server, *instance_results] if not result.ok]
        if failed:
            messagebox.showwarning("Stop", "\n".join(failed))

    def restart_all(self) -> None:
        self.save_all(silent=True)
        self.manager.stop_proxy()
        result = self.manager.restart_server()
        if result.ok and bool(self.proxy_vars["enabled"].get()):
            proxy_result = self.manager.start_proxy()
            if not proxy_result.ok:
                messagebox.showwarning("Proxy failed", proxy_result.message)
        elif not result.ok:
            messagebox.showerror("Restart failed", result.message)
        self.refresh_status()

    def start_proxy(self) -> None:
        self.save_all(silent=True)
        result = self.manager.start_proxy()
        self.refresh_status()
        if not result.ok:
            messagebox.showerror("Proxy failed", result.message)

    def stop_proxy(self) -> None:
        result = self.manager.stop_proxy()
        self.refresh_status()
        if not result.ok:
            messagebox.showwarning("Proxy", result.message)

    def open_server(self) -> None:
        status = self.manager.server_status()
        webbrowser.open(status["url"])

    def copy_openai_url(self) -> None:
        status = self.manager.server_status()
        self.copy_to_clipboard(status["openai_url"])

    def copy_ollama_url(self) -> None:
        status = self.manager.proxy_status()
        self.copy_to_clipboard(status["url"])

    def copy_to_clipboard(self, value: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.root.update_idletasks()
        messagebox.showinfo("Copied", value)

    def open_logs_folder(self) -> None:
        logs = Path(__file__).resolve().parent / "logs"
        webbrowser.open(logs.as_uri())

    def refresh_devices(self) -> None:
        self.save_all(silent=True)
        result = self.manager.list_devices()
        self.devices_text.delete("1.0", tk.END)
        self.devices_text.insert("1.0", result.message or "No output")

    def refresh_logs(self) -> None:
        server = self.manager.server_status()
        proxy = self.manager.proxy_status()
        selected_instance = self._find_instance(self.selected_instance_id)
        instance_status = self.manager.instance_status(selected_instance) if selected_instance else {}
        log_path = instance_status.get("log_path") or server.get("log_path") or proxy.get("log_path") or ""
        self.log_path_var.set(log_path)
        chunks = []
        if instance_status.get("log_path"):
            chunks.append(
                f"=== instance: {instance_status.get('name')} ===\n"
                + tail_file(instance_status.get("log_path"), 140)
            )
        if server.get("log_path"):
            chunks.append("=== llama-server ===\n" + tail_file(server.get("log_path"), 140))
        if proxy.get("log_path"):
            chunks.append("=== ollama proxy ===\n" + tail_file(proxy.get("log_path"), 80))
        self.logs_text.delete("1.0", tk.END)
        self.logs_text.insert("1.0", "\n\n".join(chunks) or "No active logs.")
        self.logs_text.see(tk.END)

    def refresh_status(self) -> None:
        if self._refresh_job is not None:
            try:
                self.root.after_cancel(self._refresh_job)
            except Exception:
                pass
            self._refresh_job = None

        server = self.manager.server_status()
        proxy = self.manager.proxy_status()
        owner = None
        if not server["running"]:
            try:
                owner = self.manager.port_owner(server["host"], int(server["port"]))
            except Exception:
                owner = None
        busy = ""
        if owner:
            busy = f" | port busy by pid={owner.get('pid') or '?'}"
        server_text = (
            f"{'running' if server['running'] else 'stopped'}"
            f" | pid={server.get('pid') or '-'}"
            f" | healthy={server['healthy']}"
            f" | uptime={format_uptime(server.get('uptime') or 0)}"
            f"{busy}"
        )
        proxy_text = (
            f"{'running' if proxy['running'] else 'stopped'}"
            f" | pid={proxy.get('pid') or '-'}"
            f" | healthy={proxy['healthy']}"
            f" | uptime={format_uptime(proxy.get('uptime') or 0)}"
        )
        urls_text = f"OpenAI: {server['openai_url']} | Ollama: {proxy['url']}"
        self.status_vars["server"].set(server_text)
        self.status_vars["proxy"].set(proxy_text)
        self.status_vars["urls"].set(urls_text)
        self.refresh_instances_table()
        self.refresh_logs()
        self._refresh_job = self.root.after(3000, self.refresh_status)

    def on_close(self) -> None:
        """Handle window close event with graceful shutdown dialog."""
        # Check if any processes are running
        server_status = self.manager.server_status()
        proxy_status = self.manager.proxy_status()
        instances_status = self.manager.instances_status()
        running_instances = [i for i in instances_status if i.get("running")]

        if server_status["running"] or proxy_status["running"] or running_instances:
            # Build list of running services
            services = []
            if server_status["running"]:
                services.append("llama-server")
            if proxy_status["running"]:
                services.append("Ollama proxy")
            for inst in running_instances:
                services.append(f"Instance {inst.get('name', inst.get('id', 'unknown'))}")

            message = f"Running services detected: {', '.join(services)}\n\n"
            message += "What would you like to do?"

            result = messagebox.askyesnocancel(
                "Stop services before quit?",
                message,
                default=messagebox.YES,
            )

            if result is None:  # Cancel
                return
            elif result:  # Yes - stop all and quit
                self.stop_all()
                self.root.after(500, self._destroy_window)
            else:  # No - quit without stopping
                self.root.destroy()
        else:
            self.root.destroy()

    def _destroy_window(self) -> None:
        """Destroy window after stop operations."""
        if self.root:
            self.root.destroy()

    def _setup_close_handler(self) -> None:
        """Setup window close handler."""
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Open the llama.cpp Control Deck GUI.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--geometry", default="1180x820", help="initial Tk window geometry")
    parser.add_argument(
        "--skip-device-refresh",
        action="store_true",
        help="start without running llama-server --list-devices immediately",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    root = tk.Tk()
    try:
        LlamaCppGUI(root, geometry=args.geometry, refresh_devices_on_start=not args.skip_device_refresh)
        root.mainloop()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
