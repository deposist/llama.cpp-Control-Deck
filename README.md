# llama.cpp Control Deck

**Web/Desktop control panel and Ollama-compatible proxy for local `llama.cpp` servers.**

`llama.cpp Control Deck` helps you run one or many local GGUF models without
turning every launch into a long shell command. It provides a local FastAPI web
UI, a legacy Tkinter GUI, multi-instance process management, GPU/device
diagnostics, log viewing, automatic runtime path detection, beginner-friendly
setup, and an Ollama-compatible proxy that forwards requests to the
OpenAI-compatible API exposed by `llama-server`.

[English](#english) | [Русский](#русский)

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform Linux](https://img.shields.io/badge/platform-linux-lightgrey)
![License MIT](https://img.shields.io/badge/license-MIT-green)

## English

### GitHub Description

Tkinter GUI + Ollama-compatible FastAPI proxy for managing one or many local
`llama.cpp` `llama-server` instances.

### Features

- GUI control for local models: start, stop, restart, status, uptime,
  health checks, and logs.
- Multi-instance mode for chat, embeddings, rerank, multimodal, and router
  profiles, each with its own model, port, and runtime settings.
- Ollama-compatible proxy for tools that expect the Ollama API.
- OpenAI-compatible workflow: copy URLs like `http://127.0.0.1:8081/v1`.
- Automatic detection of `python`, `llama-server`, working directory, and
  `LD_LIBRARY_PATH`.
- Automatic download/update flow for prebuilt `llama.cpp` `llama-server`
  releases from GitHub.
- Beginner setup mode that creates a local `.venv` and installs Python
  dependencies.
- Interactive buttons for Python dependencies and system Tkinter packages.
- GPU/device diagnostics through `llama-server --list-devices`.
- CLI commands for headless diagnostics and generated command inspection.

### When To Use It

Use Control Deck if you:

- run multiple local models at the same time, for example LLM + embeddings +
  rerank;
- want direct `llama.cpp` usage while keeping compatibility with Ollama clients;
- frequently change models, context size, GPU layers, batch size, and ports;
- need a local OpenAI-compatible endpoint for Open WebUI, IDE tools, RAG apps,
  or your own scripts.

### Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Linux | Ubuntu 22.04/24.04 |
| Python | 3.10 | 3.11+ |
| `llama.cpp` | built `llama-server` | CUDA build for NVIDIA GPU |
| RAM | 8 GB | 32 GB+ |
| GPU | optional | NVIDIA CUDA |

System packages:

- `python3`
- `python3-venv`
- `python3-pip`
- `python3-tk` / `python3-tkinter` / `tk`

Python dependencies:

- `psutil`
- `fastapi`
- `uvicorn`
- `httpx`

### Quick Start

Beginner-friendly path:

```bash
git clone https://github.com/deposist/llama.cpp-Control-Deck.git
cd llama.cpp-Control-Deck

./start_gui.sh --setup
```

`--setup` creates a local `.venv`, installs Python dependencies, and starts the
GUI. If Tkinter is missing, install the system package first:

```bash
# Debian / Ubuntu
sudo apt install -y python3 python3-venv python3-pip python3-tk
```

Manual setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Debian / Ubuntu
sudo apt install -y python3-tk

./start_gui.sh
```

After the GUI opens, go to **Server**, click **Auto-detect runtime**, choose a
`.gguf` model, and click **Start**.

### Installing `llama.cpp`

If `llama-server` is not built yet:

```bash
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp

# CUDA build for NVIDIA GPU
cmake -B build-cuda -DGGML_CUDA=ON
cmake --build build-cuda --config Release -j"$(nproc)"

# CPU-only build
# cmake -B build
# cmake --build build --config Release -j"$(nproc)"
```

The binary is usually located at:

```text
llama.cpp/build-cuda/bin/llama-server
```

### Running The GUI

Recommended web control panel:

```bash
./start_web.sh
```

Then open:

```text
http://127.0.0.1:8765
```

The web UI keeps the existing Python manager/proxy logic, adds a beginner
launch flow, RU/EN language switching, validation warnings, logs, GPU/device
diagnostics, release controls, and advanced settings in the browser. It uses
FastAPI, server-rendered HTML, CSS, and vanilla JavaScript; Electron, Node.js,
React, Vue, and Svelte are not required.

Path fields in the web UI have **Browse** buttons. They open a local
server-side picker for Python, `llama-server`, working directories,
`LD_LIBRARY_PATH`, `.gguf` models, MMProj files, model directories, and preset
files. The picker selects paths on the machine running `control_web.py`; it
does not upload or copy files through the browser.

Use **Runtime & updates** for `llama-server` release checks and downloads.
Downloads run in the background and the page shows the current status plus the
latest progress lines, so the browser does not look frozen during large
archives.

Use **Services** to manage multi-instance servers from the browser. The web UI
can add, edit, validate, duplicate, delete, start, stop, and restart services,
while keeping the existing `config.json` instance format compatible with the
legacy Tkinter GUI and CLI.

Legacy Tkinter GUI:

```bash
./start_gui.sh
```

For a clean first run:

```bash
./start_gui.sh --setup
```

Or run the GUI module directly:

```bash
python3 llama_cpp_gui.py
```

Useful options:

```bash
python3 control_web.py --help
python3 control_web.py --host 127.0.0.1 --port 8765
python3 llama_cpp_gui.py --help
./start_gui.sh --setup
python3 llama_cpp_gui.py --geometry 1280x860
python3 llama_cpp_gui.py --skip-device-refresh
```

### First Model Launch

1. Open the **Server** tab.
2. If you did not start with `--setup`, click **Beginner setup**.
3. Click **Auto-detect runtime**.
4. Select a model in **Model .gguf**.
5. Check **Host**, **Port**, **Context**, and **GPU layers**.
6. Click **Save**.
7. Click **Start**.
8. When the server is `running`, click **Copy OpenAI URL**.

The URL will look like this:

```text
http://127.0.0.1:8081/v1
```

Use it in Open WebUI, Continue, an OpenAI-compatible client, or a RAG app.

### Running Multiple Models

Use the **Instances** tab for multiple servers.

1. Select an existing row or click **Add**.
2. Set `Profile`, `Model .gguf`, `Port`, and `Alias`.
3. Click **Apply to selected**.
4. Click **Start selected** or **Start enabled**.

Typical layout:

| Instance | Profile | Port | Purpose |
|----------|---------|------|---------|
| Chat | `chat` | `8081` | conversational LLM |
| Embeddings | `embeddings` | `8082` | RAG embeddings |
| Rerank | `rerank` | `8083` | document reranking |
| Vision | `multimodal` | `8084` | multimodal model with `mmproj` |
| Router | `router` | `8085` | multi-model router |

### Ollama-Compatible Proxy

Some clients only know how to talk to the Ollama API. The built-in proxy accepts
Ollama-style requests and forwards them to the OpenAI API exposed by
`llama-server`.

1. Open the **Ollama proxy** tab.
2. Leave **Target OpenAI URL** empty to use the active server, or set a specific
   instance URL.
3. Click **Start proxy**.
4. Click **Copy Ollama URL**.

Default proxy URL:

```text
http://127.0.0.1:11435
```

Supported endpoints:

- `GET /`
- `GET /api/version`
- `GET /api/tags`
- `POST /api/chat`
- `POST /api/generate`
- `POST /api/embeddings`
- `POST /api/embed`

### Runtime Auto-Detection

Control Deck can detect:

- Python runtime
- `llama-server`
- working directory
- `LD_LIBRARY_PATH`
- models directory

Environment variables override detection:

```bash
export LLAMA_CPP_PYTHON=/path/to/.venv/bin/python
export LLAMA_CPP_BINARY=/path/to/llama.cpp/build-cuda/bin/llama-server
export LLAMA_CPP_CWD=/path/to/llama.cpp/build-cuda/bin
export LLAMA_CPP_LIB_DIR=/path/to/llama.cpp/build-cuda/bin
export LLAMA_CPP_MODELS_DIR=/path/to/models
export LLAMA_CPP_SEARCH_ROOTS=/extra/search/root:/another/root
```

CLI:

```bash
python3 config.py --detect-runtime
python3 config.py --apply-runtime
```

`--detect-runtime` only prints detected paths. `--apply-runtime` updates
`config.json`.

### Downloading And Updating `llama-server`

The **Server → Runtime** block includes release-management buttons:

- **Check server version** runs the selected `llama-server --version`.
- **Check updates** checks the latest `ggml-org/llama.cpp` GitHub release and
  compares it with the managed install when possible.
- **Download llama-server** downloads the latest prebuilt archive, extracts it
  under `runtime/llama.cpp/`, and updates Runtime paths automatically.

Choose **llama.cpp backend** before downloading:

| Backend | Notes |
|---------|-------|
| `auto` / `cpu` | Most compatible prebuilt Linux option. |
| `vulkan` | GPU acceleration through Vulkan drivers. |
| `rocm` | AMD ROCm build, requires ROCm runtime. |
| `openvino` | Intel OpenVINO build. |
| `sycl-fp16` / `sycl-fp32` | SYCL builds for supported systems. |

Current upstream Linux releases may not include a CUDA prebuilt archive. For
CUDA, build `llama.cpp` yourself and use **Auto-detect runtime** or **Browse**.

### CLI Mode

The GUI is not required for diagnostics or headless use:

```bash
python3 llama_server_manager.py status
python3 llama_server_manager.py server-command
python3 llama_server_manager.py instance-command chat-8081
python3 llama_server_manager.py proxy-command
python3 llama_server_manager.py devices
```

You can also start the proxy directly:

```bash
python3 ollama_proxy.py \
  --host 127.0.0.1 \
  --port 11435 \
  --target-base-url http://127.0.0.1:8081/v1 \
  --model local-llama
```

### Recommended Settings

#### Chat / LLM

```text
Profile: chat
Context: 8192
GPU layers: all
Split mode: none
Flash attention: auto
```

#### BGE-M3 / Embeddings

```text
Profile: embeddings
Context: 8192
Batch: 8192
Micro-batch: 8192
GPU layers: all
Split mode: none
Extra args: --pooling cls
```

#### Two GPUs

```text
Main GPU: 0
Split mode: layer
Tensor split: 3,1
```

### Project Structure

| File | Purpose |
|------|---------|
| `control_web.py` | local FastAPI Web UI |
| `llama_cpp_gui.py` | Tkinter GUI |
| `llama_server_manager.py` | process manager, state, health, CLI |
| `ollama_proxy.py` | FastAPI Ollama-compatible proxy |
| `config.py` | defaults, config merge, runtime detection |
| `llama_cpp_release.py` | GitHub release check/download/install helper |
| `start_web.sh` | Linux Web UI launcher |
| `start_gui.sh` | Linux launcher |
| `config.example.json` | example configuration |
| `requirements.txt` | runtime dependencies |

### Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `ModuleNotFoundError: psutil` | Python dependencies are missing | `pip install -r requirements.txt` or **Install Python libs** |
| `No module named venv` / `.venv` cannot be created | system `python3-venv` is missing | `sudo apt install python3-venv python3-pip` |
| `Tkinter is not available` | system Tkinter is missing | `sudo apt install python3-tk` or **Install system libs** |
| `llama-server not found` | wrong binary path | **Auto-detect runtime** or `LLAMA_CPP_BINARY` |
| downloaded server starts without GPU acceleration | CPU backend was selected or required driver is missing | choose `vulkan`/`rocm` backend or build CUDA manually |
| server exits immediately | wrong model, missing `.so`, not enough VRAM | open **Logs** |
| `Port 8081 is busy` | another process uses the port | change the port or stop the process |
| `CUDA error: out of memory` | not enough VRAM | reduce Context, Batch, or GPU layers |
| proxy returns 502 | target `llama-server` is not running | start the server first |
| GUI startup is slow | `--list-devices` takes time | `./start_gui.sh --skip-device-refresh` |
| Web UI freezes during refresh | overlapping parallel `refresh` requests queue up | fixed in v1.0.2 — overlapping polls are now dropped |
| Warning text unreadable in web UI | low colour contrast | fixed in v1.0.2 — colours now meet WCAG AA |

### Security

By default, `llama-server` and the proxy are intended for trusted local
environments. Do not bind services to `0.0.0.0` on untrusted networks without a
firewall, VPN, reverse proxy authentication, or another access-control layer.
Do not publish API keys, private paths, or logs with sensitive data.

### License

[MIT](LICENSE)

### Acknowledgements

- [ggerganov/llama.cpp](https://github.com/ggerganov/llama.cpp)
- [Ollama](https://ollama.com)
- [FastAPI](https://fastapi.tiangolo.com)
- [httpx](https://www.python-httpx.org)
- [psutil](https://github.com/giampaolo/psutil)

---

## Русский

### Описание для GitHub

Tkinter GUI + Ollama-compatible FastAPI proxy для управления одним или
несколькими локальными `llama.cpp` `llama-server` instance.

### Возможности

- Управление локальными моделями через GUI: запуск, остановка, рестарт, статус,
  uptime, health-check и логи.
- Multi-instance режим: отдельные профили и порты для chat, embeddings, rerank,
  multimodal и router.
- Ollama-compatible proxy: клиенты, которые ждут Ollama API, могут работать с
  чистым `llama.cpp`.
- OpenAI-compatible workflow: GUI копирует URL вида `http://127.0.0.1:8081/v1`.
- Автообнаружение `python`, `llama-server`, working directory и
  `LD_LIBRARY_PATH`.
- Автоматическое скачивание/обновление prebuilt `llama.cpp` `llama-server`
  release с GitHub.
- Beginner setup: создание локального `.venv` и установка Python-зависимостей
  одной командой.
- Интерактивные кнопки установки Python-зависимостей и системного Tkinter.
- Диагностика GPU через `llama-server --list-devices`.
- CLI для headless-сценариев и проверки generated commands.

### Когда это полезно

Проект подойдёт, если вы:

- запускаете несколько локальных моделей одновременно, например LLM +
  embeddings + rerank;
- хотите заменить Ollama на прямой `llama.cpp`, но оставить совместимость с
  Ollama-клиентами;
- часто меняете модели, контекст, GPU layers, batch size и порты;
- хотите простой локальный OpenAI-compatible endpoint для Open WebUI, IDE,
  RAG-приложений или собственных скриптов.

### Требования

| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| ОС | Linux | Ubuntu 22.04/24.04 |
| Python | 3.10 | 3.11+ |
| `llama.cpp` | собранный `llama-server` | CUDA build для NVIDIA GPU |
| RAM | 8 GB | 32 GB+ |
| GPU | опционально | NVIDIA CUDA |

Системные пакеты:

- `python3`
- `python3-venv`
- `python3-pip`
- `python3-tk` / `python3-tkinter` / `tk`

Python-зависимости:

- `psutil`
- `fastapi`
- `uvicorn`
- `httpx`

### Быстрый старт

Самый простой вариант для новичков:

```bash
git clone https://github.com/deposist/llama.cpp-Control-Deck.git
cd llama.cpp-Control-Deck

./start_gui.sh --setup
```

`--setup` создаёт локальное `.venv`, устанавливает Python-зависимости и запускает
GUI. Если Tkinter ещё не установлен, поставьте системный пакет:

```bash
# Debian / Ubuntu
sudo apt install -y python3 python3-venv python3-pip python3-tk
```

Ручной вариант:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Debian / Ubuntu
sudo apt install -y python3-tk

./start_gui.sh
```

Если GUI открылся, перейдите во вкладку **Server**, нажмите
**Auto-detect runtime**, выберите `.gguf` модель и нажмите **Start**.

### Установка `llama.cpp`

Если `llama-server` ещё не собран:

```bash
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp

# CUDA build для NVIDIA GPU
cmake -B build-cuda -DGGML_CUDA=ON
cmake --build build-cuda --config Release -j"$(nproc)"

# CPU-only вариант
# cmake -B build
# cmake --build build --config Release -j"$(nproc)"
```

После сборки бинарник обычно находится здесь:

```text
llama.cpp/build-cuda/bin/llama-server
```

### Запуск Web UI

Рекомендуемый способ управления — локальная веб-панель:

```bash
./start_web.sh
```

Затем откройте в браузере:

```text
http://127.0.0.1:8765
```

Веб-интерфейс сохраняет всю существующую логику менеджера и proxy, добавляя
начальный launch flow, переключение языка RU/EN, валидацию, логи, диагностику
GPU, управление release и расширенные настройки. Используются FastAPI,
server-rendered HTML, CSS и vanilla JavaScript; Electron, Node.js, React, Vue и
Svelte не требуются.

Поля путей в веб-интерфейсе имеют кнопки **Browse**, которые открывают
серверный файловый picker для Python, `llama-server`, рабочих директорий,
`LD_LIBRARY_PATH`, `.gguf` моделей, MMProj, директорий моделей и preset-файлов.
Picker выбирает пути на машине, где запущен `control_web.py`; файлы через браузер
не загружаются и не копируются.

Раздел **Runtime & updates** служит для проверки и скачивания `llama-server`
release. Загрузки выполняются в фоне, а страница показывает текущий статус и
последние строки прогресса, чтобы браузер не выглядел зависшим во время
загрузки больших архивов.

Раздел **Services** управляет multi-instance серверами из браузера: добавление,
редактирование, валидация, дублирование, удаление, запуск, остановка и рестарт,
с сохранением совместимости формата `config.json` с legacy Tkinter GUI и CLI.

### Запуск GUI (legacy)

```bash
./start_gui.sh
```

Для первого запуска на чистой системе:

```bash
./start_gui.sh --setup
```

или:

```bash
python3 llama_cpp_gui.py
```

Полезные опции:

```bash
python3 llama_cpp_gui.py --help
./start_gui.sh --setup
python3 llama_cpp_gui.py --geometry 1280x860
python3 llama_cpp_gui.py --skip-device-refresh
```

### Первый запуск модели

1. Откройте вкладку **Server**.
2. Если запускали GUI не через `--setup`, нажмите **Beginner setup**.
3. Нажмите **Auto-detect runtime**.
4. В поле **Model .gguf** выберите модель.
5. Проверьте **Host**, **Port**, **Context**, **GPU layers**.
6. Нажмите **Save**.
7. Нажмите **Start**.
8. Когда сервер стал `running`, нажмите **Copy OpenAI URL**.

URL будет выглядеть примерно так:

```text
http://127.0.0.1:8081/v1
```

Его можно вставить в Open WebUI, Continue, собственный OpenAI-compatible клиент
или RAG-приложение.

### Несколько моделей одновременно

Для нескольких серверов используйте вкладку **Instances**.

1. Выберите существующую строку или нажмите **Add**.
2. Укажите `Profile`, `Model .gguf`, `Port`, `Alias`.
3. Нажмите **Apply to selected**.
4. Нажмите **Start selected** или **Start enabled**.

Типичный набор:

| Instance | Profile | Port | Назначение |
|----------|---------|------|------------|
| Chat | `chat` | `8081` | диалоговая модель |
| Embeddings | `embeddings` | `8082` | RAG-векторизация |
| Rerank | `rerank` | `8083` | переоценка документов |
| Vision | `multimodal` | `8084` | multimodal модель с `mmproj` |
| Router | `router` | `8085` | multi-model router |

### Ollama-Compatible Proxy

Некоторые клиенты умеют подключаться только к Ollama API. Встроенный прокси
принимает Ollama-style запросы и отправляет их в OpenAI API `llama-server`.

1. Откройте вкладку **Ollama proxy**.
2. Оставьте **Target OpenAI URL** пустым, чтобы использовать активный сервер,
   или укажите конкретный URL instance.
3. Нажмите **Start proxy**.
4. Нажмите **Copy Ollama URL**.

По умолчанию прокси слушает:

```text
http://127.0.0.1:11435
```

Поддерживаемые endpoints:

- `GET /`
- `GET /api/version`
- `GET /api/tags`
- `POST /api/chat`
- `POST /api/generate`
- `POST /api/embeddings`
- `POST /api/embed`

### Автообнаружение путей

Control Deck умеет искать:

- Python runtime
- `llama-server`
- working directory
- `LD_LIBRARY_PATH`
- папку моделей

Приоритеты можно задать переменными окружения:

```bash
export LLAMA_CPP_PYTHON=/path/to/.venv/bin/python
export LLAMA_CPP_BINARY=/path/to/llama.cpp/build-cuda/bin/llama-server
export LLAMA_CPP_CWD=/path/to/llama.cpp/build-cuda/bin
export LLAMA_CPP_LIB_DIR=/path/to/llama.cpp/build-cuda/bin
export LLAMA_CPP_MODELS_DIR=/path/to/models
export LLAMA_CPP_SEARCH_ROOTS=/extra/search/root:/another/root
```

CLI:

```bash
python3 config.py --detect-runtime
python3 config.py --apply-runtime
```

`--detect-runtime` только печатает найденные пути. `--apply-runtime` обновляет
`config.json`.

### Скачивание и обновление `llama-server`

В блоке **Server → Runtime** есть кнопки управления release:

- **Check server version** запускает `llama-server --version` для выбранного
  бинарника.
- **Check updates** проверяет последний release `ggml-org/llama.cpp` на GitHub
  и сравнивает его с managed install, если он есть.
- **Download llama-server** скачивает последний prebuilt archive, распаковывает
  его в `runtime/llama.cpp/` и автоматически прописывает Runtime paths.

Перед скачиванием выберите **llama.cpp backend**:

| Backend | Примечание |
|---------|------------|
| `auto` / `cpu` | Самый совместимый prebuilt Linux-вариант. |
| `vulkan` | GPU acceleration через Vulkan drivers. |
| `rocm` | AMD ROCm build, нужен ROCm runtime. |
| `openvino` | Intel OpenVINO build. |
| `sycl-fp16` / `sycl-fp32` | SYCL builds для поддерживаемых систем. |

В текущих upstream Linux releases может не быть CUDA prebuilt archive. Для CUDA
соберите `llama.cpp` вручную и используйте **Auto-detect runtime** или
**Browse**.

### CLI Режим

GUI не обязателен для диагностики и headless-сценариев:

```bash
python3 llama_server_manager.py status
python3 llama_server_manager.py server-command
python3 llama_server_manager.py instance-command chat-8081
python3 llama_server_manager.py proxy-command
python3 llama_server_manager.py devices
```

Прокси можно запустить отдельно:

```bash
python3 ollama_proxy.py \
  --host 127.0.0.1 \
  --port 11435 \
  --target-base-url http://127.0.0.1:8081/v1 \
  --model local-llama
```

### Рекомендуемые настройки

#### Chat / LLM

```text
Profile: chat
Context: 8192
GPU layers: all
Split mode: none
Flash attention: auto
```

#### BGE-M3 / Embeddings

```text
Profile: embeddings
Context: 8192
Batch: 8192
Micro-batch: 8192
GPU layers: all
Split mode: none
Extra args: --pooling cls
```

#### Две GPU

```text
Main GPU: 0
Split mode: layer
Tensor split: 3,1
```

### Структура проекта

| Файл | Назначение |
|------|------------|
| `control_web.py` | local FastAPI Web UI |
| `llama_cpp_gui.py` | Tkinter GUI |
| `llama_server_manager.py` | process manager, state, health, CLI |
| `ollama_proxy.py` | FastAPI Ollama-compatible proxy |
| `config.py` | defaults, config merge, runtime detection |
| `llama_cpp_release.py` | helper для проверки/скачивания/установки GitHub release |
| `start_web.sh` | Linux Web UI launcher |
| `start_gui.sh` | Linux launcher |
| `config.example.json` | пример конфигурации |
| `requirements.txt` | runtime dependencies |

### Устранение проблем

| Симптом | Вероятная причина | Что сделать |
|---------|-------------------|-------------|
| `ModuleNotFoundError: psutil` | Python-зависимости не установлены | `pip install -r requirements.txt` или кнопка **Install Python libs** |
| `No module named venv` / `.venv` не создаётся | Нет системного `python3-venv` | `sudo apt install python3-venv python3-pip` |
| `Tkinter is not available` | Нет системного Tkinter | `sudo apt install python3-tk` или кнопка **Install system libs** |
| `llama-server not found` | Неверный путь | **Auto-detect runtime** или `LLAMA_CPP_BINARY` |
| скачанный сервер работает без GPU acceleration | выбран CPU backend или нет нужного драйвера | выбрать `vulkan`/`rocm` backend или собрать CUDA вручную |
| Сервер сразу завершается | неверная модель, нет `.so`, не хватает VRAM | открыть вкладку **Logs** |
| `Port 8081 is busy` | порт занят другим процессом | сменить порт или остановить процесс |
| `CUDA error: out of memory` | не хватает VRAM | уменьшить Context, Batch или GPU layers |
| Proxy возвращает 502 | целевой `llama-server` не запущен | сначала запустить сервер |
| GUI долго стартует | `--list-devices` занимает время | `./start_gui.sh --skip-device-refresh` |
| Веб-интерфейс зависает при обновлении | накопление параллельных запросов `refresh` | обновлено в v1.0.2 — теперь overlapping polls отбрасываются |
| Предупреждения в веб-интерфейсе нечитаемы | низкий контраст цветов | обновлено в v1.0.2 — цвета соответствуют WCAG AA |

### Безопасность

По умолчанию `llama-server` и proxy рассчитаны на локальный trusted network.
Не открывайте `0.0.0.0` в недоверенной сети без firewall, VPN, reverse proxy
authentication или другого слоя контроля доступа. Не публикуйте API keys,
приватные пути и логи с чувствительными данными.

### Лицензия

[MIT](LICENSE)

### Благодарности

- [ggerganov/llama.cpp](https://github.com/ggerganov/llama.cpp)
- [Ollama](https://ollama.com)
- [FastAPI](https://fastapi.tiangolo.com)
- [httpx](https://www.python-httpx.org)
- [psutil](https://github.com/giampaolo/psutil)
