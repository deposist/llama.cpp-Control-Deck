# llama.cpp Control Deck

**Desktop control panel and Ollama-compatible proxy for local `llama.cpp` servers.**

`llama.cpp Control Deck` helps you run one or many local GGUF models without
turning every launch into a long shell command. It provides a Tkinter GUI,
multi-instance process management, GPU/device diagnostics, log viewing,
automatic runtime path detection, and an Ollama-compatible proxy that forwards
requests to the OpenAI-compatible API exposed by `llama-server`.

[English summary](#english-summary) | Русский

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform Linux](https://img.shields.io/badge/platform-linux-lightgrey)
![License MIT](https://img.shields.io/badge/license-MIT-green)

## GitHub Description

Tkinter GUI + Ollama-compatible FastAPI proxy for managing one or many local
`llama.cpp` `llama-server` instances.

## Возможности

- Управление локальными моделями через GUI: запуск, остановка, рестарт, статус,
  uptime, health-check и логи.
- Multi-instance режим: отдельные профили и порты для chat, embeddings, rerank,
  multimodal и router.
- Ollama-compatible proxy: клиенты, которые ждут Ollama API, могут работать с
  чистым `llama.cpp`.
- OpenAI-compatible workflow: GUI копирует URL вида `http://127.0.0.1:8081/v1`.
- Автообнаружение `python`, `llama-server`, working directory и `LD_LIBRARY_PATH`.
- Интерактивные кнопки установки Python-зависимостей и системного Tkinter.
- Диагностика GPU через `llama-server --list-devices`.
- CLI для headless-сценариев и проверки generated commands.

## Когда это полезно

Проект подойдёт, если вы:

- запускаете несколько локальных моделей одновременно, например LLM +
  embeddings + rerank;
- хотите заменить Ollama на прямой `llama.cpp`, но оставить совместимость с
  Ollama-клиентами;
- часто меняете модели, контекст, GPU layers, batch size и порты;
- хотите простой локальный OpenAI-compatible endpoint для Open WebUI, IDE,
  RAG-приложений или собственных скриптов.

## Требования

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

## Быстрый старт

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

## Установка `llama.cpp`

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

## Запуск GUI

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

## Первый запуск модели

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

## Несколько моделей одновременно

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

## Ollama-Compatible Proxy

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

## Автообнаружение путей

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

## CLI Режим

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

## Рекомендуемые настройки

### Chat / LLM

```text
Profile: chat
Context: 8192
GPU layers: all
Split mode: none
Flash attention: auto
```

### BGE-M3 / Embeddings

```text
Profile: embeddings
Context: 8192
Batch: 8192
Micro-batch: 8192
GPU layers: all
Split mode: none
Extra args: --pooling cls
```

### Две GPU

```text
Main GPU: 0
Split mode: layer
Tensor split: 3,1
```

## Структура проекта

| Файл | Назначение |
|------|------------|
| `llama_cpp_gui.py` | Tkinter GUI |
| `llama_server_manager.py` | process manager, state, health, CLI |
| `ollama_proxy.py` | FastAPI Ollama-compatible proxy |
| `config.py` | defaults, config merge, runtime detection |
| `start_gui.sh` | Linux launcher |
| `config.example.json` | пример конфигурации |
| `requirements.txt` | runtime dependencies |
| `requirements-dev.txt` | test/lint dependencies |
| `tests/` | smoke tests |

## Разработка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

ruff check .
python3 -m pytest -q
python3 -m py_compile config.py llama_cpp_gui.py llama_server_manager.py ollama_proxy.py
```

Перед pull request:

- обновите README, если меняется поведение;
- добавьте тесты для новой логики;
- не коммитьте `config.json`, `logs/`, `runtime/`, модели и API-ключи.

## Troubleshooting

| Симптом | Вероятная причина | Что сделать |
|---------|-------------------|-------------|
| `ModuleNotFoundError: psutil` | Python-зависимости не установлены | `pip install -r requirements.txt` или кнопка **Install Python libs** |
| `No module named venv` / `.venv` не создаётся | Нет системного `python3-venv` | `sudo apt install python3-venv python3-pip` |
| `Tkinter is not available` | Нет системного Tkinter | `sudo apt install python3-tk` или кнопка **Install system libs** |
| `llama-server not found` | Неверный путь | **Auto-detect runtime** или `LLAMA_CPP_BINARY` |
| Сервер сразу завершается | неверная модель, нет `.so`, не хватает VRAM | открыть вкладку **Logs** |
| `Port 8081 is busy` | порт занят другим процессом | сменить порт или остановить процесс |
| `CUDA error: out of memory` | не хватает VRAM | уменьшить Context, Batch или GPU layers |
| Proxy возвращает 502 | целевой `llama-server` не запущен | сначала запустить сервер |
| GUI долго стартует | `--list-devices` занимает время | `./start_gui.sh --skip-device-refresh` |

## Безопасность

По умолчанию `llama-server` и proxy рассчитаны на локальный trusted network.
Не открывайте `0.0.0.0` в недоверенной сети без firewall, VPN или внешней
аутентификации. Не публикуйте API keys, приватные пути и логи с чувствительными
данными.

См. [SECURITY.md](SECURITY.md).

## Как помочь

Issues и pull requests приветствуются. Особенно полезны:

- тесты на разные сборки `llama.cpp`;
- улучшения UX без усложнения интерфейса;
- документация для популярных клиентов;
- отчёты о несовместимостях с новыми версиями `llama-server`.

См. [CONTRIBUTING.md](CONTRIBUTING.md) и [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Лицензия

[MIT](LICENSE)

## Благодарности

- [ggerganov/llama.cpp](https://github.com/ggerganov/llama.cpp)
- [Ollama](https://ollama.com)
- [FastAPI](https://fastapi.tiangolo.com)
- [httpx](https://www.python-httpx.org)
- [psutil](https://github.com/giampaolo/psutil)

---

## English Summary

`llama.cpp Control Deck` is a Linux desktop GUI and Ollama-compatible proxy for
managing local `llama.cpp` `llama-server` processes. It can run one or many GGUF
models, manage per-instance ports and profiles, expose OpenAI-compatible and
Ollama-compatible endpoints, detect runtime paths automatically, show logs, and
run basic GPU/device diagnostics.

Quick start:

```bash
git clone https://github.com/deposist/llama.cpp-Control-Deck.git
cd llama.cpp-Control-Deck
sudo apt install -y python3 python3-venv python3-pip python3-tk
./start_gui.sh --setup
```

Repository description:

```text
Tkinter GUI + Ollama-compatible FastAPI proxy for managing one or many local llama.cpp llama-server instances.
```
